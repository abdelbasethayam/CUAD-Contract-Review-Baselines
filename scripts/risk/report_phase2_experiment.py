#!/usr/bin/env python3
"""Rebuild an auditable Phase 2 experiment report without treating silver as gold."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SILVER_DIR = ROOT / "data" / "risk" / "silver"
SILVER_CSV = SILVER_DIR / "silver_annotations_final_v5_qwen3_gemma3_20261007.csv"
SILVER_JSONL = SILVER_DIR / "silver_annotations_final_v5_qwen3_gemma3_20261007.jsonl"
GOLD_CSV = ROOT / "data" / "risk" / "gold" / "gold_annotations.csv"
PLAYBOOK = ROOT / "data" / "risk" / "commercial_clause_risk_playbook.json"
TAXONOMY = ROOT / "backend" / "data" / "legal_knowledge" / "risk_taxonomy.json"
INTEGRITY = ROOT / "data" / "risk" / "EVALUATION_INTEGRITY_REPORT.json"
EXPERT_MANIFEST = ROOT / "data" / "risk" / "external" / "cuad_expert_test.manifest.json"
LOCAL_CUAD_MANIFEST = ROOT / "data" / "risk" / "results" / "local_hashing_cuad_index_manifest.json"
LOCAL_PROFILE_MANIFEST = ROOT / "data" / "risk" / "results" / "local_hashing_index_manifest.json"
LEGAL_RETRIEVAL_VALIDATION = ROOT / "data" / "risk" / "results" / "legal_knowledge_retrieval_validation.json"
LOCAL_HASHING_BASELINE = ROOT / "data" / "risk" / "results" / "local_hashing_cuad_retrieval_baseline.json"
CROSS_DOCUMENT_AUDIT = ROOT / "data" / "risk" / "results" / "cross_document_scenario_audit.json"
CROSS_DOCUMENT_MATRIX = ROOT / "data" / "risk" / "evaluation" / "cross_document_v1" / "scenario_matrix.jsonl"
CROSS_DOCUMENT_MODEL_JSONL = ROOT / "data" / "risk" / "results" / "cross_document_model_scenarios.jsonl"
CROSS_DOCUMENT_MODEL_CSV = ROOT / "data" / "risk" / "results" / "cross_document_model_scenarios.csv"
CROSS_DOCUMENT_MODEL_SUMMARY = ROOT / "data" / "risk" / "results" / "cross_document_model_scenarios_summary.json"
CROSS_DOCUMENT_ANALYZER = ROOT / "backend" / "app" / "core" / "risk" / "contract_checks.py"
CROSS_DOCUMENT_MODEL_RUNNER = ROOT / "scripts" / "risk" / "run_cross_document_model_scenarios.py"
CROSS_DOCUMENT_COMPARISON_JSON = ROOT / "data" / "risk" / "results" / "cross_document_model_scenario_comparison.json"
CROSS_DOCUMENT_COMPARISON_MD = ROOT / "data" / "risk" / "results" / "cross_document_model_scenario_comparison.md"
SMOKE_RUNS = {
    "txt_three_pass": (ROOT / "data/risk/results/smoke_upload_api_result.json", ROOT / "data/risk/results/smoke_test_audit.json"),
    "pdf_three_pass": (ROOT / "data/risk/results/smoke_upload_api_pdf_result.json", ROOT / "data/risk/results/smoke_test_audit_pdf.json"),
    "txt_single_pass": (ROOT / "data/risk/results/smoke_upload_api_fast_result.json", ROOT / "data/risk/results/smoke_test_audit_fast.json"),
    "txt_current_20261009": (ROOT / "data/risk/results/smoke_upload_api_current_20261009.json", ROOT / "data/risk/results/smoke_test_audit_current.json"),
    "txt_post_batching_20261009": (ROOT / "data/risk/results/smoke_upload_api_post_batching_20261009.json", ROOT / "data/risk/results/smoke_test_audit_post_batching.json"),
}
OUT_DIR = ROOT / "data" / "risk" / "results"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{n}: {exc}") from exc
    return rows


def maybe_git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()
    silver_csv = read_csv(SILVER_CSV)
    silver_jsonl = read_jsonl(SILVER_JSONL)
    gold = read_csv(GOLD_CSV)
    playbook = json.loads(PLAYBOOK.read_text(encoding="utf-8"))
    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    integrity = json.loads(INTEGRITY.read_text(encoding="utf-8"))
    expert = json.loads(EXPERT_MANIFEST.read_text(encoding="utf-8"))
    local_cuad = json.loads(LOCAL_CUAD_MANIFEST.read_text(encoding="utf-8")) if LOCAL_CUAD_MANIFEST.exists() else None
    local_profile = json.loads(LOCAL_PROFILE_MANIFEST.read_text(encoding="utf-8")) if LOCAL_PROFILE_MANIFEST.exists() else None
    legal_retrieval = json.loads(LEGAL_RETRIEVAL_VALIDATION.read_text(encoding="utf-8")) if LEGAL_RETRIEVAL_VALIDATION.exists() else None
    local_hashing_baseline = json.loads(LOCAL_HASHING_BASELINE.read_text(encoding="utf-8")) if LOCAL_HASHING_BASELINE.exists() else None
    cross_document_audit = json.loads(CROSS_DOCUMENT_AUDIT.read_text(encoding="utf-8")) if CROSS_DOCUMENT_AUDIT.exists() else None
    cross_document_model_summary = json.loads(CROSS_DOCUMENT_MODEL_SUMMARY.read_text(encoding="utf-8")) if CROSS_DOCUMENT_MODEL_SUMMARY.exists() else None
    cross_document_comparison = json.loads(CROSS_DOCUMENT_COMPARISON_JSON.read_text(encoding="utf-8")) if CROSS_DOCUMENT_COMPARISON_JSON.exists() else None
    smoke_run_summaries = {}
    for run_name, (result_path, audit_path) in SMOKE_RUNS.items():
        if result_path.exists() and audit_path.exists():
            smoke_result = json.loads(result_path.read_text(encoding="utf-8"))
            smoke_audit = json.loads(audit_path.read_text(encoding="utf-8"))
            response = smoke_result.get("response") or {}
            audit_summary = smoke_audit.get("summary") or {}
            smoke_run_summaries[run_name] = {
                "result_path": str(result_path.relative_to(ROOT)),
                "audit_path": str(audit_path.relative_to(ROOT)),
                "result_sha256": sha256(result_path),
                "audit_sha256": sha256(audit_path),
                "http_status": smoke_result.get("http_status"),
                "elapsed_seconds": smoke_result.get("elapsed_seconds"),
                "analysis_id": smoke_result.get("analysis_id"),
                "pipeline_status": response.get("pipeline_status") or audit_summary.get("pipeline_status"),
                "clause_count": response.get("total_clauses") or audit_summary.get("clause_count"),
                "risk_self_consistency_passes": (smoke_audit.get("pipeline_config") or {}).get("risk_self_consistency_passes"),
                "clause_risk_finding_count": audit_summary.get("clause_risk_finding_count"),
                "cross_clause_finding_count": audit_summary.get("cross_clause_finding_count"),
                "document_finding_count": audit_summary.get("document_finding_count"),
                "overall_status": audit_summary.get("overall_status"),
                "overall_risk": audit_summary.get("overall_risk"),
                "audit_status": smoke_audit.get("status"),
                "audit_passed": bool(smoke_audit.get("checks")) and all(bool(value) for value in smoke_audit.get("checks", {}).values()) and not smoke_audit.get("failed_checks"),
                "not_an_accuracy_measurement": True,
            }

    ids_csv = [str(row.get("sample_id") or "") for row in silver_csv]
    ids_jsonl = [str(row.get("sample_id") or "") for row in silver_jsonl]
    status_counts = Counter(str(row.get("silver_status") or "MISSING") for row in silver_csv)
    risk_counts = Counter(str(row.get("silver_risk") or "MISSING").upper() for row in silver_csv)
    partition_counts = Counter(str(row.get("annotation_partition") or "MISSING") for row in silver_csv)
    protocol_counts = Counter(str(row.get("protocol_version") or "MISSING") for row in silver_csv)
    ids_unique = len(set(ids_csv)) == len(ids_csv)
    csv_jsonl_same_ids = sorted(ids_csv) == sorted(ids_jsonl)
    evidence_yes = [row for row in silver_csv if str(row.get("silver_risk") or "").upper() == "YES"]
    evidence_valid_yes = [
        row for row in evidence_yes
        if str(row.get("silver_evidence") or "")
        and str(row.get("silver_evidence") or "") in str(row.get("clause_text") or "")
    ]
    domain_set = {
        str(item.get("risk_domain"))
        for item in taxonomy.get("risk_domains") or []
        if item.get("risk_domain")
    }
    all_checks = []
    for clause_type, entry in (playbook.get("clause_types") or {}).items():
        for item in entry.get("checklist") or []:
            all_checks.append((clause_type, item))
    cross_checks = list(playbook.get("cross_clause_checks") or [])
    doc_checks = list(playbook.get("document_level_checks") or [])
    every_check = [item for _, item in all_checks] + cross_checks + doc_checks
    missing_domains = [
        {"id": item.get("id"), "domain": item.get("risk_domain")}
        for item in every_check
        if item.get("risk_domain") not in domain_set
    ]

    filled_risk = sum(bool(str(row.get("gold_risk") or "").strip()) for row in gold)
    filled_evidence = sum(bool(str(row.get("gold_evidence") or "").strip()) for row in gold)
    integrity_checks = integrity.get("checks") or []
    integrity_passed = sum(bool(item.get("passed")) for item in integrity_checks)

    checks = {
        "silver_csv_has_300_rows": len(silver_csv) == 300,
        "silver_jsonl_has_300_rows": len(silver_jsonl) == 300,
        "silver_sample_ids_unique": ids_unique,
        "silver_csv_jsonl_ids_match": csv_jsonl_same_ids,
        "silver_partitions_expected": partition_counts == {
            "locked_test": 150, "calibration": 75, "development": 75
        },
        "all_114_playbook_checks_have_canonical_domains": len(every_check) == 114 and not missing_domains,
        "all_existing_integrity_checks_pass": bool(integrity_checks) and integrity_passed == len(integrity_checks),
        "human_gold_still_unannotated": filled_risk == 0 and filled_evidence == 0,
        "every_machine_yes_has_exact_clause_quote": len(evidence_yes) == len(evidence_valid_yes),
        "cross_document_synthetic_matrix_passes": bool(cross_document_audit) and cross_document_audit.get("status") == "PASS" and cross_document_audit.get("case_count") == 39,
        "cross_document_model_scenarios_complete": bool(cross_document_model_summary) and cross_document_model_summary.get("status") == "COMPLETED" and cross_document_model_summary.get("case_count") == 39 and bool(cross_document_model_summary.get("evidence_exact_all")),
        "cross_document_model_analyzer_hash_current_and_runner_traced": bool(cross_document_model_summary) and cross_document_model_summary.get("analyzer_code_sha256") == sha256(CROSS_DOCUMENT_ANALYZER) and bool(cross_document_model_summary.get("runner_code_sha256")) and cross_document_model_summary.get("summary_generator_code_sha256") == sha256(CROSS_DOCUMENT_MODEL_RUNNER),
        "cross_document_batching_ablation_complete": bool(cross_document_comparison) and cross_document_comparison.get("status") == "COMPLETED" and cross_document_comparison.get("case_count") == 39 and cross_document_comparison.get("same_case_set") is True and len(cross_document_comparison.get("status_changes", [])) <= 39,
        "five_recorded_upload_smoke_audits_pass": len(smoke_run_summaries) == 5 and all(item["audit_passed"] for item in smoke_run_summaries.values()),
    }
    failed = [name for name, passed in checks.items() if not passed]

    report = {
        "report_version": "phase2-reproducible-report-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head_at_report_time": maybe_git_commit(),
        "interpretation_warning": (
            "This report describes pipeline integrity, machine-silver behavior and operational evidence. "
            "It does not calculate custom-risk accuracy because no human gold annotations exist."
        ),
        "reproduction_inputs": {
            "silver_csv": str(SILVER_CSV.relative_to(ROOT)),
            "silver_jsonl": str(SILVER_JSONL.relative_to(ROOT)),
            "gold_template": str(GOLD_CSV.relative_to(ROOT)),
            "playbook": str(PLAYBOOK.relative_to(ROOT)),
            "taxonomy": str(TAXONOMY.relative_to(ROOT)),
            "integrity_report": str(INTEGRITY.relative_to(ROOT)),
            "external_cuad_manifest": str(EXPERT_MANIFEST.relative_to(ROOT)),
            "local_hashing_cuad_index_manifest": str(LOCAL_CUAD_MANIFEST.relative_to(ROOT)) if LOCAL_CUAD_MANIFEST.exists() else None,
            "local_hashing_profile_manifest": str(LOCAL_PROFILE_MANIFEST.relative_to(ROOT)) if LOCAL_PROFILE_MANIFEST.exists() else None,
            "legal_knowledge_retrieval_validation": str(LEGAL_RETRIEVAL_VALIDATION.relative_to(ROOT)) if LEGAL_RETRIEVAL_VALIDATION.exists() else None,
            "local_hashing_cuad_retrieval_baseline": str(LOCAL_HASHING_BASELINE.relative_to(ROOT)) if LOCAL_HASHING_BASELINE.exists() else None,
            "cross_document_scenario_matrix": str(CROSS_DOCUMENT_MATRIX.relative_to(ROOT)) if CROSS_DOCUMENT_MATRIX.exists() else None,
            "cross_document_scenario_audit": str(CROSS_DOCUMENT_AUDIT.relative_to(ROOT)) if CROSS_DOCUMENT_AUDIT.exists() else None,
            "cross_document_model_scenarios_jsonl": str(CROSS_DOCUMENT_MODEL_JSONL.relative_to(ROOT)) if CROSS_DOCUMENT_MODEL_JSONL.exists() else None,
            "cross_document_model_scenarios_csv": str(CROSS_DOCUMENT_MODEL_CSV.relative_to(ROOT)) if CROSS_DOCUMENT_MODEL_CSV.exists() else None,
            "cross_document_model_scenarios_summary": str(CROSS_DOCUMENT_MODEL_SUMMARY.relative_to(ROOT)) if CROSS_DOCUMENT_MODEL_SUMMARY.exists() else None,
            "upload_smoke_runs": {name: {"result": str(paths[0].relative_to(ROOT)), "audit": str(paths[1].relative_to(ROOT))} for name, paths in SMOKE_RUNS.items()},
        },
        "hashes": {
            "silver_csv_sha256": sha256(SILVER_CSV),
            "silver_jsonl_sha256": sha256(SILVER_JSONL),
            "gold_template_sha256": sha256(GOLD_CSV),
            "playbook_sha256": sha256(PLAYBOOK),
            "taxonomy_sha256": sha256(TAXONOMY),
            "integrity_report_sha256": sha256(INTEGRITY),
            "external_cuad_manifest_sha256": sha256(EXPERT_MANIFEST),
            "local_hashing_cuad_index_manifest_sha256": sha256(LOCAL_CUAD_MANIFEST) if LOCAL_CUAD_MANIFEST.exists() else None,
            "local_hashing_profile_manifest_sha256": sha256(LOCAL_PROFILE_MANIFEST) if LOCAL_PROFILE_MANIFEST.exists() else None,
            "legal_knowledge_retrieval_validation_sha256": sha256(LEGAL_RETRIEVAL_VALIDATION) if LEGAL_RETRIEVAL_VALIDATION.exists() else None,
            "local_hashing_cuad_retrieval_baseline_sha256": sha256(LOCAL_HASHING_BASELINE) if LOCAL_HASHING_BASELINE.exists() else None,
            "cross_document_scenario_matrix_sha256": sha256(CROSS_DOCUMENT_MATRIX) if CROSS_DOCUMENT_MATRIX.exists() else None,
            "cross_document_scenario_audit_sha256": sha256(CROSS_DOCUMENT_AUDIT) if CROSS_DOCUMENT_AUDIT.exists() else None,
            "cross_document_model_scenarios_jsonl_sha256": sha256(CROSS_DOCUMENT_MODEL_JSONL) if CROSS_DOCUMENT_MODEL_JSONL.exists() else None,
            "cross_document_model_scenarios_csv_sha256": sha256(CROSS_DOCUMENT_MODEL_CSV) if CROSS_DOCUMENT_MODEL_CSV.exists() else None,
            "cross_document_model_scenarios_summary_sha256": sha256(CROSS_DOCUMENT_MODEL_SUMMARY) if CROSS_DOCUMENT_MODEL_SUMMARY.exists() else None,
            "cross_document_model_scenario_comparison_json_sha256": sha256(CROSS_DOCUMENT_COMPARISON_JSON) if CROSS_DOCUMENT_COMPARISON_JSON.exists() else None,
            "cross_document_model_scenario_comparison_md_sha256": sha256(CROSS_DOCUMENT_COMPARISON_MD) if CROSS_DOCUMENT_COMPARISON_MD.exists() else None,
            "cross_document_analyzer_code_sha256": sha256(CROSS_DOCUMENT_ANALYZER),
            "cross_document_runner_code_sha256": sha256(CROSS_DOCUMENT_MODEL_RUNNER),
            "upload_smoke_run_hashes": {name: {"result_sha256": sha256(paths[0]), "audit_sha256": sha256(paths[1])} for name, paths in SMOKE_RUNS.items() if paths[0].exists() and paths[1].exists()},
        },
        "upload_smoke_tests": {
            "interpretation": "Pipeline integration diagnostics only; synthetic/repository fixtures do not measure risk accuracy or legal correctness.",
            "runs": smoke_run_summaries,
        },
        "cross_document_synthetic_evaluation": {
            "interpretation": "Authored synthetic scenario matrix for regression/coverage; not human gold and not a measure of risk accuracy or generalization.",
            "audit": cross_document_audit,
            "matrix_path": str(CROSS_DOCUMENT_MATRIX.relative_to(ROOT)) if CROSS_DOCUMENT_MATRIX.exists() else None,
            "matrix_sha256": sha256(CROSS_DOCUMENT_MATRIX) if CROSS_DOCUMENT_MATRIX.exists() else None,
            "model_execution": cross_document_model_summary,
            "model_jsonl_path": str(CROSS_DOCUMENT_MODEL_JSONL.relative_to(ROOT)) if CROSS_DOCUMENT_MODEL_JSONL.exists() else None,
            "model_csv_path": str(CROSS_DOCUMENT_MODEL_CSV.relative_to(ROOT)) if CROSS_DOCUMENT_MODEL_CSV.exists() else None,
            "batching_ablation_comparison": cross_document_comparison,
            "batching_ablation_comparison_path": str(CROSS_DOCUMENT_COMPARISON_JSON.relative_to(ROOT)) if CROSS_DOCUMENT_COMPARISON_JSON.exists() else None,
            "batching_ablation_comparison_markdown_path": str(CROSS_DOCUMENT_COMPARISON_MD.relative_to(ROOT)) if CROSS_DOCUMENT_COMPARISON_MD.exists() else None,
        },
        "retrieval_profile": {
            "active_server_embedding_backend": "local_hashing" if local_profile and local_profile.get("status") == "PASS" else None,
            "description": "Deterministic 768-dimensional HashingVectorizer lexical-vector baseline; do not compare its retrieval behavior as equivalent to Cohere Embed v3 semantic embeddings.",
            "cuad_train_index": local_cuad,
            "local_profile_validation": local_profile,
            "legal_knowledge_validation": legal_retrieval,
            "local_hashing_cuad_retrieval_baseline": local_hashing_baseline,
        },
        "datasets": {
            "split": {
                "train_contracts": integrity.get("train_contracts"),
                "test_contracts": integrity.get("test_contracts"),
                "train_clause_rows": integrity.get("train_rows"),
                "test_clause_rows": integrity.get("test_rows"),
            },
            "silver": {
                "rows": len(silver_csv),
                "unique_samples": len(set(ids_csv)),
                "unique_contracts": len({row.get("document_id") for row in silver_csv}),
                "unique_checks": len({row.get("check_id") for row in silver_csv}),
                "partitions": dict(partition_counts),
                "statuses": dict(status_counts),
                "risk_decisions": dict(risk_counts),
                "protocols": dict(protocol_counts),
                "machine_yes_rows": len(evidence_yes),
                "machine_yes_with_exact_evidence": len(evidence_valid_yes),
                "machine_yes_evidence_rate": (
                    len(evidence_valid_yes) / len(evidence_yes) if evidence_yes else None
                ),
                "direct_machine_agreement_rate": status_counts.get("MACHINE_AGREED", 0) / len(silver_csv) if silver_csv else None,
                "agreement_including_agreed_uncertain_rate": (
                    (status_counts.get("MACHINE_AGREED", 0) + status_counts.get("MACHINE_AGREED_UNCERTAIN", 0)) / len(silver_csv)
                    if silver_csv else None
                ),
                "disagreement_rate": status_counts.get("MACHINE_DISAGREEMENT", 0) / len(silver_csv) if silver_csv else None,
                "evidence_invalid_agreement_rate": status_counts.get("MACHINE_AGREED_BUT_EVIDENCE_INVALID", 0) / len(silver_csv) if silver_csv else None,
                "custom_risk_accuracy": None,
                "custom_risk_accuracy_reason": "No human gold risk labels are available.",
            },
            "human_gold": {
                "queue_rows": len(gold),
                "filled_risk_labels": filled_risk,
                "filled_evidence_spans": filled_evidence,
                "status": "PENDING_HUMAN_ADJUDICATION" if filled_risk == 0 and filled_evidence == 0 else "PARTIALLY_ANNOTATED",
            },
            "external_cuad": {
                "task_count": expert.get("task_count"),
                "contract_count": expert.get("test_contract_count"),
                "category_count": expert.get("category_count"),
                "answerable_tasks": expert.get("answerable_tasks"),
                "impossible_tasks": expert.get("impossible_tasks"),
                "allowed_claim": "CUAD clause/evidence behavior only; not custom risk-predicate, severity or legal-correctness ground truth.",
            },
            "playbook": {
                "clause_type_count": len(playbook.get("clause_types") or {}),
                "clause_check_count": len(all_checks),
                "cross_clause_check_count": len(cross_checks),
                "document_check_count": len(doc_checks),
                "canonical_domain_count": len(domain_set),
                "missing_domain_mappings": missing_domains,
                "source_version": playbook.get("source_version", playbook.get("version")),
            },
            "integrity": {
                "checks_total": len(integrity_checks),
                "checks_passed": integrity_passed,
                "all_passed": bool(integrity_checks) and integrity_passed == len(integrity_checks),
                "checks": integrity_checks,
            },
        },
        "validation": {
            "checks": checks,
            "failed_checks": failed,
            "status": "PASS" if not failed else "FAIL",
        },
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "phase2_reproducible_report.json"
    md_path = args.out_dir / "phase2_reproducible_report.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    silver = report["datasets"]["silver"]
    play = report["datasets"]["playbook"]
    gold_info = report["datasets"]["human_gold"]
    if local_hashing_baseline:
        baseline_metrics = local_hashing_baseline["metrics"]
        baseline_isolation = local_hashing_baseline["isolation"]
        local_hashing_baseline_md = (
            f"- Train/test contract overlap: {baseline_isolation['train_test_contract_overlap']}.\n"
            f"- Indexed training clauses: {baseline_isolation['train_eligible_rows']} from {baseline_isolation['train_contract_count']} contracts.\n"
            f"- Held-out test clauses: {baseline_isolation['test_eligible_rows']} from {baseline_isolation['test_contract_count']} contracts.\n"
            f"- 1-NN accuracy / Recall@1: {baseline_metrics['nearest_neighbor_accuracy']:.4f}.\n"
            f"- Macro-F1: {baseline_metrics['nearest_neighbor_macro_f1']:.4f}.\n"
            f"- Recall@5: {baseline_metrics['recall_at_5']:.4f}; MRR@5: {baseline_metrics['mrr_at_5']:.4f}.\n"
            f"- Contract-cluster bootstrap 95% CI for accuracy: {baseline_metrics['nearest_neighbor_accuracy_contract_bootstrap_95_ci']['lower_95']:.4f} to {baseline_metrics['nearest_neighbor_accuracy_contract_bootstrap_95_ci']['upper_95']:.4f}.\n"
            f"- Contract-cluster bootstrap 95% CI for macro-F1: {baseline_metrics['nearest_neighbor_macro_f1_contract_bootstrap_95_ci']['lower_95']:.4f} to {baseline_metrics['nearest_neighbor_macro_f1_contract_bootstrap_95_ci']['upper_95']:.4f}.\n\n"
            "This is a deterministic lexical-vector nearest-neighbor clause-category baseline, not custom-risk accuracy and not equivalent to the prior Cohere-plus-SLM system. "
            "Full per-category metrics are in data/risk/results/local_hashing_cuad_retrieval_baseline.json and can be regenerated with scripts/risk/evaluate_local_hashing_baseline.py."
        )
    else:
        local_hashing_baseline_md = "Evaluation is unavailable because the local-hashing CUAD baseline JSON is missing."
    smoke_names = {
        "txt_three_pass": "Synthetic TXT (3 passes)",
        "pdf_three_pass": "Repository PDF fixture (3 passes)",
        "txt_single_pass": "Synthetic TXT (1 pass)",
    }
    smoke_md_rows = []
    for run_name, item in smoke_run_summaries.items():
        smoke_md_rows.append(
            f"| {smoke_names.get(run_name, run_name)} | {item.get('http_status')} | "
            f"{item.get('pipeline_status')} | {item.get('clause_count')} | "
            f"{item.get('risk_self_consistency_passes')} | {float(item.get('elapsed_seconds') or 0):.1f} s | "
            f"{'PASS' if item.get('audit_passed') else 'FAIL'} |"
        )
    smoke_md_table = "\n".join(smoke_md_rows) or "| No recorded smoke runs | — | — | — | — | — | — |"
    md = f"""# Phase 2 Reproducible Experiment Report

