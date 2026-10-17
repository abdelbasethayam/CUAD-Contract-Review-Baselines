#!/usr/bin/env python3
"""Fail-closed validator for adjudicated contract-risk gold records."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "data" / "risk" / "evaluation" / "risk_gold.schema.json"
CATALOG_PATH = ROOT / "data" / "risk" / "authority_catalog.json"
PLAYBOOK_PATH = ROOT / "data" / "risk" / "commercial_clause_risk_playbook.json"
REGISTRY_PATH = ROOT / "data" / "risk" / "rule_registry.jsonl"
DEFAULT_INPUT = ROOT / "data" / "risk" / "evaluation" / "risk_gold.jsonl"
VALID_LEGAL_EFFECTIVE_STATUSES = {"VERIFIED_FOR_RELEVANT_PERIOD"}
LEGAL_VERIFIED_SOURCE_STATUSES = {
    "OFFICIAL_TEXT_AND_PINPOINT_RETRIEVED",
    "OFFICIAL_CHAPTER_TEXT_AND_PINPOINT_RETRIEVED",
    "OFFICIAL_PART_PAGE_AND_SECTION_PINPOINT",
}


def _jurisdiction_codes(value: str) -> set[str]:
    normalized = str(value or "").strip().upper()
    aliases = {
        "UNITED STATES FEDERAL LAW": "US-FEDERAL",
        "U.S. FEDERAL LAW": "US-FEDERAL",
        "FEDERAL LAW": "US-FEDERAL",
        "NEW YORK": "US-NY",
        "NEW YORK LAW": "US-NY",
        "DELAWARE": "US-DE",
        "DELAWARE LAW": "US-DE",
        "CALIFORNIA": "US-CA",
        "CALIFORNIA LAW": "US-CA",
    }
    normalized = aliases.get(normalized, normalized)
    return set(re.findall(r"\bUS-[A-Z]{2,8}\b", normalized))


def _authority_jurisdiction_compatible(resolved_law: str, authority_jurisdiction: str) -> bool:
    resolved_codes = _jurisdiction_codes(resolved_law)
    authority_code = str(authority_jurisdiction or "").strip().upper()
    if not resolved_codes:
        return False
    if authority_code == "US-FEDERAL":
        # Federal authority can be relevant to a U.S. contract, subject to the statute's scope.
        return any(code.startswith("US-") for code in resolved_codes)
    return authority_code in resolved_codes


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid_jsonl_line:{line_number}:{exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"record_must_be_object:{line_number}")
        records.append(record)
    return records


def validate_records(
    records: list[dict[str, Any]],
    *,
    schema: dict[str, Any],
    taxonomy: set[str],
    base_rule_ids: set[str],
    authority_by_id: dict[str, dict[str, Any]],
    normalized_text_by_contract: dict[str, str] | None = None,
) -> list[str]:
    problems: list[str] = []
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    seen_record_ids: set[str] = set()
    contract_splits: dict[str, set[str]] = defaultdict(set)
    duplicate_group_splits: dict[str, set[str]] = defaultdict(set)

    for index, record in enumerate(records, start=1):
        record_id = str(record.get("record_id") or f"row-{index}")
        for error in validator.iter_errors(record):
            problems.append(
                f"schema_error:{record_id}:{'/'.join(str(x) for x in error.absolute_path)}:{error.message}"
            )
        if record_id in seen_record_ids:
            problems.append(f"duplicate_record_id:{record_id}")
        seen_record_ids.add(record_id)

        if record.get("clause_type") not in taxonomy:
            problems.append(f"unknown_clause_type:{record_id}:{record.get('clause_type')}")
        if record.get("rule_id") not in base_rule_ids:
            problems.append(f"unknown_or_nonbase_rule_id:{record_id}:{record.get('rule_id')}")

        split = str(record.get("split") or "")
        contract_id = str(record.get("contract_id") or "")
        if contract_id:
            contract_splits[contract_id].add(split)
        group_id = record.get("near_duplicate_group_id")
        if group_id:
            duplicate_group_splits[str(group_id)].add(split)

        reviewer_1 = record.get("reviewer_1") or {}
        reviewer_2 = record.get("reviewer_2") or {}
        adjudication = record.get("adjudication") or {}
        reviewer_ids = {
            str(reviewer_1.get("reviewer_id") or "").strip(),
            str(reviewer_2.get("reviewer_id") or "").strip(),
        }
        if len(reviewer_ids) != 2 or "" in reviewer_ids:
            problems.append(f"reviewers_must_be_distinct:{record_id}")
        adjudicator_id = str(adjudication.get("adjudicator_id") or "").strip()
        if not adjudicator_id or adjudicator_id in reviewer_ids:
            problems.append(f"adjudicator_must_be_independent:{record_id}")
        if record.get("decision") != adjudication.get("final_decision"):
            problems.append(f"record_decision_must_match_adjudication:{record_id}")

        evidence = record.get("evidence") or []
        for evidence_index, item in enumerate(evidence, start=1):
            quote = str(item.get("quote") or "")
            if _sha256(quote) != item.get("quote_sha256"):
                problems.append(f"evidence_quote_hash_mismatch:{record_id}:{evidence_index}")
            start = item.get("start_char")
            end = item.get("end_char")
            if isinstance(start, int) and isinstance(end, int) and end <= start:
                problems.append(f"invalid_evidence_offsets:{record_id}:{evidence_index}")
            if normalized_text_by_contract is not None and contract_id not in normalized_text_by_contract:
                problems.append(f"normalized_text_missing_for_contract:{record_id}:{contract_id}")
            text = (normalized_text_by_contract or {}).get(contract_id)
            if text is not None:
                if _sha256(text) != record.get("normalized_text_sha256"):
                    problems.append(f"normalized_text_hash_mismatch:{record_id}")
                if not isinstance(start, int) or not isinstance(end, int) or text[start:end] != quote:
                    problems.append(f"evidence_quote_not_exact_source_span:{record_id}:{evidence_index}")

        referenced_ids = []
        for authority in record.get("authority_refs") or []:
            authority_id = str(authority.get("authority_id") or "")
            referenced_ids.append(authority_id)
            source = authority_by_id.get(authority_id)
            if source is None:
                problems.append(f"unknown_authority_id:{record_id}:{authority_id}")
                continue
            for record_field, source_field in (
                ("citation", "citation"),
                ("pinpoint", "pinpoint"),
                ("jurisdiction", "jurisdiction"),
                ("source_tier", "source_tier"),
                ("retrieval_date", "retrieval_date"),
                ("verification_status", "verification_status"),
                ("effective_date_status", "effective_date_status"),
            ):
                if authority.get(record_field) != source.get(source_field):
                    problems.append(f"authority_metadata_mismatch:{record_id}:{authority_id}:{record_field}")

        if record.get("review_target") == "LEGAL_PROPOSITION":
            governing_law = record.get("governing_law") or {}
            if governing_law.get("status") != "VERIFIED" or not governing_law.get("resolved_law") or not governing_law.get("relevant_date"):
                problems.append(f"legal_proposition_requires_verified_law_and_date:{record_id}")
            if not referenced_ids:
                problems.append(f"legal_proposition_requires_authority:{record_id}")
            resolved_law = str(governing_law.get("resolved_law") or "")
            for authority_id in referenced_ids:
                source = authority_by_id.get(authority_id)
                if source is None:
                    continue
                if source.get("source_tier") != "A":
                    problems.append(f"legal_proposition_requires_tier_a_authority:{record_id}:{authority_id}")
                if not _authority_jurisdiction_compatible(resolved_law, str(source.get("jurisdiction") or "")):
                    problems.append(f"authority_jurisdiction_mismatch:{record_id}:{authority_id}:{resolved_law}:{source.get('jurisdiction')}")
                if source.get("effective_date_status") not in VALID_LEGAL_EFFECTIVE_STATUSES:
                    problems.append(f"authority_effective_period_not_verified:{record_id}:{authority_id}")
                verification = str(source.get("verification_status") or "")
                if verification not in LEGAL_VERIFIED_SOURCE_STATUSES:
                    problems.append(f"authority_source_verification_not_cleared:{record_id}:{authority_id}")

    for contract_id, splits in contract_splits.items():
        if len(splits) > 1:
            problems.append(f"contract_leakage_across_splits:{contract_id}:{sorted(splits)}")
    for group_id, splits in duplicate_group_splits.items():
        if len(splits) > 1:
            problems.append(f"near_duplicate_leakage_across_splits:{group_id}:{sorted(splits)}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema-only", action="store_true", help="Validate schema without claiming a gold set exists.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Adjudicated gold JSONL file.")
    parser.add_argument("--normalized-text-dir", type=Path, help="Directory containing <contract_id>.txt normalized contract text.")
    args = parser.parse_args()

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    if args.schema_only:
        print(json.dumps({
            "status": "PASS_SCHEMA_ONLY",
            "gold_dataset_present": DEFAULT_INPUT.exists(),
            "legal_accuracy_claim_allowed": False,
        }, indent=2))
        return 0

    if not args.input.is_file():
        print(f"Gold file not found: {args.input}. No project-specific risk gold has been created.", file=sys.stderr)
        return 2
    if args.normalized_text_dir is None or not args.normalized_text_dir.is_dir():
        print("--normalized-text-dir is required to verify evidence offsets against source text.", file=sys.stderr)
        return 2

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    playbook = json.loads(PLAYBOOK_PATH.read_text(encoding="utf-8"))
    registry = _load_jsonl(REGISTRY_PATH)
    taxonomy = set((playbook.get("clause_types") or {}).keys())
    base_rule_ids = {
        str(item["rule_id"])
        for item in registry
        if item.get("record_kind") == "BASE_RULE"
    }
    authority_by_id = {
        str(item["authority_id"]): item
        for item in catalog.get("authorities", [])
        if item.get("authority_id")
    }
    records = _load_jsonl(args.input)
    normalized_text_by_contract = {}
    missing_text_files = []
    for record in records:
        contract_id = str(record.get("contract_id") or "")
        if contract_id and contract_id not in normalized_text_by_contract:
            text_path = args.normalized_text_dir / f"{contract_id}.txt"
            if text_path.is_file():
                normalized_text_by_contract[contract_id] = text_path.read_text(encoding="utf-8")
            else:
                missing_text_files.append(str(text_path))
    if missing_text_files:
        print(json.dumps({
            "status": "FAIL",
            "record_count": len(records),
            "missing_normalized_text_files": sorted(set(missing_text_files)),
            "legal_accuracy_claim_allowed": False,
        }, indent=2, ensure_ascii=False))
        return 1
    problems = validate_records(
        records,
        schema=schema,
        taxonomy=taxonomy,
        base_rule_ids=base_rule_ids,
        authority_by_id=authority_by_id,
        normalized_text_by_contract=normalized_text_by_contract,
    )
    report = {
        "status": "PASS" if records and not problems else "FAIL",
        "record_count": len(records),
        "contract_count": len({item.get("contract_id") for item in records}),
        "legal_accuracy_claim_allowed": False,
        "problems": problems,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
