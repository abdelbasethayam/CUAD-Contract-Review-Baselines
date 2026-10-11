#!/usr/bin/env python3
"""Run a direct LLM diagnostic over synthetic cross-clause/document scenarios.

The expected behaviors are authored regression stimuli, not human gold. This
script measures scenario conformance only and must not be reported as accuracy.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from backend.app.core.risk.contract_checks import analyze_contract_checks
from backend.app.core.risk.deterministic_cross_checks import run_deterministic_cross_checks
from backend.app.core.risk.risk_playbook import load_playbook

SUITE = ROOT / "data/risk/evaluation/cross_document_v1"
MATRIX = SUITE / "scenario_matrix.jsonl"
MANIFEST = SUITE / "manifest.json"
RESULTS = ROOT / "data/risk/results"
JSONL = RESULTS / "cross_document_model_scenarios.jsonl"
CSV = RESULTS / "cross_document_model_scenarios.csv"
SUMMARY = RESULTS / "cross_document_model_scenarios_summary.json"
SUMMARY_MD = RESULTS / "cross_document_model_scenarios_summary.md"
ANALYZER_CODE = ROOT / "backend/app/core/risk/contract_checks.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_clauses(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    # Split by blank lines or numbered section headings; support both fixture layouts.
    pieces = [piece.strip() for piece in re.split(r"\n\s*\n|(?=^\d+\.\s)", text, flags=re.MULTILINE) if piece.strip()]
    clauses = []
    for piece in pieces:
        if piece.upper().startswith(("SYNTHETIC ", "BALANCED SOFTWARE", "INCOMPLETE AGREEMENT")):
            continue
        if piece.startswith("Constructed solely") or piece.startswith("Synthetic regression") or piece.startswith("Synthetic incomplete"):
            continue
        if piece.startswith("[executed"):
            continue
        heading_match = re.match(r"^\s*\d+\.\s*([^\n.]+)", piece)
        heading = (heading_match.group(1) if heading_match else piece.splitlines()[0]).strip().upper()
        # Use the numbered section heading, not arbitrary words in the body,
        # to avoid labeling a whole section as "LIABILITY" merely because that
        # concept is mentioned inside an IP or assignment provision.
        if "LIQUIDATED DAMAGES" in heading or (heading in {"DAMAGES", "REMEDIES"} and "liquidated damages" in piece.lower()):
            label = "Liquidated Damages"
        elif (heading in {"TERM", "TERM OF AGREEMENT"} and re.search(r"\brenew\w*\b", piece, re.I)) or "TERM AND RENEWAL" in heading or "RENEWAL" in heading:
            label = "Renewal Term"
        elif "IP OWNERSHIP" in heading or "OWNERSHIP AND LICENSE" in heading:
            label = "Ip Ownership Assignment"
        elif "CAP ON LIABILITY" in heading or "LIABILITY CAP" in heading:
            label = "Cap On Liability"
        elif "LIMITATION OF LIABILITY" in heading or heading == "LIABILITY":
            label = "Cap On Liability"
        elif "TERM AND RENEWAL" in heading or "RENEWAL" in heading:
            label = "Renewal Term"
        elif "CONVENIENCE TERMINATION" in heading or "TERMINATION FOR CONVENIENCE" in heading or heading.startswith("EXIT"):
            label = "Termination For Convenience"
        elif "ASSIGNMENT" in heading or heading.startswith("TRANSFER"):
            label = "Anti-Assignment"
        elif "CRITICAL SOFTWARE" in heading or "SOFTWARE CONTINUITY" in heading:
            label = "Source Code Escrow"
        elif "INSURANCE" in heading:
            label = "Insurance"
        elif "INDEMNIFICATION" in heading:
            label = "Indemnification"
        elif "LICENSE" in heading:
            label = "License Grant"
        elif "INCORPORATED" in heading or "ONLINE TERMS" in heading or "ORDER OF PRECEDENCE" in heading or "PRECEDENCE" in heading:
            label = "Governing Law"
        elif "GOVERNING LAW" in heading or "LAW AND DISPUTES" in heading:
            label = "Governing Law"
        else:
            label = "NO_APPLICABLE_LABEL"
        clauses.append({
            "clause_index": len(clauses),
            "predicted_label": label,
            "clause_text": piece,
            "classification_status": "SYNTHETIC_FIXTURE_LABEL",
        })
    if len(clauses) < 3:
        raise ValueError(f"Too few fixture clauses in {path}: {len(clauses)}")
    return clauses


def valid_evidence(findings: list[dict], clauses: list[dict]) -> tuple[bool, int, int]:
    by_id = {int(c["clause_index"]): str(c.get("clause_text") or "") for c in clauses}
    total = 0
    valid = 0
    for finding in findings:
        if finding.get("risk_status") != "POTENTIAL_RISK":
            continue
        evidence = finding.get("evidence") or []
        total += len(evidence)
        for item in evidence:
            try:
                clause_id = int(item.get("clause_id"))
            except (TypeError, ValueError):
                continue
            quote = str(item.get("quote") or "")
            if clause_id in by_id and quote and quote in by_id[clause_id]:
                valid += 1
    return total == valid, valid, total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=["positive", "control", "incomplete"], nargs="*")
    parser.add_argument("--passes", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)

    matrix = [json.loads(x) for x in MATRIX.read_text(encoding="utf-8").splitlines() if x.strip()]
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    scenarios = ["positive", "control", "incomplete"]
    if args.only:
        scenarios = args.only

    existing = []
    seen = set()
    if args.resume and JSONL.exists():
        for line in JSONL.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if (
                row.get("scenario_type") in scenarios
                and row.get("playbook_sha256") == sha(ROOT / "data/risk/commercial_clause_risk_playbook.json")
                and row.get("analyzer_code_sha256") == sha(ANALYZER_CODE)
                and row.get("fixture_sha256") == manifest["fixture_sha256"].get(row.get("scenario_type"))
                and row.get("scenario_matrix_sha256", sha(MATRIX)) == sha(MATRIX)
            ):
                # The builder's manifest includes creation time; if all substantive inputs
                # (playbook, matrix and fixture) match, refresh the manifest pointer without
                # rerunning the costly LLM call.
                row["scenario_suite_manifest_sha256"] = sha(MANIFEST)
                row["scenario_matrix_sha256"] = sha(MATRIX)
                existing.append(row)
                seen.add(row["scenario_id"])
    # Keep results for scenarios not requested so a one-scenario append never
    # destroys prior records for the other fixture types.
    preserved = []
    if JSONL.exists():
        for line in JSONL.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("scenario_type") not in scenarios:
                preserved.append(row)

    playbook = load_playbook()
    playbook_hash = sha(ROOT / "data/risk/commercial_clause_risk_playbook.json")
    analyzer_code_hash = sha(ANALYZER_CODE)
    runner_code_hash = sha(Path(__file__).resolve())
    matrix_by_scenario = {name: [row for row in matrix if row["scenario_type"] == name] for name in scenarios}
    new_rows = list(existing)
    scenario_summaries = []

    for scenario_type in scenarios:
        pending = [row for row in matrix_by_scenario[scenario_type] if row["scenario_id"] not in seen]
        if not pending:
            print(f"[SKIP] {scenario_type}: all rows already checkpointed", flush=True)
            continue

        # One inference call evaluates the full set of X/DOC checks per fixture.
        fixture_path = ROOT / pending[0]["fixture_file"]
        fixture_hash = sha(fixture_path)
        clauses = split_clauses(fixture_path)
        deterministic = run_deterministic_cross_checks(clauses)
        start = time.monotonic()
        cross, document = analyze_contract_checks(
            clauses,
            playbook=playbook,
            passes=max(1, args.passes),
            deterministic_signals=deterministic,
        )
        elapsed = round(time.monotonic() - start, 3)
        actual = {str(item.get("check_id")): item for item in cross + document}
        batch_provenance = next((item.get("provenance") or {} for item in cross + document if item.get("provenance")), {})
        evidence_ok, evidence_valid_count, evidence_total = valid_evidence(cross + document, clauses)

        for item in matrix_by_scenario[scenario_type]:
            finding = actual.get(item["check_id"], {
                "check_id": item["check_id"],
                "risk_status": "INSUFFICIENT_EVIDENCE",
                "answer": "DON'T KNOW",
                "why_flagged": "No output for this check was returned.",
                "evidence": [],
                "clause_ids": [],
            })
            row = {
                **item,
                "observed_status": finding.get("risk_status") or "MISSING",
                "observed_answer": finding.get("answer"),
                "observed_risk_type": finding.get("risk_type"),
                "observed_clause_ids": finding.get("clause_ids") or [],
                "observed_evidence": finding.get("evidence") or [],
                "observed_why_flagged": finding.get("why_flagged") or "",
                "observed_final_score": finding.get("final_score"),
                "observed_severity": finding.get("severity") or finding.get("risk_level"),
                "model_check_batch_size": (finding.get("provenance") or {}).get("check_batch_size", batch_provenance.get("check_batch_size")),
                "model_batches_per_pass": (finding.get("provenance") or {}).get("model_batches_per_pass", batch_provenance.get("model_batches_per_pass")),
                "matches_synthetic_expected_status": (finding.get("risk_status") or "MISSING") == item["expected_status"],
                "all_positive_evidence_exact": evidence_ok,
                "fixture_sha256": fixture_hash,
                "playbook_sha256": playbook_hash,
                "analyzer_code_sha256": analyzer_code_hash,
                "runner_code_sha256": runner_code_hash,
                "scenario_suite_manifest_sha256": sha(MANIFEST),
                "scenario_matrix_sha256": sha(MATRIX),
                "model_name": os.environ.get("RISK_MODEL", "from-backend-config"),
                "passes": max(1, args.passes),
                "inference_seconds_for_fixture": elapsed,
                "label_provenance": "AUTHORED_SYNTHETIC_TEST_STIMULUS_NOT_HUMAN_GOLD",
                "interpretation": "Scenario conformance only; not real-contract accuracy or legal correctness.",
                "run_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            new_rows.append(row)
        scenario_summaries.append({
            "scenario_type": scenario_type,
            "fixture_path": str(fixture_path.relative_to(ROOT)),
            "fixture_sha256": fixture_hash,
            "clause_count": len(clauses),
            "elapsed_seconds": elapsed,
            "cross_findings_returned": len(cross),
            "document_findings_returned": len(document),
            "exact_positive_evidence_count": evidence_valid_count,
            "positive_evidence_count": evidence_total,
            "all_positive_evidence_exact": evidence_ok,
            "model_check_batch_size": batch_provenance.get("check_batch_size"),
            "model_batches_per_pass": batch_provenance.get("model_batches_per_pass"),
        })
        # Durable checkpoint after each scenario completes.
        combined = preserved + new_rows
        with JSONL.open("w", encoding="utf-8") as stream:
            for record in combined:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"[DONE] {scenario_type}: {len(clauses)} clauses, {len(cross)} cross findings, {len(document)} document findings in {elapsed}s", flush=True)

    combined = preserved + new_rows
    with JSONL.open("w", encoding="utf-8") as stream:
        for record in combined:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    # CSV stores the expected/observed decisions; complex evidence remains JSON in a cell.
    columns = [
        "scenario_id", "check_id", "scope", "scenario_type", "risk_domain",
        "expected_status", "observed_status", "matches_synthetic_expected_status",
        "observed_answer", "observed_risk_type", "observed_final_score", "observed_severity",
        "observed_clause_ids", "observed_evidence", "observed_why_flagged",
        "model_check_batch_size", "model_batches_per_pass", "all_positive_evidence_exact", "fixture_file", "fixture_sha256",
        "playbook_sha256", "analyzer_code_sha256", "runner_code_sha256", "scenario_matrix_sha256", "scenario_suite_manifest_sha256", "model_name",
        "passes", "inference_seconds_for_fixture", "label_provenance",
    ]
    rows = []
    for record in combined:
        rows.append({key: json.dumps(record.get(key), ensure_ascii=False) if isinstance(record.get(key), (list, dict)) else record.get(key) for key in columns})
    with CSV.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    # Only count the requested current-playbook rows for the report.
    current_rows = [row for row in combined if row.get("playbook_sha256") == playbook_hash]
    conformance = sum(bool(row.get("matches_synthetic_expected_status")) for row in current_rows)
    conformance_by_type = {}
    for scenario_type in ("positive", "control", "incomplete"):
        subset = [row for row in current_rows if row.get("scenario_type") == scenario_type]
        matched = sum(bool(row.get("matches_synthetic_expected_status")) for row in subset)
        conformance_by_type[scenario_type] = {
            "cases": len(subset),
            "matched": matched,
            "rate": matched / len(subset) if subset else None,
            "observed_status_counts": {
                status: sum(row.get("observed_status") == status for row in subset)
                for status in ("POTENTIAL_RISK", "NO_RISK", "INSUFFICIENT_EVIDENCE", "MISSING")
            },
        }
    conformance_by_check = []
    for check_id in sorted({str(row.get("check_id")) for row in current_rows}):
        subset = [row for row in current_rows if str(row.get("check_id")) == check_id]
        matched = sum(bool(row.get("matches_synthetic_expected_status")) for row in subset)
        conformance_by_check.append({
            "check_id": check_id,
            "scope": subset[0].get("scope") if subset else None,
            "risk_domain": subset[0].get("risk_domain") if subset else None,
            "cases": len(subset),
            "matched": matched,
            "rate": matched / len(subset) if subset else None,
            "expected_statuses": [row.get("expected_status") for row in subset],
            "observed_statuses": [row.get("observed_status") for row in subset],
        })
    summary = {
        "schema_version": 1,
        "status": "COMPLETED" if {row["scenario_type"] for row in current_rows} >= {"positive", "control", "incomplete"} and len(current_rows) >= 39 else "PARTIAL",
        "case_count": len(current_rows),
        "expected_case_count": 39,
        "model_check_batch_size": 4,
        "model_batches_per_pass": 4,
        "scenario_types": {name: sum(row.get("scenario_type") == name for row in current_rows) for name in ("positive", "control", "incomplete")},
        "check_ids_covered": sorted({row.get("check_id") for row in current_rows}),
        "expected_status_counts": {status: sum(row.get("expected_status") == status for row in current_rows) for status in ("POTENTIAL_RISK", "NO_RISK", "INSUFFICIENT_EVIDENCE")},
        "observed_status_counts": {status: sum(row.get("observed_status") == status for row in current_rows) for status in ("POTENTIAL_RISK", "NO_RISK", "INSUFFICIENT_EVIDENCE", "MISSING")},
        "scenario_status_conformance_count": conformance,
        "scenario_status_conformance_rate": conformance / len(current_rows) if current_rows else None,
        "scenario_status_conformance_by_type": conformance_by_type,
        "scenario_status_conformance_by_check": conformance_by_check,
        "metrics_warning": "Scenario-status conformance on synthetic stimuli is not accuracy, precision/recall on real contracts, or legal correctness.",
        "evidence_exact_all": all(bool(row.get("all_positive_evidence_exact")) for row in current_rows),
        "scenario_run_summaries": scenario_summaries,
        "playbook_sha256": playbook_hash,
        "analyzer_code_sha256": analyzer_code_hash,
        "runner_code_sha256": sorted({row.get("runner_code_sha256") for row in current_rows if row.get("runner_code_sha256")})[0] if len({row.get("runner_code_sha256") for row in current_rows if row.get("runner_code_sha256")}) == 1 else sorted({row.get("runner_code_sha256") for row in current_rows if row.get("runner_code_sha256")} ),
        "summary_generator_code_sha256": runner_code_hash,
        "scenario_suite_manifest_sha256": sha(MANIFEST),
        "jsonl_sha256": sha(JSONL),
        "csv_sha256": sha(CSV),
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "COMPLETED" and summary["evidence_exact_all"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