**Validation: {report['validation']['status']}**  
Generated (UTC): {report['generated_at_utc']}  
Git HEAD at report time: {report['git_head_at_report_time'] or 'unavailable'}

> This report is not a legal correctness evaluation. Custom-risk accuracy remains unavailable because the human gold queue has no adjudicated labels.

## Dataset and integrity

| Item | Result |
|---|---:|
| Train contracts | {report['datasets']['split']['train_contracts']} |
| Held-out test contracts | {report['datasets']['split']['test_contracts']} |
| Train clause rows | {report['datasets']['split']['train_clause_rows']} |
| Test clause rows | {report['datasets']['split']['test_clause_rows']} |
| Integrity checks passing | {integrity_passed}/{len(integrity_checks)} |
| Clause-level playbook checks | {play['clause_check_count']} |
| Cross-clause checks | {play['cross_clause_check_count']} |
| Document checks | {play['document_check_count']} |
| Canonical taxonomy domains | {play['canonical_domain_count']} |
| Human-risk labels filled | {filled_risk}/{len(gold)} |
| Human-evidence spans filled | {filled_evidence}/{len(gold)} |

## Machine-silver results (diagnostics only)

| Machine status | Count |
|---|---:|
""" + "\n".join(f"| {name} | {count} |" for name, count in status_counts.items()) + f"""

