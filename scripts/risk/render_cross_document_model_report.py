#!/usr/bin/env python3
"""Render cross/document synthetic model results as a concise Markdown report.

Synthetic status matching is a regression metric only; it is not human gold or accuracy.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUMMARY = ROOT / "data/risk/results/cross_document_model_scenarios_summary.json"
CSV = ROOT / "data/risk/results/cross_document_model_scenarios.csv"
OUT = ROOT / "data/risk/results/cross_document_model_scenarios_summary.md"


def main() -> int:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    if summary.get("case_count") != 39:
        raise SystemExit(f"Expected 39 scenario results, found {summary.get('case_count')}")

    run_summaries = summary.get("scenario_run_summaries") or [{}]
    lines = [
        "# Cross-Clause / Document-Level Model Scenario Results",
        "",
        f"Status: {summary.get('status')}",
        "",
        f"- Cases: {summary.get('case_count')} / {summary.get('expected_case_count')}",
        f"- Synthetic status matches: {summary.get('scenario_status_conformance_count')} / {summary.get('case_count')} ({summary.get('scenario_status_conformance_rate', 0):.1%})",
        f"- Exact-positive-evidence gate: {summary.get('evidence_exact_all')}",
        f"- Check batch size: {summary.get('model_check_batch_size', run_summaries[0].get('model_check_batch_size'))}",
        f"- Model batches per scenario/pass: {summary.get('model_batches_per_pass', run_summaries[0].get('model_batches_per_pass'))}",
        "",
        "Interpretation: these are authored synthetic regression cases, not human gold. Status matching measures implementation behavior on these fixtures only; it is not accuracy, precision/recall on real contracts, or legal correctness.",
        "",
        "## Results by scenario type",
        "",
        "| Scenario | Cases | Matches | Rate | POTENTIAL_RISK | NO_RISK | INSUFFICIENT_EVIDENCE | MISSING |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, item in summary.get("scenario_status_conformance_by_type", {}).items():
        counts = item.get("observed_status_counts") or {}
        rate = item.get("rate")
        rate_str = f"{rate:.1%}" if rate is not None else "N/A"
        lines.append(
            f"| {name} | {item.get('cases')} | {item.get('matched')} | {rate_str} | "
            f"{counts.get('POTENTIAL_RISK', 0)} | {counts.get('NO_RISK', 0)} | "
            f"{counts.get('INSUFFICIENT_EVIDENCE', 0)} | {counts.get('MISSING', 0)} |"
        )

    lines += [
        "",
        "## Results by check",
        "",
        "| Check | Scope | Domain | Matches | Cases | Rate | Expected statuses | Observed statuses |",
        "|---|---|---|---:|---:|---:|---|---|",
    ]
    for item in summary.get("scenario_status_conformance_by_check", []):
        rate = item.get("rate")
        rate_str = f"{rate:.1%}" if rate is not None else "N/A"
        expected = ", ".join(str(x) for x in item.get("expected_statuses", []))
        observed = ", ".join(str(x) for x in item.get("observed_statuses", []))
        lines.append(
            f"| {item.get('check_id')} | {item.get('scope')} | {item.get('risk_domain')} | "
            f"{item.get('matched')} | {item.get('cases')} | {rate_str} | {expected} | {observed} |"
        )

    lines += [
        "",
        "## Traceability",
        "",
        f"- Playbook SHA-256: {summary.get('playbook_sha256')}",
        f"- Analyzer code SHA-256: {summary.get('analyzer_code_sha256')}",
        f"- Runner code SHA-256: {summary.get('runner_code_sha256')}",
        f"- Scenario manifest SHA-256: {summary.get('scenario_suite_manifest_sha256')}",
        f"- JSONL SHA-256: {summary.get('jsonl_sha256')}",
        f"- CSV SHA-256: {summary.get('csv_sha256')}",
        f"- CSV artifact: {CSV.relative_to(ROOT)}",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
