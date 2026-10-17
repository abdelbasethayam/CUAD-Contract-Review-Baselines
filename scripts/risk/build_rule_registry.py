#!/usr/bin/env python3
"""Build a reproducible, governed rule registry from the Phase 2 playbook.

The 16 contract-profile expansions are candidate applicability hypotheses, not
new approved legal rules. They are deliberately disabled until reviewed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK_PATH = ROOT / "data" / "risk" / "commercial_clause_risk_playbook.json"
REGISTRY_PATH = ROOT / "data" / "risk" / "rule_registry.jsonl"
SOURCE_REGISTRY_PATH = ROOT / "data" / "risk" / "source_registry.json"
MANIFEST_PATH = ROOT / "data" / "risk" / "rule_registry_manifest.json"
REGISTRY_VERSION = "0.1.0"
SCHEMA_VERSION = 1

CONTRACT_PROFILES = [
    {"id": "general_commercial", "label": "General commercial", "note": "General commercial agreements; applicability still requires review."},
    {"id": "saas_cloud", "label": "SaaS / cloud services", "note": "Cloud subscriptions, hosted software, and SaaS services."},
    {"id": "software_license", "label": "Software licence", "note": "Software licence and support agreements."},
    {"id": "technology_transfer", "label": "Technology transfer", "note": "Technology transfer, know-how, and IP commercialization."},
    {"id": "professional_services", "label": "Professional services", "note": "Consulting, agency, and professional services."},
    {"id": "goods_supply", "label": "Goods supply", "note": "Purchase, sale, and supply of goods."},
    {"id": "manufacturing", "label": "Manufacturing", "note": "Manufacturing, OEM, and production agreements."},
    {"id": "distribution_reseller", "label": "Distribution / reseller", "note": "Distribution, reseller, and channel arrangements."},
    {"id": "outsourcing_bpo", "label": "Outsourcing / BPO", "note": "Outsourcing and business-process services."},
    {"id": "data_processing_privacy", "label": "Data processing / privacy", "note": "Data processing and privacy-related agreements."},
    {"id": "marketing_services", "label": "Marketing services", "note": "Marketing, advertising, and media services."},
    {"id": "construction_projects", "label": "Construction / projects", "note": "Construction, engineering, and project delivery."},
    {"id": "nda_confidentiality", "label": "NDA / confidentiality", "note": "Confidentiality and non-disclosure agreements."},
    {"id": "employment_services", "label": "Employment / personnel", "note": "Employment, contractor, and personnel arrangements."},
    {"id": "ma_transaction", "label": "M&A transaction", "note": "Merger, acquisition, and transaction agreements."},
    {"id": "franchise", "label": "Franchise", "note": "Franchise and branded-network arrangements."},
]

SOURCE_OVERRIDES = {
    "P1": {
        "source_tier": "B",
        "authority_status": "NON_BINDING_PROFESSIONAL_PRACTICE",
        "jurisdiction": "NON_JURISDICTIONAL_PRACTICE",
        "contract_type": "commercial_general",
        "effective_date": None,
        "effective_date_status": "PUBLICATION_YEAR_MENTIONED_BUT_NOT_VERIFIED",
        "pinpoint_citation": None,
        "citation_status": "NEEDS_EXACT_REPORT_EDITION_AND_PINPOINT",
        "license_status": "VERIFY_BEFORE_REPUBLISHING",
        "transferability": "limited_by_analogy",
        "can_support_legal_conclusion": False,
        "missing_metadata": ["exact_report_title", "edition_or_publication_date_verification", "pinpoint_citation", "retrieval_date"],
        "metadata_note": "The legacy reference says Most Negotiated Terms (e.g. 2024) and links only to a general homepage; it is not a pinpoint citation."
    },
    "P2": {
        "source_tier": "B",
        "authority_status": "NON_BINDING_PROFESSIONAL_PRACTICE",
        "jurisdiction": "UNSPECIFIED",
        "contract_type": "commercial_general",
        "effective_date": None,
        "effective_date_status": "NOT_PROVIDED",
        "pinpoint_citation": None,
        "citation_status": "GENERIC_REFERENCE_NOT_PINPOINTED",
        "license_status": "LICENSE_REQUIRED",
        "transferability": "limited_by_analogy",
        "can_support_legal_conclusion": False,
        "missing_metadata": ["specific_publication", "source_url", "jurisdiction_or_practice_scope", "effective_date_or_edition", "pinpoint_citation", "retrieval_date"],
        "metadata_note": "The legacy reference combines Practical Law and similar notes rather than identifying one retrievable source."
    },
    "P3": {
        "source_tier": "D",
        "authority_status": "INTERNAL_MARKET_PRACTICE_HYPOTHESIS",
        "jurisdiction": "NOT_APPLICABLE_NONLEGAL_GUIDANCE",
        "contract_type": "commercial_saas",
        "effective_date": None,
        "effective_date_status": "NOT_APPLICABLE_UNTIL_A_SPECIFIC_MARKET_SOURCE_IS_IDENTIFIED",
        "pinpoint_citation": None,
        "citation_status": "UNSOURCED_MARKET_PRACTICE_HYPOTHESIS",
        "license_status": "VERIFY_SOURCE",
        "transferability": "limited_by_analogy",
        "can_support_legal_conclusion": False,
        "missing_metadata": ["verifiable_source", "source_url", "pinpoint_citation", "retrieval_date"],
        "metadata_note": "A general market-practice statement is not a primary authority and must not be represented as law."
    },
    "P4": {
        "source_tier": "B",
        "authority_status": "NON_BINDING_DRAFTING_TREATISE",
        "jurisdiction": "NON_JURISDICTIONAL_DRAFTING_GUIDANCE",
        "contract_type": "commercial_general",
        "effective_date": None,
        "effective_date_status": "EDITION_NOT_SPECIFIED",
        "pinpoint_citation": None,
        "citation_status": "NEEDS_EDITION_AND_PINPOINT",
        "license_status": "LICENSE_REQUIRED",
        "transferability": "limited_by_analogy",
        "can_support_legal_conclusion": False,
        "missing_metadata": ["edition", "publisher_record_or_url", "pinpoint_citation", "retrieval_date"],
        "metadata_note": "Drafting guidance only; do not infer jurisdiction-specific legal effect from the treatise."
    },
    "P5": {
        "source_tier": "B",
        "authority_status": "NON_BINDING_DRAFTING_TREATISE",
        "jurisdiction": "NON_JURISDICTIONAL_DRAFTING_GUIDANCE",
        "contract_type": "commercial_general",
        "effective_date": None,
        "effective_date_status": "EDITION_NOT_SPECIFIED",
        "pinpoint_citation": None,
        "citation_status": "NEEDS_EDITION_AND_PINPOINT",
        "license_status": "LICENSE_REQUIRED",
        "transferability": "limited_by_analogy",
        "can_support_legal_conclusion": False,
        "missing_metadata": ["edition", "publisher_record_or_url", "pinpoint_citation", "retrieval_date"],
        "metadata_note": "Drafting guidance only; the legacy entry also refers to related practice materials without identifying them."
    },
    "P6": {
        "source_tier": "B",
        "authority_status": "NON_BINDING_RISK_MANAGEMENT_GUIDANCE",
        "jurisdiction": "NON_JURISDICTIONAL_RISK_MANAGEMENT_GUIDANCE",
        "contract_type": "commercial_general",
        "effective_date": None,
        "effective_date_status": "EDITION_NOT_SPECIFIED",
        "pinpoint_citation": None,
        "citation_status": "NEEDS_EDITION_AND_PINPOINT",
        "license_status": "VERIFY_BEFORE_REPUBLISHING",
        "transferability": "limited_by_analogy",
        "can_support_legal_conclusion": False,
        "missing_metadata": ["edition_or_publication_date", "publisher_record_or_url", "pinpoint_citation", "retrieval_date"],
        "metadata_note": "Risk-management guidance supports review design, not binding-law conclusions."
    },
    "P7": {
        "source_tier": "D",
        "authority_status": "UNSOURCED_JURISDICTION_SENSITIVE_HYPOTHESIS",
        "jurisdiction": "UNSPECIFIED",
        "contract_type": "jurisdiction_dependent",
        "effective_date": None,
        "effective_date_status": "REQUIRES_JURISDICTION_SPECIFIC_AUTHORITY",
        "pinpoint_citation": None,
        "citation_status": "MUST_REPLACE_WITH_JURISDICTION_SPECIFIC_PRIMARY_AUTHORITY",
        "license_status": "VERIFY_SOURCE",
        "transferability": "not_transferable_without_jurisdiction_review",
        "can_support_legal_conclusion": False,
        "missing_metadata": ["target_jurisdiction", "primary_authority", "source_url", "effective_date", "pinpoint_citation", "retrieval_date"],
        "metadata_note": "Penalty doctrine and limits on excluding liability vary by governing law; this generic note cannot support a legal conclusion."
    },
}

JURISDICTION_SENSITIVE_TERMS = (
    "non-compete", "noncompete", "no-solicit", "nonsolicit",
    "price restriction", "resale price", "competition restriction",
    "liquidated damages", "penalty", "covenant not to sue",
    "non-disparagement", "governing law", "enforceab", "public policy",
)

def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def _git_blob_sha(data: bytes) -> str:
    import hashlib
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\\0" + data).hexdigest()

def _source_registry(playbook: dict[str, Any]) -> dict[str, Any]:
    result = []
    for source_id, raw in sorted((playbook.get("sources") or {}).items()):
        override = SOURCE_OVERRIDES.get(source_id, {})
        citation = str(raw.get("citation") or raw.get("source_title") or source_id).strip()
        result.append({
            "schema_version": SCHEMA_VERSION,
            "source_id": str(source_id),
            "source_title": citation,
            "citation": citation,
            "source_url": raw.get("url"),
            "source_tier": override.get("source_tier", "D"),
            "authority_status": override.get("authority_status", "UNVERIFIED_LEGACY_SOURCE"),
            "jurisdiction": override.get("jurisdiction", "UNSPECIFIED"),
            "contract_type": override.get("contract_type", "unspecified"),
            "effective_date": override.get("effective_date"),
            "effective_date_status": override.get("effective_date_status", "NOT_PROVIDED"),
            "pinpoint_citation": override.get("pinpoint_citation"),
            "retrieval_date": None,
            "citation_status": override.get("citation_status", "UNVERIFIED"),
            "license_status": override.get("license_status", "VERIFY_SOURCE"),
            "transferability": override.get("transferability", "limited_by_analogy"),
            "can_support_legal_conclusion": bool(override.get("can_support_legal_conclusion", False)),
            "missing_metadata": override.get("missing_metadata", ["source_authority_review"]),
            "metadata_note": override.get("metadata_note", "Legacy source metadata requires review."),
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "registry_version": REGISTRY_VERSION,
        "source_playbook_hash": str(playbook.get("_source_blob_sha") or ""),
        "status": "INCOMPLETE_SOURCE_CITATIONS",
        "source_count": len(result),
        "verified_pinpoint_source_count": sum(1 for item in result if item["citation_status"] == "VERIFIED_PINPOINT"),
        "sources": result,
    }

def _base_inputs(playbook: dict[str, Any]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for category, payload in sorted((playbook.get("clause_types") or {}).items()):
        for item in payload.get("checklist") or []:
            rule_id = str(item.get("id") or "").strip()
            if not rule_id:
                continue
            rules.append({
                "base_rule_id": rule_id,
                "rule_family": "CLAUSE_CHECK",
                "clause_type": str(category),
                "title": str(item.get("question") or rule_id),
                "risk_domain": str(item.get("risk_domain") or "Commercial Risk"),
                "risk_subdomain": item.get("risk_subdomain"),
                "risk_type": item.get("risk_type"),
                "perspective": str(item.get("perspective") or playbook.get("perspective") or "customer_buyer"),
                "contract_type_scope": ["unspecified_commercial_contract"],
                "jurisdiction_scope": item.get("jurisdiction_scope") or ["UNSPECIFIED"],
                "decision_logic": {
                    "question": str(item.get("question") or ""),
                    "trigger_condition": str(item.get("flag_if") or ""),
                    "counterconditions": item.get("do_not_flag_if") or [],
                    "dependencies": item.get("dependencies") or [],
                    "applies_when": item.get("applies_when") or [],
                    "pattern": None,
                    "exclude_patterns": [],
                },
                "evidence_contract": {
                    "required_evidence": item.get("required_evidence") or ["Exact contiguous quote from the uploaded contract supporting the condition."],
                    "evidence_location": str(item.get("evidence_location") or "clause"),
                    "exact_quote_required": True,
                    "must_be_from_uploaded_contract": True,
                    "source_citation_is_not_contract_evidence": True,
                    "affected_clause_ids_required": False,
                },
                "source_ids": sorted(set(str(x) for x in (item.get("sources") or []))),
                "rationale": item.get("rationale") or "Review trigger inherited from the unapproved baseline playbook; not a legal conclusion.",
                "positive_examples": item.get("positive_examples") or [],
                "negative_examples": item.get("negative_examples") or [],
                "regression_cases": {"positive": [], "negative": [], "edge": []},
            })
    for item in playbook.get("cross_clause_checks") or []:
        rule_id = str(item.get("id") or "").strip()
        if not rule_id:
            continue
        rules.append({
            "base_rule_id": rule_id,
            "rule_family": "CROSS_CLAUSE_CHECK",
            "clause_type": None,
            "title": str(item.get("question") or rule_id),
            "risk_domain": str(item.get("risk_domain") or "Commercial Risk"),
            "risk_subdomain": item.get("risk_subdomain"),
            "risk_type": item.get("risk_type"),
            "perspective": str(playbook.get("perspective") or "customer_buyer"),
            "contract_type_scope": ["unspecified_commercial_contract"],
            "jurisdiction_scope": item.get("jurisdiction_scope") or ["UNSPECIFIED"],
            "decision_logic": {
                "question": str(item.get("question") or ""),
                "trigger_condition": str(item.get("flag_if") or ""),
                "counterconditions": item.get("do_not_flag_if") or [],
                "dependencies": item.get("dependencies") or [],
                "applies_when": item.get("pair") or [],
                "pattern": None,
                "exclude_patterns": [],
            },
            "evidence_contract": {
                "required_evidence": ["Exact quote from every affected contract clause needed to substantiate the interaction."],
                "evidence_location": "same_contract",
                "exact_quote_required": True,
                "must_be_from_uploaded_contract": True,
                "source_citation_is_not_contract_evidence": True,
                "affected_clause_ids_required": True,
            },
            "source_ids": sorted(set(str(x) for x in (item.get("sources") or []))),
            "rationale": "Cross-clause candidate check; semantic conflict must be independently established.",
            "positive_examples": [],
            "negative_examples": [],
            "regression_cases": {"positive": [], "negative": [], "edge": []},
        })
    for item in playbook.get("document_level_checks") or []:
        rule_id = str(item.get("id") or "").strip()
        if not rule_id:
            continue
        rules.append({
            "base_rule_id": rule_id,
            "rule_family": "DOCUMENT_CHECK",
            "clause_type": None,
            "title": str(item.get("question") or rule_id),
            "risk_domain": str(item.get("risk_domain") or "Commercial Risk"),
            "risk_subdomain": item.get("risk_subdomain"),
            "risk_type": item.get("risk_type"),
            "perspective": str(playbook.get("perspective") or "customer_buyer"),
            "contract_type_scope": ["unspecified_commercial_contract"],
            "jurisdiction_scope": item.get("jurisdiction_scope") or ["UNSPECIFIED"],
            "decision_logic": {
                "question": str(item.get("question") or ""),
                "trigger_condition": str(item.get("flag_if") or ""),
                "counterconditions": [],
                "dependencies": item.get("dependencies") or [],
                "applies_when": [],
                "pattern": None,
                "exclude_patterns": [],
            },
            "evidence_contract": {
                "required_evidence": ["Exact contract text identifying the missing or inconsistent document-level dependency."],
                "evidence_location": "document_package",
                "exact_quote_required": True,
                "must_be_from_uploaded_contract": True,
                "source_citation_is_not_contract_evidence": True,
                "affected_clause_ids_required": True,
            },
            "source_ids": sorted(set(str(x) for x in (item.get("sources") or []))),
            "rationale": "Document-package review trigger; absence from an incomplete upload is not proof of absence from the signed agreement.",
            "positive_examples": [],
            "negative_examples": [],
            "regression_cases": {"positive": [], "negative": [], "edge": []},
        })
    for item in playbook.get("deterministic_rules") or []:
        rule_id = str(item.get("id") or "").strip()
        if not rule_id:
            continue
        rules.append({
            "base_rule_id": rule_id,
            "rule_family": "DETERMINISTIC_REGEX",
            "clause_type": None,
            "title": str(item.get("risk_type") or item.get("question") or rule_id),
            "risk_domain": str(item.get("risk_domain") or "Commercial Risk"),
            "risk_subdomain": item.get("risk_subdomain"),
            "risk_type": item.get("risk_type"),
            "perspective": str(playbook.get("perspective") or "customer_buyer"),
            "contract_type_scope": ["unspecified_commercial_contract"],
            "jurisdiction_scope": item.get("jurisdiction_scope") or ["UNSPECIFIED"],
            "decision_logic": {
                "question": str(item.get("question") or ""),
                "trigger_condition": "The configured regular expression matches uploaded contract text.",
                "counterconditions": item.get("exclude_patterns") or [],
                "dependencies": [],
                "applies_when": [],
                "pattern": str(item.get("pattern") or ""),
                "exclude_patterns": item.get("exclude_patterns") or [],
            },
            "evidence_contract": {
                "required_evidence": ["Exact matched substring from the uploaded contract."],
                "evidence_location": "clause",
                "exact_quote_required": True,
                "must_be_from_uploaded_contract": True,
                "source_citation_is_not_contract_evidence": True,
                "affected_clause_ids_required": False,
            },
            "source_ids": sorted(set(str(x) for x in (item.get("sources") or []))),
            "rationale": str(item.get("explanation") or "Textual trigger only; requires reviewer interpretation."),
            "positive_examples": [],
            "negative_examples": [],
            "regression_cases": {"positive": [], "negative": [], "edge": []},
        })
    return rules

def _is_jurisdiction_sensitive(rule: dict[str, Any]) -> bool:
    blob = " ".join([
        str(rule.get("title") or ""),
        str(rule.get("risk_domain") or ""),
        str(rule.get("risk_type") or ""),
        str(rule.get("decision_logic", {}).get("question") or ""),
        str(rule.get("decision_logic", {}).get("trigger_condition") or ""),
    ]).lower()
    return any(term in blob for term in JURISDICTION_SENSITIVE_TERMS)

def _record(rule: dict[str, Any], playbook: dict[str, Any], *, candidate_profile: dict[str, str] | None = None) -> dict[str, Any]:
    family = rule["rule_family"]
    category = rule.get("clause_type")
    registry_key = f"{family}::{category}::{rule['base_rule_id']}" if category else f"{family}::{rule['base_rule_id']}"
    candidate = candidate_profile is not None
    profile_id = candidate_profile["id"] if candidate_profile else "commercial_general"
    record_id = f"CANDIDATE::{registry_key}::{profile_id}" if candidate else f"BASE::{registry_key}"
    contract_scope = [profile_id] if candidate else list(rule.get("contract_type_scope") or ["unspecified_commercial_contract"])
    decision_logic = dict(rule["decision_logic"])
    if candidate:
        decision_logic["applicability_hypothesis"] = (
            "Proposed contract-type specialization only. Do not assume this check applies to this profile; "
            "a reviewer must verify the contract context and approve applicability."
        )
    source_ids = list(rule.get("source_ids") or [])
    source_status = "NO_SOURCE_LINKED" if not source_ids else "INCOMPLETE_SOURCE_CITATION"
    jurisdiction_scope = list(rule.get("jurisdiction_scope") or ["UNSPECIFIED"])
    jurisdiction_status = "UNRESOLVED" if any(str(x).upper() == "UNSPECIFIED" for x in jurisdiction_scope) else "DECLARED_NOT_VERIFIED"
    return {
        "schema_version": SCHEMA_VERSION,
        "rule_id": record_id,
        "base_rule_key": registry_key,
        "base_rule_id": rule["base_rule_id"],
        "record_kind": "CONTEXT_VARIANT_CANDIDATE" if candidate else "BASE_RULE",
        "rule_family": family,
        "title": rule["title"],
        "clause_type": category,
        "risk_domain": rule.get("risk_domain") or "Commercial Risk",
        "risk_subdomain": rule.get("risk_subdomain"),
        "risk_type": rule.get("risk_type"),
        "perspective": rule.get("perspective") or "customer_buyer",
        "contract_type_profile": profile_id,
        "contract_type_scope": contract_scope,
        "applicability_status": "NEEDS_HUMAN_REVIEW" if candidate else "BASELINE_APPLICABILITY_NOT_ADJUDICATED",
        "jurisdiction_scope": jurisdiction_scope,
        "jurisdiction_status": jurisdiction_status,
        "jurisdiction_review_required": bool(_is_jurisdiction_sensitive(rule) or jurisdiction_status == "UNRESOLVED"),
        "decision_logic": decision_logic,
        "evidence_contract": rule["evidence_contract"],
        "source_ids": source_ids,
        "source_status": source_status,
        "rationale": rule["rationale"],
        "severity_rationale": {
            "status": "NOT_USED",
            "reason": "Ordinal severity labels are not used. This rule does not estimate legal impact, loss probability, or business materiality."
        },
        "confidence_policy": {
            "target": "PREDICTION_CORRECTNESS",
            "raw_support_score_status": "HEURISTIC_UNCALIBRATED",
            "probability_allowed_only_when": "A versioned calibration artifact for the exact playbook and support-score version passes a contract-disjoint locked test.",
            "model_self_reported_confidence_allowed": False,
        },
        "regression_cases": rule.get("regression_cases") or {"positive": [], "negative": [], "edge": []},
        "validation_status": "DRAFT_UNVALIDATED",
        "approval_status": str(playbook.get("approval_status") or "UNAPPROVED"),
        "execution_status": "DISABLED_UNVALIDATED_CANDIDATE" if candidate else "PILOT_REVIEW_ONLY",
        "execution_eligible": not candidate,
        "legal_conclusion_allowed": False,
        "source_playbook_hash": str(playbook.get("_source_blob_sha") or ""),
        "candidate_note": candidate_profile.get("note") if candidate else None,
    }

def _candidate_record(rule: dict[str, Any], playbook: dict[str, Any], profile: dict[str, str]) -> dict[str, Any]:
    category = rule.get("clause_type")
    family = rule["rule_family"]
    base_key = f"{family}::{category}::{rule['base_rule_id']}" if category else f"{family}::{rule['base_rule_id']}"
    return {
        "schema_version": SCHEMA_VERSION,
        "rule_id": f"CANDIDATE::{base_key}::{profile['id']}",
        "base_rule_key": base_key,
        "base_rule_id": rule["base_rule_id"],
        "record_kind": "CONTEXT_VARIANT_CANDIDATE",
        "contract_type_profile": profile["id"],
        "applicability_status": "NEEDS_HUMAN_REVIEW",
        "inherits_from_base_rule": f"BASE::{base_key}",
        "inherited_fields": [
            "rule_family", "title", "risk_domain", "risk_subdomain", "risk_type",
            "perspective", "jurisdiction_scope", "decision_logic", "evidence_contract",
            "source_ids", "source_status", "rationale", "confidence_policy",
        ],
        "candidate_note": profile["note"],
        "validation_status": "DRAFT_UNVALIDATED",
        "approval_status": str(playbook.get("approval_status") or "UNAPPROVED"),
        "execution_status": "DISABLED_UNVALIDATED_CANDIDATE",
        "execution_eligible": False,
        "legal_conclusion_allowed": False,
        "source_playbook_hash": str(playbook.get("_source_blob_sha") or ""),
    }

def build_artifacts(playbook: dict[str, Any]) -> tuple[str, str, str]:
    # Git blob SHA is computed over the exact committed file bytes, so changing
    # any rule invalidates the generated registry even if a declared field is stale.
    playbook = dict(playbook)
    playbook["_source_blob_sha"] = _git_blob_sha(PLAYBOOK_PATH.read_bytes())
    base_rules = _base_inputs(playbook)
    base_records = [_record(rule, playbook) for rule in base_rules]
    candidate_records = [
        _candidate_record(rule, playbook, profile)
        for rule in base_rules
        for profile in CONTRACT_PROFILES
    ]
    records = base_records + candidate_records
    source_registry = _source_registry(playbook)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "registry_version": REGISTRY_VERSION,
        "source_playbook_hash": str(playbook.get("_source_blob_sha") or ""),
        "policy_status": str(playbook.get("approval_status") or "UNAPPROVED"),
        "execution_mode": "PILOT_REVIEW_ONLY",
        "base_rule_count": len(base_records),
        "candidate_rule_count": len(candidate_records),
        "total_rule_records": len(records),
        "candidate_profile_count": len(CONTRACT_PROFILES),
        "candidate_profiles": CONTRACT_PROFILES,
        "source_count": len(source_registry["sources"]),
        "verified_pinpoint_source_count": source_registry["verified_pinpoint_source_count"],
        "production_approved_rule_count": sum(1 for item in base_records if item["validation_status"] == "APPROVED"),
        "interpretation": (
            "The registry contains baseline rule records and disabled context-specific candidates. "
            "Candidate records are not new approved legal rules. Current baseline rules are review-only "
            "because the policy is unapproved and source citations are incomplete."
        ),
    }
    registry_text = "".join(_canonical(item) + "\n" for item in records)
    source_text = json.dumps(source_registry, ensure_ascii=False, indent=2) + "\n"
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    return registry_text, source_text, manifest_text

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if committed registry artifacts are stale.")
    parser.add_argument("--write", action="store_true", help="Regenerate registry artifacts.")
    args = parser.parse_args()
    if args.check == args.write:
        parser.error("Choose exactly one of --check or --write.")
    playbook = json.loads(PLAYBOOK_PATH.read_text(encoding="utf-8"))
    expected = build_artifacts(playbook)
    paths = [REGISTRY_PATH, SOURCE_REGISTRY_PATH, MANIFEST_PATH]
    if args.write:
        for path, content in zip(paths, expected):
            path.write_text(content, encoding="utf-8")
            print(f"Wrote {path.relative_to(ROOT)}")
        return 0
    mismatches = []
    for path, content in zip(paths, expected):
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            mismatches.append(str(path.relative_to(ROOT)))
    if mismatches:
        print("Rule registry is stale or missing: " + ", ".join(mismatches), file=sys.stderr)
        print("Run: python scripts/risk/build_rule_registry.py --write", file=sys.stderr)
        return 1
    print(f"Rule registry reproducible: {len(_base_inputs(playbook))} base rules, {len(_base_inputs(playbook)) * len(CONTRACT_PROFILES)} disabled candidates.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