| Decision | Count |
|---|---:|
""" + "\n".join(f"| {name} | {count} |" for name, count in risk_counts.items()) + f"""

Direct model agreement rate: {silver['direct_machine_agreement_rate']:.3f}  
Agreement including agreed-uncertain: {silver['agreement_including_agreed_uncertain_rate']:.3f}  
Disagreement rate: {silver['disagreement_rate']:.3f}  
Machine YES cases with exact contiguous evidence: {silver['machine_yes_with_exact_evidence']}/{silver['machine_yes_rows']}

These are machine-consensus and evidence-gate diagnostics, **not accuracy, precision, recall, or human agreement**. The models can agree and still be wrong.

## Split policy and experiment controls

- Train and test are contract-disjoint (410 / 100 contracts).
- Human gold queue plan: development 75, calibration 75, locked test 150; all annotation fields are currently blank.
- The separate machine-silver set has the same partition sizes. A quarantined 30-case locked-test pilot was not used for tuning; the protocol used for parameter diagnostics was limited to calibration/development.
- No custom-risk fine-tuning was performed.
- Exact playbook/taxonomy/hash inputs are recorded in the JSON report.
- Machine-silver is reproducible by running the recorded adjudication script with the pinned model names, server URLs, queue, and protocol settings, but LLM outputs can still vary across Ollama/model/library versions. The committed raw outputs and hashes are the authoritative record of this completed run.

