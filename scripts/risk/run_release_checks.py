#!/usr/bin/env python3
"""Run deterministic Phase 2 release checks and persist outputs/hashes."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "risk" / "results"


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_head() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return None


def main() -> int:
    started_at = datetime.now(timezone.utc)
    env = os.environ.copy()
    venv_site = ROOT / ".venv" / "lib" / "python3.12" / "site-packages"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT), str(ROOT / "backend"), str(venv_site), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    pytest_cmd = shutil.which("pytest")
    if not pytest_cmd:
        raise SystemExit("pytest is not installed; install requirements-dev.txt before release checks.")
    commands = [
        ("compileall", [sys.executable, "-m", "compileall", "-q", "backend/app", "scripts/risk"]),
        ("evaluation_integrity", [sys.executable, "scripts/risk/validate_evaluation_integrity.py"]),
        ("playbook_domain_validation", [sys.executable, "scripts/risk/normalize_playbook_domains.py"]),
        ("team_export", [sys.executable, "scripts/risk/export_team_pack.py"]),
        ("cross_document_scenario_build", [sys.executable, "scripts/risk/build_cross_document_scenario_suite.py"]),
        ("cross_document_scenario_audit", [sys.executable, "scripts/risk/audit_cross_document_scenario_suite.py"]),
        ("cross_document_model_scenarios", [sys.executable, "scripts/risk/run_cross_document_model_scenarios.py", "--passes", "1", "--resume"]),
        ("render_cross_document_model_report", [sys.executable, "scripts/risk/render_cross_document_model_report.py"]),
        ("compare_cross_document_model_runs", [sys.executable, "scripts/risk/compare_cross_document_model_runs.py"]),
        ("upload_smoke_audit_current", [sys.executable, "scripts/risk/audit_smoke_run.py", "--input", "data/risk/results/smoke_upload_api_current_20261009.json", "--suffix", "current"]),
        ("upload_smoke_audit_batching", [sys.executable, "scripts/risk/audit_smoke_run.py", "--input", "data/risk/results/smoke_upload_api_batching_20261009.json", "--suffix", "batching"]),
        ("upload_smoke_audit_post_batching", [sys.executable, "scripts/risk/audit_smoke_run.py", "--input", "data/risk/results/smoke_upload_api_post_batching_20261009.json", "--suffix", "post_batching"]),
        ("upload_smoke_audit_txt_3pass", [sys.executable, "scripts/risk/audit_smoke_run.py"]),
        ("upload_smoke_audit_pdf", [sys.executable, "scripts/risk/audit_smoke_run.py", "--input", "data/risk/results/smoke_upload_api_pdf_result.json", "--suffix", "pdf"]),
        ("upload_smoke_audit_txt_single_pass", [sys.executable, "scripts/risk/audit_smoke_run.py", "--input", "data/risk/results/smoke_upload_api_fast_result.json", "--suffix", "fast"]),
        ("local_hashing_category_baseline", [sys.executable, "scripts/risk/evaluate_local_hashing_baseline.py"]),
        ("phase2_report", [sys.executable, "scripts/risk/report_phase2_experiment.py"]),
        ("backend_tests", [pytest_cmd, "-q", "backend/tests"]),
    ]
    results = []
    for name, command in commands:
        start = time.monotonic()
        proc = subprocess.run(
            command, cwd=ROOT, env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        results.append({
            "name": name,
            "command": command,
            "exit_code": proc.returncode,
            "duration_seconds": round(time.monotonic() - start, 3),
            "passed": proc.returncode == 0,
            "output": proc.stdout[-30000:],
        })
        print(f"[{'PASS' if proc.returncode == 0 else 'FAIL'}] {name} ({results[-1]['duration_seconds']}s)", flush=True)
        if proc.returncode != 0:
            print(proc.stdout[-8000:], flush=True)

    finished_at = datetime.now(timezone.utc)
    inputs = [
        ROOT / "data/risk/EVALUATION_INTEGRITY_REPORT.json",
        ROOT / "data/risk/results/phase2_reproducible_report.json",
        ROOT / "data/risk/results/local_hashing_cuad_index_manifest.json",
        ROOT / "data/risk/results/local_hashing_index_manifest.json",
        ROOT / "data/risk/results/legal_knowledge_retrieval_validation.json",
        ROOT / "data/risk/results/smoke_upload_api_result.json",
        ROOT / "data/risk/results/smoke_test_audit.json",
        ROOT / "data/risk/results/smoke_upload_api_current_20261009.json",
        ROOT / "data/risk/results/smoke_test_audit_current.json",
        ROOT / "data/risk/results/smoke_upload_api_batching_20261009.json",
        ROOT / "data/risk/results/smoke_test_audit_batching.json",
        ROOT / "data/risk/results/smoke_upload_api_post_batching_20261009.json",
        ROOT / "data/risk/results/smoke_test_audit_post_batching.json",
        ROOT / "data/risk/results/smoke_upload_api_fast_result.json",
        ROOT / "data/risk/results/smoke_test_audit_fast.json",
        ROOT / "data/risk/results/smoke_upload_api_pdf_result.json",
        ROOT / "data/risk/results/smoke_test_audit_pdf.json",
        ROOT / "data/risk/results/local_hashing_cuad_retrieval_baseline.json",
        ROOT / "data/risk/results/cross_document_scenario_audit.json",
        ROOT / "data/risk/evaluation/cross_document_v1/scenario_matrix.jsonl",
        ROOT / "data/risk/evaluation/cross_document_v1/manifest.json",
        ROOT / "data/risk/results/cross_document_model_scenarios.jsonl",
        ROOT / "data/risk/results/cross_document_model_scenarios.csv",
        ROOT / "data/risk/results/cross_document_model_scenarios_summary.json",
        ROOT / "data/risk/results/cross_document_model_scenarios_summary.md",
        ROOT / "data/risk/results/cross_document_model_scenario_comparison.json",
        ROOT / "data/risk/results/cross_document_model_scenario_comparison.md",
        ROOT / "scripts/risk/compare_cross_document_model_runs.py",
        ROOT / "scripts/risk/render_cross_document_model_report.py",
        ROOT / "data/risk/team_export/export_manifest.json",
        ROOT / "data/risk/silver/silver_annotations_final_v5_qwen3_gemma3_20261007.csv",
        ROOT / "data/risk/silver/silver_annotations_final_v5_qwen3_gemma3_20261007.jsonl",
        ROOT / "data/risk/commercial_clause_risk_playbook.json",
        ROOT / "backend/data/legal_knowledge/risk_taxonomy.json",
        ROOT / "scripts/risk/smoke_upload_api.py",
        ROOT / "backend/app/core/risk/contract_checks.py",
        ROOT / "scripts/risk/run_cross_document_model_scenarios.py",
        ROOT / "scripts/risk/build_cross_document_scenario_suite.py",
        ROOT / "scripts/risk/audit_cross_document_scenario_suite.py",
        ROOT / "scripts/risk/report_phase2_experiment.py",
        ROOT / "scripts/risk/run_release_checks.py",
        ROOT / "docs/PHASE2_PAPER_DRAFT.md",
        ROOT / "docs/PHASE2_REPRODUCIBILITY.md",
        ROOT / "docs/PHASE2_CLAIM_EVIDENCE_MATRIX.md",
        ROOT / "docs/PHASE2_LOGICAL_MODEL.md",
        ROOT / "data/risk/GOLD_STATUS.md",
        ROOT / "backend/tests/test_contract_checks_batching.py",
    ]
    report = {
        "schema_version": 1,
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": finished_at.isoformat(),
        "elapsed_seconds": round((finished_at - started_at).total_seconds(), 3),
        "git_head_at_run_time": git_head(),
        "status": "PASS" if all(x["passed"] for x in results) else "FAIL",
        "checks": results,
        "hashes": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in inputs
        },
        "interpretation": (
            "Release checks validate code/data invariants and unit behavior. "
            "They do not estimate custom risk accuracy or legal correctness; "
            "human gold remains unavailable."
        ),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "release_validation.json"
    md_path = OUT_DIR / "release_validation.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = [
        "# Phase 2 Release Validation",
        "",
        f"**Status: {report['status']}**",
        f"Started UTC: {report['started_at_utc']}",
        f"Finished UTC: {report['finished_at_utc']}",
        f"Elapsed seconds: {report['elapsed_seconds']}",
        f"Git HEAD: {report['git_head_at_run_time'] or 'unavailable'}",
        "",
        "| Check | Result | Duration (s) |",
        "|---|---:|---:|",
    ]
    summary.extend(
        f"| {item['name']} | {'PASS' if item['passed'] else 'FAIL'} | {item['duration_seconds']} |"
        for item in results
    )
    summary.extend([
        "",
        "## Interpretation",
        "",
        "These checks validate implementation/data integrity, not custom-risk accuracy. Human-gold annotations are still absent. Review captured stdout/stderr in the JSON file for detailed counts and warnings.",
        "",
        "## SHA-256",
        "",
    ])
    summary.extend(f"- {path}: {digest or 'MISSING'}" for path, digest in report["hashes"].items())
    md_path.write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "json": str(json_path.relative_to(ROOT)),
        "markdown": str(md_path.relative_to(ROOT)),
        "checks": [{"name": x["name"], "passed": x["passed"]} for x in results],
    }, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
