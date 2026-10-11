#!/usr/bin/env python3
"""Build a traceable, minimal release pack for the Phase 2 risk system."""
from __future__ import annotations
import hashlib, json, zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data/risk/releases"
STAMP = "20261009"
ZIP_PATH = OUT_DIR / f"phase2_reproducible_release_{STAMP}.zip"
MANIFEST_PATH = OUT_DIR / f"phase2_reproducible_release_{STAMP}.manifest.json"

FILES = [
    "docs/PHASE2_PAPER_DRAFT.md",
    "docs/PHASE2_REPRODUCIBILITY.md",
    "docs/PHASE2_CLAIM_EVIDENCE_MATRIX.md",
    "docs/PHASE2_LOGICAL_MODEL.md",
    "data/risk/GOLD_STATUS.md",
    "data/risk/EVALUATION_PROTOCOL.md",
    "data/risk/EVALUATION_INTEGRITY_REPORT.json",
    "data/risk/commercial_clause_risk_playbook.json",
    "backend/data/legal_knowledge/risk_taxonomy.json",
    "backend/data/legal_knowledge/source_registry.json",
    "data/risk/gold/annotation_queue.csv",
    "data/risk/gold/gold_annotations.csv",
    "data/risk/silver/silver_annotations_final_v5_qwen3_gemma3_20261007.csv",
    "data/risk/silver/silver_annotations_final_v5_qwen3_gemma3_20261007.jsonl",
    "data/risk/silver/silver_annotations_final_v5_summary.json",
    "data/risk/external/cuad_expert_test.jsonl",
    "data/risk/external/cuad_expert_test.manifest.json",
    "data/risk/evaluation/cross_document_v1/scenario_matrix.jsonl",
    "data/risk/evaluation/cross_document_v1/manifest.json",
    "data/risk/evaluation/cross_document_v1/positive_risk_stress_contract.txt",
    "data/risk/evaluation/cross_document_v1/protected_control_contract.txt",
    "data/risk/evaluation/cross_document_v1/incomplete_contract_pack.txt",
    "data/risk/evaluation/cross_document_v1/archive/cross_document_model_scenarios_pre_batching_20261009.jsonl",
    "data/risk/evaluation/cross_document_v1/archive/cross_document_model_scenarios.csv_pre_batching_20261009.csv",
    "data/risk/evaluation/cross_document_v1/archive/cross_document_model_scenarios_summary.json_pre_batching_20261009.json",
    "data/risk/results/cross_document_scenario_audit.json",
    "data/risk/results/cross_document_scenario_audit.md",
    "data/risk/results/cross_document_model_scenarios.jsonl",
    "data/risk/results/cross_document_model_scenarios.csv",
    "data/risk/results/cross_document_model_scenarios_summary.json",
    "data/risk/results/cross_document_model_scenarios_summary.md",
    "data/risk/results/cross_document_model_scenario_comparison.json",
    "data/risk/results/cross_document_model_scenario_comparison.md",
    "data/risk/results/smoke_upload_api_current_20261009.json",
    "data/risk/results/smoke_test_audit_current.json",
    "data/risk/results/smoke_test_audit_current.md",
    "data/risk/results/smoke_upload_api_post_batching_20261009.json",
    "data/risk/results/smoke_upload_api_batching_20261009.json",
    "data/risk/results/smoke_test_audit_batching.json",
    "data/risk/results/smoke_test_audit_post_batching.json",
    "data/risk/results/smoke_test_audit_post_batching.md",
    "data/risk/results/smoke_upload_api_result.json",
    "data/risk/results/smoke_test_audit.json",
    "data/risk/results/smoke_test_audit.md",
    "data/risk/results/smoke_upload_api_fast_result.json",
    "data/risk/results/smoke_test_audit_fast.json",
    "data/risk/results/smoke_test_audit_fast.md",
    "data/risk/results/smoke_upload_api_pdf_result.json",
    "data/risk/results/smoke_test_audit_pdf.json",
    "data/risk/results/smoke_test_audit_pdf.md",
    "data/risk/results/local_hashing_cuad_retrieval_baseline.json",
    "data/risk/results/local_hashing_cuad_index_manifest.json",
    "data/risk/results/local_hashing_index_manifest.json",
    "data/risk/results/legal_knowledge_retrieval_validation.json",
    "data/risk/results/phase2_reproducible_report.json",
    "data/risk/results/phase2_reproducible_report.md",
    "data/risk/results/release_validation.json",
    "data/risk/results/release_validation.md",
    "data/risk/team_export/README.md",
    "data/risk/team_export/export_manifest.json",
    "data/risk/team_export/risk_playbook_exact.json",
    "data/risk/team_export/risk_clause_checks.csv",
    "data/risk/team_export/risk_cross_clause_checks.csv",
    "data/risk/team_export/risk_document_checks.csv",
    "data/risk/team_export/risk_taxonomy.json",
    "data/risk/team_export/source_registry.json",
    "scripts/risk/package_phase2_release.py",
    "scripts/risk/run_cross_document_model_scenarios.py",
    "scripts/risk/compare_cross_document_model_runs.py",
    "scripts/risk/render_cross_document_model_report.py",
    "scripts/risk/build_cross_document_scenario_suite.py",
    "scripts/risk/audit_cross_document_scenario_suite.py",
    "scripts/risk/normalize_playbook_domains.py",
    "scripts/risk/export_team_pack.py",
    "scripts/risk/validate_evaluation_integrity.py",
    "scripts/risk/report_phase2_experiment.py",
    "scripts/risk/run_release_checks.py",
    "scripts/risk/smoke_upload_api.py",
    "backend/app/core/risk/contract_checks.py",
    "backend/app/core/risk/contract_risk_engine.py",
    "backend/app/core/risk/risk_playbook.py",
    "backend/app/core/risk/risk_engine.py",
    "backend/app/core/risk/risk_scoring.py",
    "backend/tests/test_contract_checks_batching.py",
    "backend/tests/test_contract_checks_evaluation.py",
    "backend/tests/test_deterministic_cross_checks.py",
    "backend/tests/test_cross_clause_candidate_retrieval.py",
]

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    missing = [name for name in FILES if not (ROOT / name).is_file()]
    if missing:
        raise SystemExit("Missing required release inputs:\n" + "\n".join(missing))
    entries = {name: {"sha256": digest(ROOT / name), "bytes": (ROOT / name).stat().st_size} for name in FILES}
    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_root": str(ROOT),
        "release_zip": str(ZIP_PATH.relative_to(ROOT)),
        "file_count": len(entries),
        "files": entries,
        "interpretation": (
            "Includes code/data/docs/results needed to inspect and reproduce the recorded Phase 2 experiments. "
            "The custom risk queue is still unannotated human gold; model-silver and synthetic scenario results "
            "are diagnostic and must not be called human-gold accuracy."
        ),
    }
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in FILES:
            archive.write(ROOT / name, arcname=name)
        archive.writestr("RELEASE_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    manifest["zip_sha256"] = digest(ZIP_PATH)
    manifest["zip_bytes"] = ZIP_PATH.stat().st_size
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "zip": str(ZIP_PATH.relative_to(ROOT)),
        "manifest": str(MANIFEST_PATH.relative_to(ROOT)),
        "file_count": len(entries),
        "zip_bytes": manifest["zip_bytes"],
        "zip_sha256": manifest["zip_sha256"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