## Comparability with existing repository results

| Existing experiment | Reported outcome | What it measures | Comparable as custom-risk accuracy? |
|---|---:|---|---|
| Phase 1 accepted paper — retrieval-conditioned SLM | 66.41% accuracy / 51.72% macro-F1 | CUAD clause-category classification on 1,679 held-out clauses | No |
| Phase 1 zero-shot baseline | 35.80% accuracy / 31.41% macro-F1 | Same Phase 1 clause-category target | No |
| Phase 1 random few-shot baseline | 50.98% accuracy / 40.93% macro-F1 | Same Phase 1 clause-category target | No |
| Fixed-10 CUAD classifier / RAG pilot | 4/10 = 0.40 | CUAD clause category prediction, 10-row pilot | No |
| Fixed-10 hybrid retrieval pilot | 5/10 = 0.50 accuracy; Recall@5 = 0.60 | Candidate retrieval and clause classification, 10-row pilot | No |
| Fixed-10 k-NN majority pilot | 6/10 = 0.60 | CUAD label prediction, 10-row pilot | No |
| Phase 2 two-model silver | YES={risk_counts.get('YES', 0)}, NO={risk_counts.get('NO', 0)}, UNCERTAIN={risk_counts.get('UNCERTAIN', 0)} | Custom risk-predicate outputs without human gold | No |
| External CUAD expert annotations | {expert.get('task_count')} contract/category tasks | CUAD category/evidence benchmark | No, not custom risk gold |

