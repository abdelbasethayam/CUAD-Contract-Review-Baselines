#!/usr/bin/env python3
"""Validate complete, scoped authority mapping for all 37 contract clause classes.

This is a structural/provenance gate. It does not certify legal correctness or
make an authority applicable to a contract.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK_PATH = ROOT / "data" / "risk" / "commercial_clause_risk_playbook.json"
CATALOG_PATH = ROOT / "data" / "risk" / "authority_catalog.json"
CATALOG_SCHEMA_PATH = ROOT / "data" / "risk" / "authority_catalog.schema.json"
MAP_PATH = ROOT / "data" / "risk" / "clause_authority_map.json"
MAP_SCHEMA_PATH = ROOT / "data" / "risk" / "clause_authority_map.schema.json"

OFFICIAL_HOSTS = {
    "uscode.house.gov",
    "www.nysenate.gov",
    "nysenate.gov",
    "delcode.delaware.gov",
    "leginfo.legislature.ca.gov",
    "www.ftc.gov",
    "ftc.gov",
}
ALLOWED_REPUBLICATION_HOSTS = {"law.justia.com"}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate() -> tuple[dict, list[str]]:
    problems: list[str] = []
    playbook = _load(PLAYBOOK_PATH)
    catalog = _load(CATALOG_PATH)
    clause_map = _load(MAP_PATH)
    catalog_schema = _load(CATALOG_SCHEMA_PATH)
    map_schema = _load(MAP_SCHEMA_PATH)

    Draft202012Validator.check_schema(catalog_schema)
    Draft202012Validator.check_schema(map_schema)
    catalog_errors = list(
        Draft202012Validator(catalog_schema, format_checker=FormatChecker()).iter_errors(catalog)
    )
    map_errors = list(
        Draft202012Validator(map_schema, format_checker=FormatChecker()).iter_errors(clause_map)
    )
    for error in catalog_errors[:100]:
        problems.append(
            f"authority_catalog_schema:{'/'.join(str(x) for x in error.absolute_path)}:{error.message}"
        )
    for error in map_errors[:100]:
        problems.append(
            f"clause_authority_map_schema:{'/'.join(str(x) for x in error.absolute_path)}:{error.message}"
        )

    taxonomy = set((playbook.get("clause_types") or {}).keys())
    entries = clause_map.get("clauses") or []
    map_names = [str(item.get("clause_type") or "") for item in entries]
    map_set = set(map_names)
    if len(entries) != 37 or len(taxonomy) != 37:
        problems.append(f"taxonomy_count_must_be_37:{len(taxonomy)}:{len(entries)}")
    if len(map_names) != len(map_set):
        problems.append("duplicate_clause_type_in_authority_map")
    if taxonomy != map_set:
        problems.append(
            "clause_taxonomy_mismatch:"
            f"missing={sorted(taxonomy - map_set)};extra={sorted(map_set - taxonomy)}"
        )

    authorities = catalog.get("authorities") or []
    authority_ids = [str(item.get("authority_id") or "") for item in authorities]
    if len(authority_ids) != len(set(authority_ids)):
        problems.append("duplicate_authority_id")
    authority_by_id = {item.get("authority_id"): item for item in authorities}
    source_types = Counter()
    verification_statuses = Counter()
    mapped_authority_ids: set[str] = set()

    for authority in authorities:
        authority_id = str(authority.get("authority_id") or "<missing-id>")
        source_types[str(authority.get("source_type") or "UNKNOWN")] += 1
        verification_statuses[str(authority.get("verification_status") or "UNKNOWN")] += 1
        parsed = urlparse(str(authority.get("url") or ""))
        if parsed.scheme != "https" or not parsed.netloc:
            problems.append(f"authority_url_must_be_https:{authority_id}")
        host = (parsed.hostname or "").lower()
        if authority.get("source_type") in {"FEDERAL_STATUTE", "STATE_STATUTE", "REGULATOR_STATUS_NOTICE"}:
            if host not in OFFICIAL_HOSTS:
                problems.append(f"government_authority_not_on_official_host:{authority_id}:{host}")
        elif authority.get("source_type") == "PRIMARY_COURT_OPINION_REPUBLISHED":
            if host not in ALLOWED_REPUBLICATION_HOSTS:
                problems.append(f"court_opinion_host_not_declared_republication:{authority_id}:{host}")
            if "OFFICIAL_DOCKET_COPY" not in str(authority.get("currentness_status") or ""):
                problems.append(f"republished_case_must_require_official_docket_check:{authority_id}")
        if not str(authority.get("pinpoint") or "").strip():
            problems.append(f"authority_pinpoint_missing:{authority_id}")
        if authority.get("retrieval_date") != catalog.get("retrieval_date"):
            problems.append(f"authority_retrieval_date_mismatch:{authority_id}")
        if authority.get("source_tier") == "A" and host in ALLOWED_REPUBLICATION_HOSTS:
            if "REPUBLICATION_HOST" not in str(authority.get("verification_status") or ""):
                problems.append(f"case_host_provenance_not_disclosed:{authority_id}")

    map_coverage = Counter()
    for item in entries:
        clause_type = str(item.get("clause_type") or "")
        authority_ids_for_clause = item.get("authority_ids") or []
        map_coverage[str(item.get("authority_coverage_status") or "UNKNOWN")] += 1
        if item.get("legal_conclusion_allowed") is not False:
            problems.append(f"legal_conclusion_must_remain_disabled:{clause_type}")
        if item.get("review_status") != "RESEARCH_SEED_NOT_LEGALLY_APPROVED":
            problems.append(f"clause_map_must_remain_unapproved:{clause_type}")
        if authority_ids_for_clause:
            if item.get("authority_coverage_status") != "LIMITED_PRIMARY_AUTHORITY_LINKED":
                problems.append(f"authority_coverage_status_mismatch:{clause_type}")
        else:
            if item.get("authority_coverage_status") != "NO_UNIVERSAL_PRIMARY_AUTHORITY_IDENTIFIED":
                problems.append(f"no_authority_must_be_explicitly_scoped:{clause_type}")
            if not any(
                phrase in str(item.get("scope_note") or "").lower()
                for phrase in ("no universal", "no single general", "no general")
            ):
                problems.append(f"no_authority_requires_explicit_explanation:{clause_type}")
        for authority_id in authority_ids_for_clause:
            if authority_id not in authority_by_id:
                problems.append(f"dangling_authority_reference:{clause_type}:{authority_id}")
            else:
                mapped_authority_ids.add(authority_id)

    unreferenced_authorities = sorted(set(authority_ids) - mapped_authority_ids)
    if unreferenced_authorities:
        problems.append(f"unreferenced_authority_records:{unreferenced_authorities}")

    report = {
        "status": "PASS" if not problems else "FAIL",
        "legal_approval_status": "NOT_APPROVED",
        "taxonomy_count": len(taxonomy),
        "mapped_clause_count": len(entries),
        "authority_record_count": len(authorities),
        "authority_records_referenced_by_map": len(mapped_authority_ids),
        "clause_coverage": dict(map_coverage),
        "source_types": dict(source_types),
        "source_verification_statuses": dict(verification_statuses),
        "clauses_without_universal_primary_authority": sorted(
            item["clause_type"] for item in entries if not item.get("authority_ids")
        ),
        "limitations": [
            "Structural completeness is not legal validation.",
            "The map is not a 50-state survey.",
            "New York and Delaware UCC authorities are limited to their statutory transaction scope.",
            "The FTC status notice does not replace state non-compete law.",
            "The republished Delaware opinion requires official docket and subsequent-history review.",
            "All clause rules remain review triggers; legal conclusions remain disabled.",
        ],
        "problems": problems,
    }
    return report, problems


def main() -> int:
    report, problems = validate()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
