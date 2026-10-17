#!/usr/bin/env python3
"""Validate registry reproducibility, source completeness, and execution gates."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts" / "risk") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "risk"))
from build_rule_registry import (
    MANIFEST_PATH,
    REGISTRY_PATH,
    SOURCE_REGISTRY_PATH,
    PLAYBOOK_PATH,
    build_artifacts,
)

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
    ids = [item["rule_id"] for item in records]
    if len(ids) != len(set(ids)):
        problems.append("duplicate_rule_ids")
    if len(records) != manifest["total_rule_records"]:
        problems.append("manifest_record_count_mismatch")
    if sum(item["record_kind"] == "BASE_RULE" for item in records) != manifest["base_rule_count"]:
        problems.append("base_rule_count_mismatch")
    if sum(item["record_kind"] == "CONTEXT_VARIANT_CANDIDATE" for item in records) != manifest["candidate_rule_count"]:
        problems.append("candidate_rule_count_mismatch")
    if manifest["production_approved_rule_count"] != 0:
        problems.append("unexpected_approved_rules_without_review")
    if any(item["execution_eligible"] for item in records if item["record_kind"] == "CONTEXT_VARIANT_CANDIDATE"):
        problems.append("candidate_rule_enabled_for_execution")
    if any(item["validation_status"] != "DRAFT_UNVALIDATED" for item in records):
        problems.append("unreviewed_rule_misrepresented_as_validated")
    source_ids = {item["source_id"] for item in sources["sources"]}
    if any(set(item["source_ids"]) - source_ids for item in records):
        problems.append("dangling_source_reference")
    required_source_fields = {
        "source_id", "source_title", "source_url", "source_tier", "authority_status",
        "jurisdiction", "contract_type", "effective_date", "effective_date_status",
        "pinpoint_citation", "retrieval_date", "citation_status", "license_status",
        "transferability", "can_support_legal_conclusion", "missing_metadata",
    }
    for source in sources["sources"]:
        if required_source_fields - set(source):
            problems.append(f"source_metadata_fields_missing:{source.get('source_id')}")
        if source.get("can_support_legal_conclusion") and (
            not source.get("pinpoint_citation") or source.get("citation_status") != "VERIFIED_PINPOINT"
        ):
            problems.append(f"unsupported_authority_claim:{source.get('source_id')}")
    if manifest["base_rule_count"] != 121:
        problems.append(f"unexpected_base_rule_count:{manifest['base_rule_count']}")
    if manifest["candidate_rule_count"] < 1000:
        problems.append(f"candidate_registry_below_target:{manifest['candidate_rule_count']}")
    if manifest["verified_pinpoint_source_count"] != 0:
        problems.append("legacy_sources_must_not_be_marked_verified_without_review")

    report = {
        "status": "PASS" if not problems else "FAIL",
        "base_rule_count": manifest["base_rule_count"],
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
