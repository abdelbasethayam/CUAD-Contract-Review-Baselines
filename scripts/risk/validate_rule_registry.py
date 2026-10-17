#!/usr/bin/env python3
"""Validate registry reproducibility, source completeness, and execution gates."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts" / "risk") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "risk"))
from build_rule_registry import (
    MANIFEST_PATH,
    REGISTRY_PATH,
    SOURCE_REGISTRY_PATH,
    PLAYBOOK_PATH,
    CONTRACT_PROFILES,
    AUTHORITY_MAP_PATH,
    AUTHORITY_CATALOG_PATH,
    _base_inputs,
    _git_blob_sha,
    build_artifacts,
)

RULE_SCHEMA_PATH = ROOT / "data" / "risk" / "rule_registry.schema.json"
SOURCE_SCHEMA_PATH = ROOT / "data" / "risk" / "source_registry.schema.json"

def _rule_lifecycle_problems(item: dict[str, object]) -> list[str]:
    """Return governance violations for a single base rule without mutating it."""
    problems: list[str] = []
    if item.get("record_kind") != "BASE_RULE":
        return problems
    status = item.get("validation_status")
    approval_status = item.get("approval_status")
    execution_status = item.get("execution_status")
    eligible = item.get("execution_eligible") is True
    governance = item.get("review_governance") or {}
    if status in {"ADJUDICATED", "APPROVED"}:
        raw_reviewers = governance.get("reviewer_ids") or []
        reviewers = [
            str(reviewer).strip()
            for reviewer in raw_reviewers
            if isinstance(reviewer, str) and reviewer.strip()
        ] if isinstance(raw_reviewers, list) else []
        raw_decisions = governance.get("reviewer_decisions") or []
        decisions = [decision for decision in raw_decisions if isinstance(decision, dict)] if isinstance(raw_decisions, list) else []
        decision_ids = [str(decision.get("reviewer_id") or "").strip() for decision in decisions]
        valid_decision_labels = {"POTENTIAL_RISK", "NO_RISK", "INSUFFICIENT_EVIDENCE", "NOT_APPLICABLE"}
        adjudicator = str(governance.get("adjudicator_id") or "").strip()
        if (
            governance.get("status") != status
            or len(set(reviewers)) < 2
            or len(reviewers) != len(raw_reviewers)
            or len(decisions) < 2
            or len(set(decision_ids)) != len(decision_ids)
            or set(decision_ids) != set(reviewers)
            or any(
                decision.get("decision") not in valid_decision_labels
                or not str(decision.get("rationale") or "").strip()
                or not str(decision.get("reviewed_at") or "").strip()
                for decision in decisions
            )
            or not adjudicator
            or adjudicator in set(reviewers)
            or not str(governance.get("adjudication_reference") or "").strip()
            or not str(governance.get("adjudicated_at") or "").strip()
        ):
            problems.append(f"independent_adjudication_metadata_incomplete:{item.get('rule_id')}")
    if status == "APPROVED":
        if (
            approval_status != "APPROVED"
            or execution_status != "APPROVED_FOR_EXECUTION"
            or not eligible
            or not str(governance.get("approved_by") or "").strip()
            or not str(governance.get("approved_at") or "").strip()
            or not str(governance.get("approval_basis") or "").strip()
        ):
            problems.append(f"approved_rule_missing_approval_gate:{item.get('rule_id')}")
        cases = item.get("regression_cases") or {}
        if not cases.get("positive") or not cases.get("negative") or not cases.get("edge"):
            problems.append(f"approved_rule_missing_positive_negative_edge_tests:{item.get('rule_id')}")
        scope = [str(value).strip().upper() for value in (item.get("jurisdiction_scope") or [])]
        if item.get("jurisdiction_status") != "VERIFIED" or not scope or any(value in {"", "UNSPECIFIED", "UNKNOWN"} for value in scope):
            problems.append(f"approved_rule_jurisdiction_not_verified:{item.get('rule_id')}")
        authority_sources = (item.get("legal_authority") or {}).get("sources") or []
        if not authority_sources or any(
            source.get("citation_status") != "VERIFIED_PINPOINT"
            or not str(source.get("pinpoint_citation") or "").strip()
            or not str(source.get("retrieval_date") or "").strip()
            or str(source.get("jurisdiction") or "").strip().upper() in {
                "", "UNSPECIFIED", "NON_JURISDICTIONAL_PRACTICE",
                "NON_JURISDICTIONAL_DRAFTING_GUIDANCE",
                "NOT_APPLICABLE_NONLEGAL_GUIDANCE",
            }
            or str(source.get("effective_date_status") or "").strip().upper() not in {
                "VERIFIED", "VERIFIED_FOR_RELEVANT_PERIOD", "NOT_APPLICABLE",
            }
            for source in authority_sources
        ):
            problems.append(f"approved_rule_source_scope_not_verified:{item.get('rule_id')}")
    elif approval_status == "APPROVED" or execution_status == "APPROVED_FOR_EXECUTION":
        problems.append(f"rule_approval_state_inconsistent:{item.get('rule_id')}")
    if status == "REJECTED" and eligible:
        problems.append(f"rejected_rule_execution_enabled:{item.get('rule_id')}")
    if item.get("legal_conclusion_allowed") is not False:
        problems.append(f"rule_must_not_emit_legal_conclusion:{item.get('rule_id')}")
    return problems


def main() -> int:
    playbook = json.loads(PLAYBOOK_PATH.read_text(encoding="utf-8"))
    expected_registry, expected_sources, expected_manifest = build_artifacts(playbook)
    problems: list[str] = []
    for path, expected in (
        (REGISTRY_PATH, expected_registry),
        (SOURCE_REGISTRY_PATH, expected_sources),
        (MANIFEST_PATH, expected_manifest),
    ):
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            problems.append(f"stale_or_missing:{path.relative_to(ROOT)}")
    if problems:
        print(json.dumps({"status": "FAIL", "problems": problems}, indent=2))
        return 1

    records = [json.loads(line) for line in REGISTRY_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    sources = json.loads(SOURCE_REGISTRY_PATH.read_text(encoding="utf-8"))
    authority_map_doc = json.loads(AUTHORITY_MAP_PATH.read_text(encoding="utf-8"))
    authority_catalog_doc = json.loads(AUTHORITY_CATALOG_PATH.read_text(encoding="utf-8"))
    authority_by_clause = {
        str(entry["clause_type"]): entry
        for entry in authority_map_doc.get("clauses", [])
        if entry.get("clause_type")
    }
    authority_catalog_by_id = {
        str(entry["authority_id"]): entry
        for entry in authority_catalog_doc.get("authorities", [])
        if entry.get("authority_id")
    }
    rule_schema = json.loads(RULE_SCHEMA_PATH.read_text(encoding="utf-8"))
    source_schema = json.loads(SOURCE_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(rule_schema)
    Draft202012Validator.check_schema(source_schema)
    rule_validator = Draft202012Validator(rule_schema, format_checker=FormatChecker())
    source_validator = Draft202012Validator(source_schema, format_checker=FormatChecker())
    schema_errors: list[str] = []
    for record_number, record in enumerate(records, start=1):
        for error in rule_validator.iter_errors(record):
            schema_errors.append(
                f"rule_schema:record_{record_number}:{'/'.join(str(part) for part in error.absolute_path)}:{error.message}"
            )
            if len(schema_errors) >= 100:
                break
        if len(schema_errors) >= 100:
            break
    for source in sources.get("sources", []):
        for error in source_validator.iter_errors(source):
            schema_errors.append(
                f"source_schema:{source.get('source_id', '<missing-id>')}:{'/'.join(str(part) for part in error.absolute_path)}:{error.message}"
            )
            if len(schema_errors) >= 100:
                break
        if len(schema_errors) >= 100:
            break
    if schema_errors:
        problems.extend(f"schema_validation_error:{item}" for item in schema_errors)
        print(json.dumps({"status": "FAIL", "problems": problems}, indent=2))
        return 1
    ids = [item["rule_id"] for item in records]
    if len(ids) != len(set(ids)):
        problems.append("duplicate_rule_ids")
    if len(records) != manifest["total_rule_records"]:
        problems.append("manifest_record_count_mismatch")
    if sum(item["record_kind"] == "BASE_RULE" for item in records) != manifest["base_rule_count"]:
        problems.append("base_rule_count_mismatch")
    if sum(item["record_kind"] == "CONTEXT_VARIANT_CANDIDATE" for item in records) != manifest["candidate_rule_count"]:
        problems.append("candidate_rule_count_mismatch")
    approved_rules = [
        item for item in records
        if item.get("record_kind") == "BASE_RULE"
        and item.get("validation_status") == "APPROVED"
        and item.get("approval_status") == "APPROVED"
        and item.get("execution_eligible") is True
    ]
    if manifest["production_approved_rule_count"] != len(approved_rules):
        problems.append("manifest_approved_rule_count_mismatch")
    if approved_rules and playbook.get("approval_status") != "APPROVED":
        problems.append("approved_rule_under_unapproved_playbook")
    if any(item["execution_eligible"] for item in records if item["record_kind"] == "CONTEXT_VARIANT_CANDIDATE"):
        problems.append("candidate_rule_enabled_for_execution")
    for item in records:
        problems.extend(_rule_lifecycle_problems(item))
    for item in records:
        if item["record_kind"] != "BASE_RULE" or item.get("rule_family") != "DETERMINISTIC_REGEX":
            continue
        cases = item.get("regression_cases") or {}
        if not cases.get("positive") or not cases.get("negative") or not cases.get("edge"):
            problems.append(f"deterministic_rule_missing_positive_negative_or_edge_cases:{item.get('base_rule_id')}")
    source_ids = {item["source_id"] for item in sources["sources"]}
    if any(set(item.get("source_ids") or []) - source_ids for item in records):
        problems.append("dangling_source_reference")
    base_keys = {item["base_rule_key"] for item in records if item["record_kind"] == "BASE_RULE"}
    if any(item.get("base_rule_key") not in base_keys for item in records if item["record_kind"] == "CONTEXT_VARIANT_CANDIDATE"):
        problems.append("candidate_without_base_rule")
    required_rule_fields = {
        "rule_id", "base_rule_key", "base_rule_id", "record_kind", "rule_family",
        "title", "risk_domain", "perspective", "contract_type_profile", "contract_type_scope",
        "jurisdiction_scope", "jurisdiction_status", "decision_logic", "evidence_contract",
        "source_ids", "source_status", "source_tier", "authority_jurisdictions",
        "effective_dates", "pinpoint_citations", "citation_status", "legal_authority",
        "severity_rationale", "confidence_policy", "regression_cases", "validation_status",
        "approval_status", "execution_status", "execution_eligible",
        "legal_conclusion_allowed", "source_playbook_hash", "authority_map",
    }
    if any(required_rule_fields - set(item) for item in records if item["record_kind"] == "BASE_RULE"):
        problems.append("base_rule_missing_required_structured_fields")
    for item in records:
        if item["record_kind"] != "BASE_RULE":
            continue
        authority = item.get("legal_authority") or {}
        authority_sources = authority.get("sources") or []
        authority_ids = {str(source.get("source_id")) for source in authority_sources}
        if authority_ids != set(str(source_id) for source_id in (item.get("source_ids") or [])):
            problems.append(f"rule_authority_reference_mismatch:{item.get('rule_id')}")
        for source in authority_sources:
            required_authority_fields = {
                "source_id", "source_title", "source_url", "source_tier",
                "authority_status", "jurisdiction", "effective_date",
                "effective_date_status", "pinpoint_citation", "citation_status",
                "retrieval_date", "license_status", "transferability",
                "can_support_legal_conclusion",
            }
            if required_authority_fields - set(source):
                problems.append(f"rule_authority_metadata_incomplete:{item.get('rule_id')}:{source.get('source_id')}")
            if source.get("can_support_legal_conclusion") and (
                not source.get("pinpoint_citation") or source.get("citation_status") != "VERIFIED_PINPOINT"
            ):
                problems.append(f"rule_has_unverified_legal_authority:{item.get('rule_id')}:{source.get('source_id')}")
        if authority.get("can_support_legal_conclusion") is True and not authority_sources:
            problems.append(f"rule_legal_conclusion_without_source:{item.get('rule_id')}")
    if any(not item.get("inherits_from_base_rule") or not item.get("inherited_fields") for item in records if item["record_kind"] == "CONTEXT_VARIANT_CANDIDATE"):
        problems.append("candidate_inheritance_contract_missing")
    required_inherited_fields = {
        "source_tier", "authority_jurisdictions", "effective_dates",
        "pinpoint_citations", "citation_status", "legal_authority", "authority_map",
    }
    if any(required_inherited_fields - set(item.get("inherited_fields") or []) for item in records if item["record_kind"] == "CONTEXT_VARIANT_CANDIDATE"):
        problems.append("candidate_missing_source_authority_inheritance")
    required_source_fields = {
        "source_id", "source_title", "source_url", "source_tier", "authority_status",
        "jurisdiction", "contract_type", "effective_date", "effective_date_status",
        "pinpoint_citation", "retrieval_date", "citation_status", "license_status",
        "transferability", "can_support_legal_conclusion", "missing_metadata",
    }
    for source in sources["sources"]:
        if required_source_fields - set(source):
            problems.append(f"source_metadata_fields_missing:{source.get('source_id')}")
        if source.get("citation_status") == "VERIFIED_PINPOINT" and not str(source.get("pinpoint_citation") or "").strip():
            problems.append(f"verified_source_without_pinpoint:{source.get('source_id')}")
        if source.get("can_support_legal_conclusion"):
            jurisdiction = str(source.get("jurisdiction") or "").strip().upper()
            effective_status = str(source.get("effective_date_status") or "").strip().upper()
            if (
                not source.get("pinpoint_citation")
                or source.get("citation_status") != "VERIFIED_PINPOINT"
                or source.get("source_tier") != "A"
                or not str(source.get("retrieval_date") or "").strip()
                or jurisdiction in {
                    "", "UNSPECIFIED", "NON_JURISDICTIONAL_PRACTICE",
                    "NON_JURISDICTIONAL_DRAFTING_GUIDANCE",
                    "NOT_APPLICABLE_NONLEGAL_GUIDANCE",
                }
                or effective_status not in {"VERIFIED", "VERIFIED_FOR_RELEVANT_PERIOD", "NOT_APPLICABLE"}
            ):
                problems.append(f"unsupported_authority_claim:{source.get('source_id')}")
    if manifest["source_count"] != len(sources.get("sources", [])):
        problems.append("manifest_source_count_mismatch")
    if manifest.get("authority_map_hash") != _git_blob_sha(AUTHORITY_MAP_PATH.read_bytes()):
        problems.append("manifest_authority_map_hash_mismatch")
    if manifest.get("authority_catalog_hash") != _git_blob_sha(AUTHORITY_CATALOG_PATH.read_bytes()):
        problems.append("manifest_authority_catalog_hash_mismatch")
    if manifest.get("authority_catalog_count") != len(authority_catalog_doc.get("authorities", [])):
        problems.append("manifest_authority_catalog_count_mismatch")
    if manifest.get("mapped_clause_count") != len(authority_map_doc.get("clauses", [])):
        problems.append("manifest_mapped_clause_count_mismatch")
    if sources.get("source_count") != len(sources.get("sources", [])):
        problems.append("source_registry_source_count_mismatch")
    expected_base_count = len(_base_inputs(playbook))
    if manifest["base_rule_count"] != expected_base_count:
        problems.append(f"base_rule_count_does_not_match_playbook:{manifest['base_rule_count']}:{expected_base_count}")
    if manifest["candidate_profile_count"] != len(CONTRACT_PROFILES):
        problems.append("candidate_profile_count_mismatch")
    if manifest["candidate_rule_count"] != expected_base_count * len(CONTRACT_PROFILES):
        problems.append("candidate_count_not_derived_from_base_rules_and_profiles")
    if manifest["candidate_rule_count"] < 1000:
        problems.append(f"candidate_registry_below_target:{manifest['candidate_rule_count']}")
    verified_pinpoint_sources = [
        source for source in sources.get("sources", [])
        if source.get("citation_status") == "VERIFIED_PINPOINT"
        and str(source.get("pinpoint_citation") or "").strip()
        and str(source.get("retrieval_date") or "").strip()
    ]
    mislabeled_verified_sources = [
        source.get("source_id")
        for source in sources.get("sources", [])
        if source.get("citation_status") == "VERIFIED_PINPOINT"
        and (
            not str(source.get("pinpoint_citation") or "").strip()
            or not str(source.get("retrieval_date") or "").strip()
        )
    ]
    if mislabeled_verified_sources:
        problems.append(f"verified_citation_missing_pinpoint:{mislabeled_verified_sources}")
    verified_count = len(verified_pinpoint_sources)
    if manifest["verified_pinpoint_source_count"] != verified_count:
        problems.append("manifest_verified_pinpoint_count_mismatch")
    if sources.get("verified_pinpoint_source_count") != verified_count:
        problems.append("source_registry_verified_pinpoint_count_mismatch")
    expected_source_status = (
        "INCOMPLETE_SOURCE_CITATIONS" if verified_count == 0
        else "ALL_PINPOINT_CITATIONS_VERIFIED" if verified_count == len(sources.get("sources", []))
        else "PARTIALLY_VERIFIED_SOURCE_CITATIONS"
    )
    if sources.get("status") != expected_source_status:
        problems.append("source_registry_status_mismatch")

    base_rules = [item for item in records if item.get("record_kind") == "BASE_RULE"]
    if manifest.get("rule_authority_map_record_count") != len(base_rules):
        problems.append("manifest_rule_authority_map_record_count_mismatch")
    authority_fields = (
        "authority_id", "title", "citation", "source_type", "url", "pinpoint",
        "jurisdiction", "source_tier", "authority_status", "effective_date",
        "effective_date_status", "retrieval_date", "verification_status",
        "currentness_status", "scope_limit",
    )
    for item in base_rules:
        category = item.get("clause_type")
        expected_entry = authority_by_clause.get(str(category or ""))
        expected_ids = list(expected_entry.get("authority_ids") or []) if expected_entry else []
        expected_sources = [
            {key: authority_catalog_by_id[authority_id].get(key) for key in authority_fields}
            for authority_id in expected_ids
            if authority_id in authority_catalog_by_id
        ]
        expected_map = {
            "clause_type": expected_entry.get("clause_type") if expected_entry else None,
            "authority_ids": expected_ids,
            "authority_sources": expected_sources,
            "authority_coverage_status": expected_entry.get("authority_coverage_status") if expected_entry else "RULE_FAMILY_SPECIFIC_AUTHORITY_REVIEW_REQUIRED",
            "scope_note": expected_entry.get("scope_note") if expected_entry else "Cross-clause, document-level, and regex rules require authority mapping based on their actual trigger and contract facts.",
            "jurisdiction_policy": expected_entry.get("jurisdiction_policy") if expected_entry else "GOVERNING_LAW_AND_RULE_CONTEXT_REQUIRED",
            "review_status": expected_entry.get("review_status") if expected_entry else "RESEARCH_SEED_NOT_LEGALLY_APPROVED",
        }
        if item.get("authority_map") != expected_map:
            problems.append(f"rule_authority_map_mismatch:{item.get('rule_id')}")
        if item.get("legal_conclusion_allowed") is not False:
            problems.append(f"rule_legal_conclusion_not_disabled:{item.get('rule_id')}")
    by_family: dict[str, dict[str, int]] = {}
    complete_exception_suite_count = 0
    for item in base_rules:
        cases = item.get("regression_cases") or {}
        complete = all(cases.get(key) for key in ("positive", "negative", "edge"))
        complete_exception_suite_count += int(complete)
        family = str(item.get("rule_family") or "UNKNOWN")
        counts = by_family.setdefault(family, {"rules": 0, "complete_exception_suites": 0})
        counts["rules"] += 1
        counts["complete_exception_suites"] += int(complete)

    source_and_jurisdiction_coverage = {
        "rules_with_linked_sources": sum(bool(item.get("source_ids")) for item in base_rules),
        "rules_without_linked_sources": sum(not bool(item.get("source_ids")) for item in base_rules),
        "rules_with_verified_pinpoint_citations": sum(item.get("citation_status") == "VERIFIED_PINPOINT" for item in base_rules),
        "rules_with_incomplete_or_missing_citations": sum(item.get("citation_status") != "VERIFIED_PINPOINT" for item in base_rules),
        "rules_with_verified_jurisdiction": sum(item.get("jurisdiction_status") == "VERIFIED" for item in base_rules),
        "rules_with_declared_but_unverified_jurisdiction": sum(item.get("jurisdiction_status") == "DECLARED_NOT_VERIFIED" for item in base_rules),
        "rules_with_unresolved_jurisdiction": sum(item.get("jurisdiction_status") == "UNRESOLVED" for item in base_rules),
    }

    release_blockers: list[str] = []
    if manifest.get("policy_status") != "APPROVED":
        release_blockers.append("playbook_policy_not_approved")
    if manifest.get("production_approved_rule_count", 0) == 0:
        release_blockers.append("no_individually_approved_rules")
    if manifest.get("verified_pinpoint_source_count", 0) == 0:
        release_blockers.append("no_verified_pinpoint_citations")
    adjudication_template = ROOT / "data" / "risk" / "gold" / "risk_finding_adjudication_template.csv"
    has_adjudicated_rows = False
    if adjudication_template.exists():
        import csv
        with adjudication_template.open(encoding="utf-8-sig", newline="") as handle:
            has_adjudicated_rows = any(
                str(row.get("adjudication_status") or "").strip().upper() == "ADJUDICATED"
                for row in csv.DictReader(handle)
            )
    if not has_adjudicated_rows:
        release_blockers.append("no_project_specific_adjudicated_risk_gold_set")
    calibration_artifact = ROOT / "data" / "risk" / "calibration" / "confidence_calibration.json"
    if not calibration_artifact.exists():
        release_blockers.append("no_validated_confidence_calibration_artifact")

    report = {
        "status": "PASS" if not problems else "FAIL",
        "registry_integrity_status": "PASS" if not problems else "FAIL",
        "release_readiness": "BLOCKED" if release_blockers else "REQUIRES_FINAL_LEGAL_RELEASE_REVIEW",
        "production_release_allowed": False if release_blockers else manifest.get("policy_status") == "APPROVED",
        "release_blockers": release_blockers,
        "base_rule_count": manifest["base_rule_count"],
        "authority_mapping_coverage": {
            "taxonomy_clause_count": len(authority_map_doc.get("clauses", [])),
            "authority_catalog_count": len(authority_catalog_doc.get("authorities", [])),
            "base_rules_with_authority_refs": sum(bool(item.get("authority_map", {}).get("authority_ids")) for item in base_rules),
            "base_rules_without_authority_refs": sum(not bool(item.get("authority_map", {}).get("authority_ids")) for item in base_rules),
            "base_rules_with_full_authority_metadata": sum(
                bool(item.get("authority_map", {}).get("authority_ids"))
                and len(item.get("authority_map", {}).get("authority_sources") or []) == len(item.get("authority_map", {}).get("authority_ids") or [])
                for item in base_rules
            ),
            "categories_without_universal_primary_authority": sorted(
                entry["clause_type"] for entry in authority_map_doc.get("clauses", []) if not entry.get("authority_ids")
            ),
        },
        "source_and_jurisdiction_coverage": source_and_jurisdiction_coverage,
        "rule_test_coverage": {
            "base_rules": len(base_rules),
            "complete_positive_negative_edge_suites": complete_exception_suite_count,
            "missing_complete_suites": len(base_rules) - complete_exception_suite_count,
            "by_rule_family": by_family,
        },
        "disabled_context_candidates": manifest["candidate_rule_count"],
        "total_rule_records": manifest["total_rule_records"],
        "source_count": manifest["source_count"],
        "verified_pinpoint_source_count": manifest["verified_pinpoint_source_count"],
        "production_approved_rule_count": manifest["production_approved_rule_count"],
        "policy_status": manifest["policy_status"],
        "problems": problems,
        "interpretation": "Registry integrity and governance checks only; not legal-risk accuracy.",
    }
    print(json.dumps(report, indent=2))
    return 0 if not problems else 1

if __name__ == "__main__":
    raise SystemExit(main())