The old repository artifact under data/metadata/rag_pipeline_results.json reports exact-match 0.0 on a metadata-heavy retrieval task; it is not used as a baseline for Phase 2 risk decisions. Published/custom-risk metrics are not blended across different target definitions.

## Upload smoke tests (pipeline validation only)

| Run | HTTP | Pipeline | Clauses | Passes | Runtime | Evidence/artifact audit |
|---|---:|---|---:|---:|---:|---|
{smoke_md_table}

These repository/synthetic fixtures demonstrate the request-to-result path, source-hash preservation, evidence checks, and artifact creation. They are not representative samples and do not measure risk accuracy or legal correctness. The single-pass TXT timing is one observed run, not a throughput benchmark.

## Active server retrieval profile

- Profile: {report['retrieval_profile']['active_server_embedding_backend'] or 'not verified from local index manifests'}.
- Embedding: deterministic 768-dimensional scikit-learn HashingVectorizer with unigrams/bigrams and L2 normalization. It is a lexical-vector baseline, not equivalent to Cohere Embed v3's pretrained semantic embeddings.
- CUAD index: {local_cuad.get('counts', {}).get('indexed_points', 'not available') if local_cuad else 'manifest missing'} train-only points. Index build manifest: data/risk/results/local_hashing_cuad_index_manifest.json.
- Combined local index validation: {local_profile.get('status', 'not available') if local_profile else 'manifest missing'}; manifests at data/risk/results/local_hashing_index_manifest.json.
- Representative legal-guidance retrieval: {legal_retrieval.get('status', 'not available') if legal_retrieval else 'result missing'} across {legal_retrieval.get('case_count', 0) if legal_retrieval else 0} query fixtures. This validates pipeline integration, not legal correctness.

