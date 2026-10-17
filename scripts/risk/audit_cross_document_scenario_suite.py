#!/usr/bin/env python3
"""Validate cross-clause/document synthetic diagnostic coverage.

This checks test-fixture integrity only. It does not measure LLM accuracy.
"""
from __future__ import annotations
import hashlib, json, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "data/risk/evaluation/cross_document_v1"
PLAYBOOK = ROOT / "data/risk/commercial_clause_risk_playbook.json"
TAXONOMY = ROOT / "backend/data/legal_knowledge/risk_taxonomy.json"
MATRIX = SUITE / "scenario_matrix.jsonl"
MANIFEST = SUITE / "manifest.json"
OUT = ROOT / "data/risk/results/cross_document_scenario_audit.json"
OUT_MD = ROOT / "data/risk/results/cross_document_scenario_audit.md"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    playbook = json.loads(PLAYBOOK.read_text(encoding="utf-8"))
    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in MATRIX.read_text(encoding="utf-8").splitlines() if line.strip()]

    expected_ids = {
        str(x.get("id"))
        for x in (playbook.get("cross_clause_checks") or []) + (playbook.get("document_level_checks") or [])
    }
    found_ids = {str(x.get("check_id") or "") for x in rows}
    domain_set = {str(x.get("risk_domain")) for x in taxonomy.get("risk_domains") or []}
    scenarios = Counter(row.get("scenario_type") for row in rows)
    status_counts = Counter(row.get("expected_status") for row in rows)
    case_ids = [str(row.get("scenario_id") or "") for row in rows]

    missing_anchors = []
    missing_fixtures = []
    fixture_hash_mismatches = []
    for row in rows:
        fixture = ROOT / str(row.get("fixture_file") or "")
        if not fixture.is_file():
            missing_fixtures.append({"scenario_id": row.get("scenario_id"), "path": str(fixture)})
            continue
        actual_hash = sha(fixture)
        if actual_hash != row.get("fixture_sha256"):
            fixture_hash_mismatches.append({"scenario_id": row.get("scenario_id"), "expected": row.get("fixture_sha256"), "actual": actual_hash})
        text = fixture.read_text(encoding="utf-8").casefold()
        for anchor in row.get("evidence_anchors") or []:
            if str(anchor).casefold() not in text:
                missing_anchors.append({"scenario_id": row.get("scenario_id"), "anchor": anchor})

    checks = {
        "all_13_cross_document_checks_covered": len(expected_ids) == 13 and found_ids == expected_ids,
        "all_expected_39_scenarios_present": len(rows) == 39 and len(set(case_ids)) == 39,
        "three_scenario_types_have_13_cases_each": scenarios == Counter({"positive": 13, "control": 13, "incomplete": 13}),
        "all_scenarios_have_canonical_domains": all(row.get("risk_domain") in domain_set for row in rows),
        "all_expected_evidence_anchors_exist": not missing_anchors,
        "all_fixture_hashes_match": not fixture_hash_mismatches,
        "all_fixture_files_exist": not missing_fixtures,
        "synthetic_non_gold_label_is_explicit": all(row.get("label_provenance") == "AUTHORED_SYNTHETIC_TEST_STIMULUS_NOT_HUMAN_GOLD" for row in rows),
        "playbook_hash_matches_manifest": sha(PLAYBOOK) == manifest.get("playbook_sha256"),
        "manifest_case_count_matches": manifest.get("case_count") == len(rows),
    }
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "case_count": len(rows),
        "check_ids_covered": sorted(found_ids),
        "scenario_type_counts": dict(scenarios),
        "expected_status_counts": dict(status_counts),
        "fixture_hashes": {kind: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for kind, path in {
            "positive": "data/risk/evaluation/cross_document_v1/positive_risk_stress_contract.txt",
            "control": "data/risk/evaluation/cross_document_v1/protected_control_contract.txt",
            "incomplete": "data/risk/evaluation/cross_document_v1/incomplete_contract_pack.txt",
        }.items()},
        "missing_anchors": missing_anchors,
        "fixture_hash_mismatches": fixture_hash_mismatches,
        "missing_fixtures": missing_fixtures,
        "interpretation": (
            "This is a synthetic fixture-integrity/coverage audit. It verifies that each cross-clause/document "
            "check has positive, protected-control and incomplete-context stimuli with the recorded text anchors. "
            "It does not prove the LLM makes the expected decision, does not estimate generalization, and is not human gold."
        ),
        "playbook_sha256": sha(PLAYBOOK),
        "taxonomy_sha256": sha(TAXONOMY),
        "scenario_matrix_sha256": sha(MATRIX),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Cross-Clause / Document-Level Scenario Audit",
        "",
        f"Status: {report['status']}",
        "",
        f"- Synthetic scenarios: {len(rows)}",
        f"- Checks covered: {len(found_ids)} (10 cross-clause + 3 document-level)",
        f"- Scenario classes: {dict(scenarios)}",
        f"- Expected behavior distribution: {dict(status_counts)}",
        "",
        "## Invariants",
        "",
    ]
    lines.extend(f"- [{'x' if value else ' '}] {name}" for name, value in checks.items())
    lines += [
        "",
        "## Interpretation",
        "",
        report["interpretation"],
        "",
        "## Hashes",
        "",
        f"- Playbook: {report['playbook_sha256']}",
        f"- Taxonomy: {report['taxonomy_sha256']}",
        f"- Scenario matrix: {report['scenario_matrix_sha256']}",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "case_count": len(rows), "checks": checks, "json": str(OUT.relative_to(ROOT)), "markdown": str(OUT_MD.relative_to(ROOT))}, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
