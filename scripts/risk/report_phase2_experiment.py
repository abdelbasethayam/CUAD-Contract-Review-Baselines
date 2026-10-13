#!/usr/bin/env python3
"""Build the annotation-independent Phase 2 playbook-rule conformance report."""
from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RISK_PLAYBOOK = ROOT / "data" / "risk" / "commercial_clause_risk_playbook.json"
TAXONOMY = ROOT / "backend" / "data" / "legal_knowledge" / "risk_taxonomy.json"
INDEX_REPORT = ROOT / "data" / "risk" / "EVALUATION_INTEGRITY_REPORT.json"
RULE_REPORT = ROOT / "data" / "risk" / "results" / "playbook_rule_validation.json"
OUT_DIR = ROOT / "data" / "risk" / "results"


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def git_head() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def main() -> int:
    playbook = json.loads(RISK_PLAYBOOK.read_text(encoding="utf-8"))
    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    index_report = json.loads(INDEX_REPORT.read_text(encoding="utf-8"))
    rule_report = json.loads(RULE_REPORT.read_text(encoding="utf-8"))

    clause_types = playbook.get("clause_types") or {}
    clause_question_count = sum(
        len((item or {}).get("checklist") or [])
        for item in clause_types.values()
    )
    deterministic_rules = playbook.get("deterministic_rules") or []
    domain_counts = Counter(
        str(item.get("risk_domain") or "UNMAPPED")
        for item in deterministic_rules
    )
    taxonomy_domains = {
        str(item.get("risk_domain") or "")
        for item in taxonomy.get("risk_domains", [])
    }
    missing_domains = sorted(set(domain_counts) - taxonomy_domains)
    source_files = [
        RISK_PLAYBOOK,
        TAXONOMY,
        INDEX_REPORT,
        RULE_REPORT,
        ROOT / "backend" / "app" / "core" / "risk" / "deterministic_rules.py",
        ROOT / "backend" / "app" / "core" / "risk" / "risk_engine.py",
        ROOT / "backend" / "app" / "core" / "risk" / "risk_detector.py",
        ROOT / "backend" / "app" / "core" / "risk" / "risk_playbook.py",
        ROOT / "scripts" / "risk" / "validate_playbook_rules.py",
    ]

    checks = [
        {"name": "playbook_has_deterministic_rules", "passed": len(deterministic_rules) >= 1, "value": len(deterministic_rules)},
        {"name": "playbook_clause_types_have_questions", "passed": bool(clause_types) and clause_question_count > 0, "value": {"clause_types": len(clause_types), "questions": clause_question_count}},
        {"name": "cross_clause_questions_present", "passed": len(playbook.get("cross_clause_checks") or []) > 0, "value": len(playbook.get("cross_clause_checks") or [])},
        {"name": "document_questions_present", "passed": len(playbook.get("document_level_checks") or []) > 0, "value": len(playbook.get("document_level_checks") or [])},
        {"name": "rule_domains_covered_by_taxonomy", "passed": not missing_domains, "value": {"missing": missing_domains, "mapped_rule_domains": dict(domain_counts)}},
        {"name": "rule_validation_report_passes", "passed": rule_report.get("status") == "PASS", "value": {"status": rule_report.get("status"), "checks_passed": rule_report.get("checks_passed"), "checks_total": rule_report.get("checks_total")}},
        {"name": "classification_index_isolation_passes", "passed": bool(index_report.get("all_passed", index_report.get("status") == "PASS"), "value": {"status": index_report.get("status"), "checks_passed": index_report.get("checks_passed"), "checks_total": index_report.get("checks_total")}},
    ]
    overall = all(item["passed"] for item in checks)
    report = {
        "report_version": "phase2-playbook-rule-report-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head_at_report_time": git_head(),
        "status": "PASS" if overall else "FAIL",
        "evaluation_mode": "PLAYBOOK_RULE_CONFORMANCE",
        "annotation_datasets_read": False,
        "risk_text_span_dataset_used_for_flagging": False,
        "fine_tuning_used": False,
        "playbook": {
            "title": playbook.get("title"),
            "source_version": playbook.get("source_version", playbook.get("version")),
            "playbook_hash": playbook.get("playbook_hash"),
            "clause_type_count": len(clause_types),
            "clause_question_count": clause_question_count,
            "cross_clause_check_count": len(playbook.get("cross_clause_checks") or []),
            "document_check_count": len(playbook.get("document_level_checks") or []),
            "deterministic_rule_count": len(deterministic_rules),
        },
        "taxonomy": {"domain_count": len(taxonomy_domains), "domains": sorted(taxonomy_domains)},
        "classification_index_isolation": {
            "status": index_report.get("status", "PASS" if index_report.get("all_passed") else "FAIL"),
            "checks_passed": index_report.get("checks_passed"),
            "checks_total": index_report.get("checks_total"),
            "train_contracts": index_report.get("train_contracts"),
            "test_contracts": index_report.get("test_contracts"),
            "train_clause_rows": index_report.get("train_clause_rows", index_report.get("train_rows")),
            "test_clause_rows": index_report.get("test_clause_rows", index_report.get("test_rows")),
        },
        "rule_validation": {
            "status": rule_report.get("status"),
            "checks_passed": rule_report.get("checks_passed"),
            "checks_total": rule_report.get("checks_total"),
            "checks": rule_report.get("checks", []),
        },
        "checks": checks,
        "checks_passed": sum(item["passed"] for item in checks),
        "checks_total": len(checks),
        "interpretation": (
            "This report validates explicit playbook rule configuration, taxonomy mapping, "
            "exact-quote rule behavior and clause-classification index isolation. It is deliberately "
            "independent of risk-span annotation datasets. The risk system is evaluated as a "
            "transparent review-prioritization engine, not as a legally authoritative decision-maker."
        ),
        "hashes": {str(path.relative_to(ROOT)): digest(path) for path in source_files if path.is_file()},
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "phase2_reproducible_report.json"
    markdown_path = OUT_DIR / "phase2_reproducible_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Phase 2 Playbook-Rule Conformance Report",
        "",
        "**Status: " + report["status"] + "**",
        "",
        "Generated UTC: " + report["generated_at_utc"],
        "Git HEAD: " + str(report["git_head_at_report_time"] or "unavailable"),
        "",
        "## Evaluation contract",
        "",
        "Risk flags are generated by deterministic predicates authored in the versioned commercial playbook and by explicit playbook questions over the uploaded contract. The risk prompt does not receive retrieved CUAD training examples or example risk spans. No annotation dataset is read by this report or required by the release checks.",
        "",
        "## Coverage",
        "",
        "- Clause categories with question checklists: " + str(report["playbook"]["clause_type_count"]),
        "- Clause-level questions: " + str(report["playbook"]["clause_question_count"]),
        "- Cross-clause questions: " + str(report["playbook"]["cross_clause_check_count"]),
        "- Document-level questions: " + str(report["playbook"]["document_check_count"]),
        "- Deterministic playbook predicates: " + str(report["playbook"]["deterministic_rule_count"]),
        "- Risk taxonomy domains: " + str(report["taxonomy"]["domain_count"]),
        "- Classification index isolation: " + str(report["classification_index_isolation"]["checks_passed"]) + "/" + str(report["classification_index_isolation"]["checks_total"]) + " checks",
        "",
        "## Release checks",
        "",
        "| Check | Result | Detail |",
        "|---|---|---|",
    ]
    for item in checks:
        lines.append("| " + item["name"] + " | " + ("PASS" if item["passed"] else "FAIL") + " | " + json.dumps(item["value"], ensure_ascii=False) + " |")
    lines.extend([
        "",
        "## What a rule match means",
        "",
        "A match means that exact wording in the uploaded contract triggered a defined review rule. The system records the rule ID, domain, explanation and exact source quote. This is a reproducible review trigger—not a legal conclusion, calibrated probability, or guarantee that unflagged text is risk-free.",
        "",
        "The relevant measured outputs are rule-pattern conformance, unique and valid rule definitions, taxonomy coverage, exact source-quote validation, train/test isolation for the separate clause-classification index, synthetic playbook-question regression tests, and backend tests.",
        "",
        "## SHA-256",
        "",
    ])
    lines.extend("- " + path + ": " + sha for path, sha in report["hashes"].items())
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks_passed": report["checks_passed"], "checks_total": report["checks_total"], "json": str(json_path.relative_to(ROOT)), "markdown": str(markdown_path.relative_to(ROOT))}, indent=2))
    return 0 if overall else 2


if __name__ == "__main__":
    raise SystemExit(main())
