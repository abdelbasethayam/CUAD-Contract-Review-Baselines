#!/usr/bin/env python3
"""Validate the playbook-rule risk contract without gold/silver risk-span datasets."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import HYBRID_COLLECTION, QDRANT_COLLECTION, QDRANT_PATH
from app.core.risk.knowledge_base import load_risk_knowledge
from app.core.risk.risk_playbook import load_playbook


def main() -> int:
    playbook = load_playbook(ROOT / "data" / "risk" / "commercial_clause_risk_playbook.json")
    taxonomy = load_risk_knowledge()
    rules = playbook.get("deterministic_rules") or []
    taxonomy_domains = {
        str(item.get("risk_domain") or "").strip()
        for item in taxonomy.get("risk_domains", [])
    }
    seen = set()
    results = []

    def check(name: str, passed: bool, detail) -> None:
        results.append({"name": name, "passed": bool(passed), "detail": detail})

    check("deterministic_rules_present", len(rules) >= 7, len(rules))
    ids = [str(item.get("id") or "") for item in rules]
    check("deterministic_rule_ids_unique", len(ids) == len(set(ids)) and all(ids), len(ids))
    regex_errors = []
    for item in rules:
        rule_id = str(item.get("id") or "<missing-id>")
        try:
            re.compile(str(item.get("pattern") or ""), re.IGNORECASE | re.DOTALL)
            for pattern in item.get("exclude_patterns") or []:
                re.compile(str(pattern), re.IGNORECASE | re.DOTALL)
        except re.error as exc:
            regex_errors.append(f"{rule_id}: {exc}")
    check("rule_regexes_compile", not regex_errors, regex_errors)

    missing_domains = [
        item.get("id")
        for item in rules
        if str(item.get("risk_domain") or "") not in taxonomy_domains
    ]
    check("rule_domains_mapped_to_taxonomy", not missing_domains, missing_domains)

    invalid_fields = [
        item.get("id")
        for item in rules
        if not item.get("question") or not item.get("risk_type") or not item.get("explanation")
    ]
    check("rules_have_question_risk_type_and_explanation", not invalid_fields, invalid_fields)

    forbidden_keys = {"training_examples", "retrieved_examples", "example_clause", "silver_evidence", "gold_evidence"}
    forbidden_fields = [
        f"{item.get('id')}:{key}"
        for item in rules
        for key in forbidden_keys
        if key in item
    ]
    check("rule_specs_contain_no_dataset_example_spans", not forbidden_fields, forbidden_fields)

    risk_sources = [
        ROOT / "backend" / "app" / "core" / "risk" / "risk_engine.py",
        ROOT / "backend" / "app" / "core" / "risk" / "risk_detector.py",
    ]
    forbidden_code_tokens = ("cuad_evidence", "_format_cuad_evidence", "CUAD retrieval evidence:")
    violations = []
    for path in risk_sources:
        source = path.read_text(encoding="utf-8")
        for token in forbidden_code_tokens:
            if token in source:
                violations.append(f"{path.relative_to(ROOT)} contains {token}")
    check("risk_prompt_path_has_no_cuad_example_injection", not violations, violations)

    active_engine = (ROOT / "backend" / "app" / "core" / "risk" / "risk_engine.py").read_text(encoding="utf-8")
    calibration_dependencies = ("load_calibration", "calibrate_risk_probability", "calibrate_severity")
    calibration_violations = [token for token in calibration_dependencies if token in active_engine]
    check("active_risk_engine_uses_no_calibration_artifacts", not calibration_violations, calibration_violations)

    release_path = ROOT / "scripts" / "risk" / "run_release_checks.py"
    release_source = release_path.read_text(encoding="utf-8")
    annotation_path_tokens = (
        "gold_annotations.csv",
        "silver_annotations_final_v5",
        "silver_queue.csv",
        "gold/annotation_queue.csv",
        "GOLD_STATUS.md",
    )
    release_annotation_refs = [token for token in annotation_path_tokens if token in release_source]
    check("release_gate_has_no_risk_annotation_inputs", not release_annotation_refs, release_annotation_refs)

    report = {
        "schema_version": 1,
        "status": "PASS" if all(item["passed"] for item in results) else "FAIL",
        "evaluation_mode": "PLAYBOOK_RULE_CONFORMANCE",
        "human_gold_required_for_release": False,
        "risk_span_dataset_used_for_flagging": False,
        "fine_tuning_used": False,
        "rule_count": len(rules),
        "taxonomy_domain_count": len(taxonomy_domains),
        "qdrant_path_for_classifier_integrity_only": str(QDRANT_PATH),
        "configured_classifier_collections": sorted({QDRANT_COLLECTION, HYBRID_COLLECTION}),
        "checks_total": len(results),
        "checks_passed": sum(item["passed"] for item in results),
        "checks": results,
        "interpretation": (
            "This is a deterministic configuration/policy conformance report, not a legal correctness or real-world risk-accuracy estimate. "
            "The risk rules run against the uploaded contract text and playbook questions; clause-category retrieval is separate."
        ),
    }
    destination = ROOT / "data" / "risk" / "results" / "playbook_rule_validation.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
