#!/usr/bin/env python3
"""Build a reproducible human-review queue for the actual Phase 2 base rules.

This queue is a worklist, not a claim that rules are legally correct. It keeps
missing cases, source pinpoints, jurisdiction verification, and adjudication
work visible instead of filling gaps with synthetic legal conclusions.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts" / "risk") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "risk"))

from build_rule_registry import (  # noqa: E402
    PLAYBOOK_PATH,
    _base_inputs,
    _git_blob_sha,
    _source_registry,
)

OUTPUT_PATH = ROOT / "data" / "risk" / "rule_review_queue.csv"
AUTHORITY_MAP_PATH = ROOT / "data" / "risk" / "clause_authority_map.json"
AUTHORITY_CATALOG_PATH = ROOT / "data" / "risk" / "authority_catalog.json"
FIELDNAMES = [
    "queue_schema_version",
    "source_playbook_hash",
    "rule_id",
    "base_rule_key",
    "base_rule_id",
    "rule_family",
    "clause_type",
    "title",
    "risk_domain",
    "risk_type",
    "perspective",
    "contract_type_scope_json",
    "jurisdiction_scope_json",
    "jurisdiction_status",
    "decision_logic_json",
    "evidence_contract_json",
    "source_ids_json",
    "source_citation_status",
    "authority_map_clause_type",
    "authority_map_ids_json",
    "authority_sources_json",
    "authority_coverage_status",
    "authority_scope_note",
    "authority_jurisdiction_policy",
    "authority_map_review_status",
    "source_metadata_json",
    "validation_status",
    "approval_status",
    "positive_case_json",
    "negative_case_json",
    "edge_case_json",
    "case_suite_status",
    "reviewer_1_id",
    "reviewer_1_decision",
    "reviewer_1_rationale",
    "reviewer_1_reviewed_at",
    "reviewer_2_id",
    "reviewer_2_decision",
    "reviewer_2_rationale",
    "reviewer_2_reviewed_at",
    "adjudicator_id",
    "adjudication_reference",
    "adjudication_notes",
    "adjudicated_at",
    "approved_by",
    "approved_at",
    "approval_basis",
    "next_action",
]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _source_status(source_ids: list[str], source_by_id: dict[str, dict[str, Any]]) -> str:
    if not source_ids:
        return "NO_SOURCE_LINKED"
    if any(source_id not in source_by_id for source_id in source_ids):
        return "DANGLING_SOURCE_REFERENCE"
    if all(
        source_by_id[source_id].get("citation_status") == "VERIFIED_PINPOINT"
        and str(source_by_id[source_id].get("pinpoint_citation") or "").strip()
        and str(source_by_id[source_id].get("retrieval_date") or "").strip()
        for source_id in source_ids
    ):
        return "VERIFIED_PINPOINT"
    return "INCOMPLETE_SOURCE_CITATION"


def _reviewer_decision(governance: dict[str, Any], position: int) -> dict[str, Any]:
    decisions = governance.get("reviewer_decisions") or []
    if isinstance(decisions, list):
        valid = [item for item in decisions if isinstance(item, dict)]
        if len(valid) >= position:
            return valid[position - 1]
    reviewer_ids = governance.get("reviewer_ids") or []
    reviewer_id = reviewer_ids[position - 1] if isinstance(reviewer_ids, list) and len(reviewer_ids) >= position else ""
    return {"reviewer_id": reviewer_id}


def build_queue_text() -> tuple[str, int, int]:
    playbook = json.loads(PLAYBOOK_PATH.read_text(encoding="utf-8"))
    authority_map = json.loads(AUTHORITY_MAP_PATH.read_text(encoding="utf-8"))
    authority_catalog = json.loads(AUTHORITY_CATALOG_PATH.read_text(encoding="utf-8"))
    authority_by_id = {
        str(item["authority_id"]): item
        for item in authority_catalog.get("authorities", [])
        if item.get("authority_id")
    }
    authority_by_clause = {
        str(item["clause_type"]): item
        for item in authority_map.get("clauses", [])
        if item.get("clause_type")
    }
    playbook_hash = _git_blob_sha(PLAYBOOK_PATH.read_bytes())
    playbook["_source_blob_sha"] = playbook_hash
    source_registry = _source_registry(playbook)
    source_by_id = {
        str(source["source_id"]): source
        for source in source_registry["sources"]
        if source.get("source_id")
    }

    rows = []
    complete_suite_count = 0
    for rule in _base_inputs(playbook):
        category = rule.get("clause_type")
        family = str(rule["rule_family"])
        base_rule_id = str(rule["base_rule_id"])
        base_key = f"{family}::{category}::{base_rule_id}" if category else f"{family}::{base_rule_id}"
        rule_id = f"BASE::{base_key}"
        cases = rule.get("regression_cases") or {"positive": [], "negative": [], "edge": []}
        positive = cases.get("positive") or []
        negative = cases.get("negative") or []
        edge = cases.get("edge") or []
        suite_complete = bool(positive and negative and edge)
        complete_suite_count += int(suite_complete)

        source_ids = sorted(set(str(source_id) for source_id in (rule.get("source_ids") or [])))
        linked_sources = [source_by_id[source_id] for source_id in source_ids if source_id in source_by_id]
        source_metadata = [
            {
                key: source.get(key)
                for key in (
                    "source_id", "source_title", "source_url", "source_tier",
                    "authority_status", "jurisdiction", "contract_type", "effective_date",
                    "effective_date_status", "pinpoint_citation", "citation_status",
                    "retrieval_date", "license_status", "transferability",
                    "can_support_legal_conclusion", "missing_metadata", "metadata_note",
                )
            }
            for source in linked_sources
        ]
        citation_status = _source_status(source_ids, source_by_id)
        jurisdiction_scope = list(rule.get("jurisdiction_scope") or ["UNSPECIFIED"])
        jurisdiction_status = str(
            rule.get("jurisdiction_status")
            or (
                "UNRESOLVED"
                if any(str(value).strip().upper() in {"", "UNSPECIFIED", "UNKNOWN"} for value in jurisdiction_scope)
                else "DECLARED_NOT_VERIFIED"
            )
        )
        validation_status = str(rule.get("validation_status") or "DRAFT_UNVALIDATED")
        approval_status = str(rule.get("approval_status") or "UNAPPROVED")
        governance = rule.get("review_governance") if isinstance(rule.get("review_governance"), dict) else {}
        reviewer_1 = _reviewer_decision(governance, 1)
        reviewer_2 = _reviewer_decision(governance, 2)

        next_actions = []
        if not suite_complete:
            next_actions.append("AUTHOR_POSITIVE_NEGATIVE_EDGE_CASES")
        if jurisdiction_status != "VERIFIED":
            next_actions.append("VERIFY_JURISDICTION_SCOPE")
        if citation_status != "VERIFIED_PINPOINT":
            next_actions.append("VERIFY_SOURCE_PINPOINTS_AND_RETRIEVAL_DATE")
        if validation_status not in {"ADJUDICATED", "APPROVED", "REJECTED"}:
            next_actions.append("DUAL_REVIEW_AND_INDEPENDENT_ADJUDICATION")
        if validation_status == "APPROVED" and approval_status != "APPROVED":
            next_actions.append("RECONCILE_RULE_APPROVAL_STATUS")

        authority_entry = authority_by_clause.get(str(category or ""))
        if authority_entry:
            authority_map_clause_type = str(authority_entry["clause_type"])
            authority_map_ids = list(authority_entry.get("authority_ids") or [])
            authority_sources = [
                {
                    key: authority_by_id[authority_id].get(key)
                    for key in (
                        "authority_id", "title", "citation", "source_type", "url", "pinpoint",
                        "jurisdiction", "source_tier", "authority_status",
                        "effective_date", "effective_date_status", "retrieval_date",
                        "verification_status", "currentness_status", "scope_limit",
                    )
                }
                for authority_id in authority_map_ids
                if authority_id in authority_by_id
            ]
            authority_coverage_status = str(authority_entry["authority_coverage_status"])
            authority_scope_note = str(authority_entry["scope_note"])
            authority_jurisdiction_policy = str(authority_entry["jurisdiction_policy"])
            authority_map_review_status = str(authority_entry["review_status"])
        else:
            authority_map_clause_type = ""
            authority_map_ids = []
            authority_sources = []
            authority_coverage_status = "RULE_FAMILY_SPECIFIC_AUTHORITY_REVIEW_REQUIRED"
            authority_scope_note = "Cross-clause, document-level, and regex rules require authority mapping based on their actual trigger and contract facts."
            authority_jurisdiction_policy = "GOVERNING_LAW_AND_RULE_CONTEXT_REQUIRED"
            authority_map_review_status = "RESEARCH_SEED_NOT_LEGALLY_APPROVED"

        rows.append({
            "queue_schema_version": "1",
            "source_playbook_hash": playbook_hash,
            "rule_id": rule_id,
            "base_rule_key": base_key,
            "base_rule_id": base_rule_id,
            "rule_family": family,
            "clause_type": category or "",
            "title": str(rule.get("title") or base_rule_id),
            "risk_domain": str(rule.get("risk_domain") or "Commercial Risk"),
            "risk_type": str(rule.get("risk_type") or ""),
            "perspective": str(rule.get("perspective") or "customer_buyer"),
            "contract_type_scope_json": _json(rule.get("contract_type_scope") or ["unspecified_commercial_contract"]),
            "jurisdiction_scope_json": _json(jurisdiction_scope),
            "jurisdiction_status": jurisdiction_status,
            "decision_logic_json": _json(rule.get("decision_logic") or {}),
            "evidence_contract_json": _json(rule.get("evidence_contract") or {}),
            "source_ids_json": _json(source_ids),
            "source_citation_status": citation_status,
            "authority_map_clause_type": authority_map_clause_type,
            "authority_map_ids_json": _json(authority_map_ids),
            "authority_sources_json": _json(authority_sources),
            "authority_coverage_status": authority_coverage_status,
            "authority_scope_note": authority_scope_note,
            "authority_jurisdiction_policy": authority_jurisdiction_policy,
            "authority_map_review_status": authority_map_review_status,
            "source_metadata_json": _json(source_metadata),
            "validation_status": validation_status,
            "approval_status": approval_status,
            "positive_case_json": _json(positive),
            "negative_case_json": _json(negative),
            "edge_case_json": _json(edge),
            "case_suite_status": "COMPLETE" if suite_complete else "INCOMPLETE",
            "reviewer_1_id": str(reviewer_1.get("reviewer_id") or ""),
            "reviewer_1_decision": str(reviewer_1.get("decision") or ""),
            "reviewer_1_rationale": str(reviewer_1.get("rationale") or ""),
            "reviewer_1_reviewed_at": str(reviewer_1.get("reviewed_at") or ""),
            "reviewer_2_id": str(reviewer_2.get("reviewer_id") or ""),
            "reviewer_2_decision": str(reviewer_2.get("decision") or ""),
            "reviewer_2_rationale": str(reviewer_2.get("rationale") or ""),
            "reviewer_2_reviewed_at": str(reviewer_2.get("reviewed_at") or ""),
            "adjudicator_id": str(governance.get("adjudicator_id") or ""),
            "adjudication_reference": str(governance.get("adjudication_reference") or ""),
            "adjudication_notes": str(governance.get("adjudication_notes") or ""),
            "adjudicated_at": str(governance.get("adjudicated_at") or ""),
            "approved_by": str(governance.get("approved_by") or ""),
            "approved_at": str(governance.get("approved_at") or ""),
            "approval_basis": str(governance.get("approval_basis") or ""),
            "next_action": ";".join(next_actions) if next_actions else "NONE",
        })

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue(), len(rows), complete_suite_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if the committed review queue is stale.")
    parser.add_argument("--write", action="store_true", help="Regenerate the review queue.")
    args = parser.parse_args()
    if args.check == args.write:
        parser.error("Choose exactly one of --check or --write.")

    expected, rule_count, complete_suite_count = build_queue_text()
    if args.write:
        OUTPUT_PATH.write_text(expected, encoding="utf-8", newline="")
        print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)}: {rule_count} base rules; {complete_suite_count} complete exception suites.")
        return 0

    if not OUTPUT_PATH.exists() or OUTPUT_PATH.read_text(encoding="utf-8") != expected:
        print("Rule review queue is stale or missing. Run: python scripts/risk/build_rule_review_queue.py --write", file=sys.stderr)
        return 1
    print(f"Rule review queue reproducible: {rule_count} base rules; {complete_suite_count} complete exception suites.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