## Local hashing held-out CUAD category baseline

{local_hashing_baseline_md}

## Reproduce

From repository root:

1. Install dependencies and configure backend/.env; do not commit credentials.
2. Build the document-disjoint split and train-only Qdrant collections as documented in the root README.
3. Start Ollama and the backend using scripts/start_all.sh (or scripts/start_backend.sh and scripts/start_frontend.sh separately).
4. Upload a PDF/TXT through the frontend or POST to /documents/classify. The run writes a source hash, configuration/playbook/calibration hashes, checkpoints, trace, clause findings, cross/document checks, and final JSON.
5. Rebuild this silver report:

   python scripts/risk/report_phase2_experiment.py

6. Stop the backend before rebuilding embedded Qdrant indexes, then run `bash scripts/risk/build_local_retrieval_profile.sh`; restart with `bash scripts/start_all.sh`.
7. Run tests from repository root:

   `PYTHONPATH="$PWD:$PWD/backend:$PWD/.venv/lib/python3.12/site-packages" .venv/bin/python -m pytest -q backend/tests`.

## SHA-256

- Silver CSV: {report['hashes']['silver_csv_sha256']}
- Silver JSONL: {report['hashes']['silver_jsonl_sha256']}
- Playbook: {report['hashes']['playbook_sha256']}
- Taxonomy: {report['hashes']['taxonomy_sha256']}
- Integrity report: {report['hashes']['integrity_report_sha256']}

## Scope of claims

Supported now: implementation/reproducibility, train/test leakage checks, exact-quote gating behavior, deterministic domain routing, and machine-silver disagreement/abstention diagnostics.  
Not supported now: custom-risk accuracy, legal correctness, severity calibration validity, probability calibration validity, or cross-clause/document risk sensitivity on real expert-labeled cases.
"""
    md_path.write_text(md, encoding="utf-8")
    print(json.dumps({
        "status": report["validation"]["status"],
        "failed_checks": failed,
        "json_report": str(json_path.relative_to(ROOT)),
        "markdown_report": str(md_path.relative_to(ROOT)),
        "silver_rows": len(silver_csv),
        "gold_filled": filled_risk,
        "domain_mappings": len(every_check) - len(missing_domains),
        "integrity_passed": f"{integrity_passed}/{len(integrity_checks)}",
    }, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
