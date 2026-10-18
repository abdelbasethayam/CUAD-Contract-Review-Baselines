
import csv
import json
import re
import time
from pathlib import Path
from threading import Lock
import hashlib
from typing import Callable

import numpy as np

from ..core.config import (
    EMBEDDING_BACKEND,
    LOCAL_HASHING_DIM,
    COHERE_MODEL,
    QDRANT_COLLECTION,
    LEGAL_KNOWLEDGE_COLLECTION,
    RISK_CONTEXT_TOP_K,
    RISK_MODEL,
    RISK_MAX_TOKENS,
    RISK_NUM_CTX,
    RISK_TEMPERATURE,
    RISK_SELF_CONSISTENCY_PASSES,
    LEGAL_KNOWLEDGE_TOP_K,
    RISK_PLAYBOOK_PATH,
    RISK_ENABLE_CROSS_CLAUSE,
    RISK_ENABLE_DOCUMENT_CHECKS,
    RUNS_DIR,
    RISK_USE_CONTEXT,
    RISK_USE_LEGAL_GUIDANCE,
    TOP_K,
    load_labels,
)
from ..core.rag import (
    classify_clause,
    embed_queries,
    load_label_definitions,
    make_cohere_client,
    make_qdrant_client,
)
from ..core.rag.clause_segmenter import segment_document
from ..core.rag.segmenter import is_definition
from ..core.rag.validator import is_real_clause
from ..core.risk.contract_checks import analyze_contract_checks
from ..core.risk.deterministic_cross_checks import run_deterministic_cross_checks
from ..core.risk.contract_metadata import extract_contract_metadata
from ..core.risk.contract_coverage import build_contract_coverage
from ..core.risk.contract_risk_engine import aggregate_clause_risks, build_risk_only_view
from ..core.risk.risk_engine import analyze_clause_risk
from ..core.risk.deterministic_rules import RULE_ENGINE_VERSION
from ..core.risk.risk_playbook import applicable_checks, load_playbook
from ..core.risk.run_store import AnalysisRun, create_or_resume_run, mark_run_complete, mark_run_failed
from ..core.risk.evidence_compressor import compress_cuad_evidence

ProgressCallback = Callable[[dict], None]
_CLASSIFICATION_LOCK = Lock()


def _is_contract_header_metadata(text: str, clause_index: int) -> bool:
    """Recognize the unnumbered front-page party block, not a substantive clause."""
    if int(clause_index) != 0:
        return False
    value = str(text or "")
    party_a = re.search(r"\bParty\s+A(?:\s*\([^)]*\))?\s*:\s*[^\n]{2,}", value, re.I)
    party_b = re.search(r"\bParty\s+B(?:\s*\([^)]*\))?\s*:\s*[^\n]{2,}", value, re.I)
    numbered = re.match(r"^\s*\d{1,3}\s*[.)]", value)
    return bool(party_a and party_b and not numbered)


def _is_numbered_structural_clause(text: str, metadata: dict) -> bool:
    """Trust a numbered top-level segment over a secondary yes/no model veto."""
    return bool(
        metadata.get("marker_kind") == "TOP_LEVEL"
        and re.match(r"^\s*\d{1,3}\s*[.)]", str(text or ""))
    )


def _emit(
    callback: ProgressCallback | None,
    stage: str,
    message: str,
    **details,
) -> None:
    if callback:
        callback(
            {
                "type": "progress",
                "stage": stage,
                "message": message,
                **details,
            }
        )


def _trace_callback(run, callback: ProgressCallback | None):
    started = time.monotonic()
    sequence = 0
    def emit(event: dict) -> None:
        nonlocal sequence
        sequence += 1
        event = {
            **event,
            "analysis_id": run.analysis_id,
            "sequence": sequence,
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
        run.append_jsonl("trace.jsonl", event)
        run.write_json(
            "status.json",
            {
                "analysis_id": run.analysis_id,
                "status": (
                    "COMPLETED" if event.get("stage") == "complete"
                    else ("FAILED" if event.get("stage") == "failed" else "RUNNING")
                ),
                "last_stage": event.get("stage", "pipeline"),
                "last_message": event.get("message", ""),
                "current": event.get("current"),
                "total": event.get("total"),
                "clause_index": event.get("clause_index"),
            },
        )
        _emit(
            callback,
            event.get("stage", "pipeline"),
            event.get("message", ""),
            **{k: v for k, v in event.items() if k not in {"type", "stage", "message"}},
        )
    return emit


def _file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _code_fingerprint() -> str:
    """Hash the source files that define the live Phase 2 pipeline."""
    root = Path(__file__).resolve().parents[3]
    # Hash complete runtime source trees and the source-of-truth configuration/data.
    # This avoids a silent same-ID resume when a relevant module (for example a
    # classifier helper or API schema) changed but was omitted from a hand-maintained list.
    paths = set()
    for pattern in ("backend/app/**/*.py", "frontend/src/**/*.js", "frontend/src/**/*.jsx",
                    "frontend/src/**/*.ts", "frontend/src/**/*.tsx", "frontend/src/**/*.css",
                    "backend/data/legal_knowledge/**/*.md"):
        paths.update(root.glob(pattern))
    paths.update({
        root / "data/risk/commercial_clause_risk_playbook.json",
        root / "backend/data/legal_knowledge/risk_taxonomy.json",
        root / "backend/data/legal_knowledge/source_registry.json",
        root / "requirements.txt",
        root / "requirements-dev.txt",
    })
    relative_paths = sorted(
        path.relative_to(root).as_posix()
        for path in paths
        if path.is_file()
    )
    digest = hashlib.sha256()
    for relative in relative_paths:
        path = root / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\\0")
        if path.is_file():
            digest.update(path.read_bytes())
        else:
            digest.update(b"MISSING")
        digest.update(b"\\0")
    return digest.hexdigest()


def _pipeline_config(top_k: int, playbook: dict) -> dict:
    return {
        "phase": 2,
        "code_fingerprint": _code_fingerprint(),
        "top_k": int(top_k),
        "risk_model": RISK_MODEL,
        "risk_temperature": RISK_TEMPERATURE,
        "risk_max_tokens": RISK_MAX_TOKENS,
        "risk_num_ctx": RISK_NUM_CTX,
        "legal_knowledge_top_k": LEGAL_KNOWLEDGE_TOP_K,
        "embedding_backend": EMBEDDING_BACKEND,
        "embedding_model": COHERE_MODEL if EMBEDDING_BACKEND == "cohere" else f"sklearn.HashingVectorizer(n_features={LOCAL_HASHING_DIM}, ngram_range=(1,2), norm=l2)",
        "qdrant_collection": QDRANT_COLLECTION,
        "legal_knowledge_collection": LEGAL_KNOWLEDGE_COLLECTION,
        "risk_context_top_k": RISK_CONTEXT_TOP_K,
        "risk_self_consistency_passes": RISK_SELF_CONSISTENCY_PASSES,
        "playbook_hash": playbook.get("playbook_hash"),
        "playbook_path": str(RISK_PLAYBOOK_PATH),
        "playbook_questions_enabled": True,
        "use_context": RISK_USE_CONTEXT,
        "use_legal_guidance": RISK_USE_LEGAL_GUIDANCE,
        "enable_cross_clause": RISK_ENABLE_CROSS_CLAUSE,
        "enable_document_checks": RISK_ENABLE_DOCUMENT_CHECKS,
    }


def _apply_clause_risk_summary(row: dict, findings: list[dict]) -> dict:
    """Replace the visible clause-level risk summary without leaking stale prior findings."""
    positives = [
        item for item in findings
        if item.get("risk_status") == "POTENTIAL_RISK" and item.get("risk")
    ]
    unresolved = [
        item for item in findings
        if item.get("risk_status") == "INSUFFICIENT_EVIDENCE"
    ]
    row["risk_findings"] = findings
    row["risk_status"] = "POTENTIAL_RISK" if positives else (
        "INSUFFICIENT_EVIDENCE" if unresolved else "NO_RISK"
    )
    row.update({
        "risk": False,
        "risk_type": None,
        "risk_level": None,
        "risk_confidence": None,
        "risk_confidence_status": "UNCALIBRATED",
        "risk_severity_signal": None,
        "risk_severity_status": "INCOMPLETE" if unresolved else "NOT_APPLICABLE",
        "risk_provenance": {},
        "risk_evidence_clause_index": None,
        "risk_evidence_scope": None,
        "risk_evidence_source_status": None,
        "risk_evidence_clause_candidates": [],
        "risk_supporting_sources": [],
        "risk_score_interpretation": None,
        "why_flagged": "",
        "evidence": "",
    })
    if positives:
        best = max(
            positives,
            key=lambda item: (
                float(item.get("raw_support_score") or 0.0),
                float(item.get("severity_signal") or 0.0),
            ),
        )
        provenance = best.get("provenance") or {}
        row.update({
            "risk": True,
            "risk_type": best.get("risk_type"),
            "risk_level": best.get("risk_level"),
            "risk_confidence": best.get("confidence"),
            "risk_confidence_status": best.get("confidence_status", "UNCALIBRATED"),
            "risk_severity_signal": best.get("severity_signal"),
            "risk_severity_status": best.get("severity_status", "UNCALIBRATED"),
            "risk_provenance": provenance,
            "risk_evidence_clause_index": best.get("evidence_clause_index"),
            "risk_evidence_scope": best.get("evidence_scope"),
            "risk_evidence_source_status": best.get("evidence_source_status"),
            "risk_evidence_clause_candidates": best.get("evidence_clause_candidates", []),
            "risk_supporting_sources": best.get("supporting_sources", []),
            "risk_score_interpretation": provenance.get("score_interpretation"),
            "why_flagged": best.get("why_flagged", ""),
            "evidence": best.get("evidence", ""),
        })
    return row


def _csv_safe_rows(rows: list[dict]) -> list[dict]:
    """Serialize nested audit fields as JSON so exported CSV remains machine-readable."""
    safe_rows: list[dict] = []
    for row in rows:
        safe = dict(row)
        provenance = safe.get("provenance") or safe.get("risk_provenance") or {}
        if isinstance(provenance, dict):
            for key in ("score_component_source", "score_interpretation", "score_version"):
                if safe.get(key) is None and provenance.get(key) is not None:
                    safe[key] = provenance[key]
        for key, value in safe.items():
            if isinstance(value, (dict, list)):
                safe[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
        safe_rows.append(safe)
    return safe_rows


def _clause_risk_checkpoint_is_complete(
    findings: list[dict],
    expected_check_ids: set[str],
    playbook_hash: str | None,
) -> bool:
    """A checkpoint is reusable only if all expected checks and model passes completed."""
    if not findings or not expected_check_ids:
        return False
    found_ids = {str(item.get("check_id") or "") for item in findings}
    if not expected_check_ids.issubset(found_ids):
        return False
    for finding in findings:
        provenance = finding.get("provenance") or {}
        if provenance.get("rule_engine_version") != RULE_ENGINE_VERSION:
            return False
        if provenance.get("playbook_hash") != playbook_hash:
            return False
        if str(finding.get("check_id") or "") in expected_check_ids:
            try:
                missing_passes = int(provenance.get("missing_passes", 0) or 0)
            except (TypeError, ValueError, OverflowError):
                return False
            if missing_passes > 0:
                return False
    return True


def _contract_checks_checkpoint_is_complete(
    payload: dict,
    playbook: dict,
    *,
    model: str,
    cross_clause_enabled: bool,
    document_checks_enabled: bool,
) -> bool:
    """Do not freeze contract checks whose model calls failed or omitted answers."""
    if not isinstance(payload, dict):
        return False
    if payload.get("playbook_hash") != playbook.get("playbook_hash"):
        return False
    if payload.get("model") != model:
        return False
    if bool(payload.get("cross_clause_enabled")) != bool(cross_clause_enabled):
        return False
    if bool(payload.get("document_checks_enabled")) != bool(document_checks_enabled):
        return False

    groups = (
        (
            {str(item.get("id")) for item in (playbook.get("cross_clause_checks") or [])},
            payload.get("cross_clause_findings") or [],
        ),
        (
            {str(item.get("id")) for item in (playbook.get("document_level_checks") or [])},
            payload.get("document_findings") or [],
        ),
    )
    for expected_ids, findings in groups:
        found = {str(item.get("check_id") or "") for item in findings}
        if not expected_ids.issubset(found):
            return False
        for finding in findings:
            if str(finding.get("check_id") or "") not in expected_ids:
                continue
            provenance = finding.get("provenance") or {}
            try:
                missing_passes = int(provenance.get("missing_passes", 0) or 0)
            except (TypeError, ValueError, OverflowError):
                return False
            if missing_passes > 0:
                return False
    return True


def _load_segments(run):
    data = run.read_json("segments.json")
    if not data:
        return None
    return data


def classify_contract(
    file_path: Path,
    top_k: int = TOP_K,
    progress_callback: ProgressCallback | None = None,
    filename: str | None = None,
) -> dict:
    with _CLASSIFICATION_LOCK:
        return _classify_contract(
            file_path,
            top_k=top_k,
            progress_callback=progress_callback,
            filename=filename or file_path.name,
        )

def resume_contract(
    analysis_id: str,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    root = Path(RUNS_DIR) / analysis_id
    manifest_path = root / "manifest.json"
    if not root.exists() or not manifest_path.exists():
        raise FileNotFoundError(f"Analysis run not found: {analysis_id}")
    source_candidates = list(root.glob("source.*"))
    if not source_candidates:
        raise FileNotFoundError(f"Persistent source missing for run: {analysis_id}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = manifest.get("pipeline") or {}
    current = _pipeline_config(int(expected.get("top_k", TOP_K)), load_playbook())
    # Explicit resume must use the same experiment configuration. A changed
    # playbook hash or deterministic rule version starts a new run instead of mixing artifacts.
    if expected and current != expected:
        raise RuntimeError(
            "Run configuration changed since this analysis started. "
            "Start a new analysis instead of resuming with mixed artifacts."
        )
    if manifest.get("status") == "COMPLETED":
        result_path = root / "result.json"
        if result_path.exists():
            return json.loads(result_path.read_text(encoding="utf-8"))
    filename = manifest.get("source", {}).get("filename") or source_candidates[0].name
    with _CLASSIFICATION_LOCK:
        return _classify_contract(
            source_candidates[0],
            top_k=int(manifest.get("pipeline", {}).get("top_k", TOP_K)),
            progress_callback=progress_callback,
            filename=filename,
            run_id=analysis_id,
        )

def _classify_contract(
    file_path: Path,
    top_k: int,
    progress_callback: ProgressCallback | None,
    filename: str,
    run_id: str | None = None,
) -> dict:
    playbook = load_playbook()
    if run_id:
        run = AnalysisRun(run_id, Path(RUNS_DIR) / run_id)
        manifest = run.read_json("manifest.json", {}) or {}
        top_k = int(manifest.get("pipeline", {}).get("top_k", top_k))
    else:
        run = create_or_resume_run(
            file_path,
            filename=filename,
            config=_pipeline_config(top_k, playbook),
        )
    trace = _trace_callback(run, progress_callback)

    try:
        segments_json = _load_segments(run)
        if segments_json is None:
            trace({"type": "progress", "stage": "extract", "message": "Extracting document structure"})
            segments = segment_document(file_path)
            segments_json = [
                {
                    "clause_index": i,
                    "clause_id": segment.clause_id,
                    "text": segment.text,
                    "parser": segment.parser,
                    "page_start": segment.page_start,
                    "page_end": segment.page_end,
                    "parent_clause": segment.parent_clause,
                    "depth": segment.depth,
                    "source_blocks": segment.source_blocks,
                    "heading": segment.heading,
                    "metadata": segment.metadata or {},
                }
                for i, segment in enumerate(segments)
            ]
            run.write_json("segments.json", segments_json)
            trace({
                "type": "progress",
                "stage": "extract",
                "message": "Document structure extracted",
                "parser": segments[0].parser if segments else None,
                "total_blocks": len(segments),
            })
        else:
            segments = None

        segment_by_index = {int(item["clause_index"]): item for item in segments_json}

        if not segments_json:
            raise ValueError(
                "No clauses were detected. The document may be empty, image-only, "
                "or use a layout the segmenter cannot recognize."
            )

        results_by_index = {
            int(item["clause_index"]): item
            for item in run.read_jsonl_index("classification.jsonl", "clause_index").values()
        }

        trace({
            "type": "progress",
            "stage": "segment",
            "message": "Clause segmentation available",
            "total": len(segments_json),
            "resumed_classifications": len(results_by_index),
        })

        need_validate = run.read_json("validated.json")
        if need_validate is None:
            validation_records = []
            for item in segments_json:
                text = str(item["text"])
                metadata = item.get("metadata", {})
                if metadata.get("is_signature_metadata") or _is_contract_header_metadata(text, int(item["clause_index"])):
                    status = "DOCUMENT_METADATA"
                elif _is_numbered_structural_clause(text, metadata):
                    # A structurally extracted numbered provision is substantive contract
                    # text even when a local yes/no validator mistakes appended signature
                    # lines for metadata. Do not let that secondary model silently drop it.
                    status = "VALID_CLAUSE"
                else:
                    status = "VALID_CLAUSE" if is_real_clause(text) else "NO_APPLICABLE_LABEL"
                validation_records.append(
                    {
                        "clause_index": int(item["clause_index"]),
                        "clause_text": text,
                        "status": status,
                    }
                )
            run.write_json("validated.json", validation_records)
        else:
            validation_records = need_validate

        valid_items = [
            x for x in validation_records if x["status"] == "VALID_CLAUSE"
        ]
        if not valid_items:
            raise ValueError("All extracted fragments were rejected as non-clauses.")

        embedding_path = run.root / "embeddings.npy"
        if embedding_path.exists():
            query_vectors = np.load(embedding_path)
            if len(query_vectors) != len(valid_items):
                query_vectors = None
        else:
            query_vectors = None

        if query_vectors is None:
            trace({
                "type": "progress",
                "stage": "embedding",
                "message": "Creating embeddings for validated clauses",
                "current": 0,
                "total": len(valid_items),
            })
            cohere_client = make_cohere_client()
            query_vectors = np.asarray(
                embed_queries(
                    cohere_client,
                    [item["clause_text"] for item in valid_items],
                ),
                dtype=np.float32,
            )
            np.save(embedding_path, query_vectors)
            trace({
                "type": "progress",
                "stage": "embedding",
                "message": "Clause embeddings checkpointed",
                "current": len(valid_items),
                "total": len(valid_items),
            })
        else:
            cohere_client = make_cohere_client()

        qdrant_client = make_qdrant_client()
        labels = load_labels()
        label_definitions = load_label_definitions(labels)

        context_clauses = [
            {
                "clause_index": int(item["clause_index"]),
                "clause_text": item["clause_text"],
                "vector": query_vectors[pos].tolist(),
            }
            for pos, item in enumerate(valid_items)
        ]

        # Phase 1 classification: resume from the exact clause that was last
        # checkpointed.
        total_valid = len(valid_items)
        for pos, item in enumerate(valid_items):
            idx = int(item["clause_index"])
            if idx in results_by_index:
                continue

            trace({
                "type": "progress",
                "stage": "classification",
                "message": f"Classifying clause {pos + 1} of {total_valid}",
                "current": pos + 1,
                "total": total_valid,
                "clause_index": idx,
            })

            if is_definition(item["clause_text"]):
                trace({
                    "type": "progress",
                    "stage": "classification",
                    "message": f"Clause {idx} is a definition; using normal CUAD classification.",
                    "clause_index": idx,
                })

            result = classify_clause(
                clause_text=item["clause_text"],
                query_vector=query_vectors[pos].tolist(),
                qdrant_client=qdrant_client,
                labels=labels,
                label_definitions=label_definitions,
                top_k=top_k,
                progress_callback=progress_callback,
            )

            segment_info = segment_by_index.get(idx, {})
            row = {
                "clause_index": idx,
                "clause_id": segment_info.get("clause_id"),
                "clause_text": item["clause_text"],
                "section_path": segment_info.get("clause_id"),
                "page_start": segment_info.get("page_start"),
                "page_end": segment_info.get("page_end"),
                "parent_clause": segment_info.get("parent_clause"),
                "depth": segment_info.get("depth"),
                "source_blocks": segment_info.get("source_blocks", []),
                "heading": segment_info.get("heading"),
                "predicted_label": result["predicted_label"],
                "clause_type": result["predicted_label"],
                "retrieved_labels": result.get("retrieved_labels", []),
                "retrieved_scores": result.get("retrieved_scores", []),
                "candidate_labels": result.get("candidate_labels", []),
                "raw_retrieved_labels": result.get("retrieved_labels", []),
                "raw_retrieved_scores": result.get("retrieved_scores", []),
                "raw_retrieved_examples": result.get("retrieved_examples", []),
                "classification_status": result["prediction_status"],
                "classification_source": result.get("classification_source"),
                "fallback_used": bool(result.get("fallback_used", False)),
                "fallback_reason": result.get("fallback_reason"),
                "classification_confidence": result.get("classification_confidence"),
                "retrieval_status": result.get("retrieval_status", "ok"),
                "retrieval_error": result.get("retrieval_error"),
                "risk_findings": [],
                "risk_status": "NOT_ANALYZED",
            }
            compressed = compress_cuad_evidence(
                clause_id=idx,
                final_label=row["predicted_label"],
                contract_text=item["clause_text"],
                retrieved_examples=row["raw_retrieved_examples"],
            )
            row["retrieved_examples"] = compressed
            row["retrieved_labels"] = [x.get("label") for x in compressed]
            row["retrieved_scores"] = [x.get("score") for x in compressed]
            run.append_jsonl("classification.jsonl", row)
            results_by_index[idx] = row
            trace({
                "type": "progress",
                "stage": "classification",
                "message": f"Clause {idx} classification checkpointed",
                "clause_index": idx,
                "current": pos + 1,
                "total": total_valid,
            })

        # Deterministic clause-family coverage is stored separately from risk truth.
        clause_rows_for_coverage = sorted(results_by_index.values(), key=lambda x: int(x["clause_index"]))
        coverage_path = run.root / "contract_coverage.json"
        if coverage_path.exists():
            contract_coverage = run.read_json("contract_coverage.json", []) or []
        else:
            contract_coverage = build_contract_coverage(clause_rows_for_coverage, playbook)
            run.write_json("contract_coverage.json", contract_coverage)

        # Phase 2 clause risk: each clause is checkpointed separately.
        clause_risks_refreshed = False
        risk_index = run.read_jsonl_index("risk_findings.jsonl", "finding_id")
        for pos, item in enumerate(valid_items):
            idx = int(item["clause_index"])
            label = str(results_by_index[idx].get("predicted_label") or "")
            findings_for_clause = [
                value for value in risk_index.values()
                if int(value.get("clause_index", -1)) == idx
            ]
            finding_ids = {
                str(value.get("check_id") or str(value.get("finding_id") or "").rsplit(":", 1)[-1])
                for value in findings_for_clause
            }
            checks_expected = {
                str(check.get("id"))
                for check in applicable_checks(
                    playbook,
                    label,
                    clause_text=str(item.get("clause_text") or ""),
                )
            }
            if not checks_expected:
                checks_expected = {"OPEN-RISK-1"}
            # Missing model passes are retryable failures, not completed checkpoints.
            if _clause_risk_checkpoint_is_complete(
                findings_for_clause,
                checks_expected,
                playbook.get("playbook_hash"),
            ):
                continue

            findings = analyze_clause_risk(
                clause_index=idx,
                clause_text=item["clause_text"],
                clause_type=label,
                query_vector=query_vectors[pos].tolist(),
                contract_clauses=context_clauses,
                cohere_client=cohere_client,
                progress_callback=trace,
                playbook=playbook,
                qdrant_client=qdrant_client,
            )
            clause_risks_refreshed = True
            # Idempotent checkpoint: replace only the clause's prior rows.
            existing_lines = run.read_jsonl_index("risk_findings.jsonl", "finding_id")
            existing_for_clause = [
                x for x in existing_lines.values()
                if int(x.get("clause_index", -1)) != idx
            ]
            target = run.path("risk_findings.jsonl")
            tmp = target.with_suffix(".jsonl.tmp")
            with tmp.open("w", encoding="utf-8") as handle:
                for value in existing_for_clause:
                    handle.write(json.dumps(value, ensure_ascii=False) + "\n")
                for finding in findings:
                    finding["finding_id"] = f"{idx}:{finding['check_id']}"
                    handle.write(json.dumps(finding, ensure_ascii=False) + "\n")
            tmp.replace(target)

            row = _apply_clause_risk_summary(results_by_index[idx], findings)

            # Rewrite the clause record atomically so the GUI sees a coherent row
            # after a restart.
            classifications = list(run.read_jsonl_index("classification.jsonl", "clause_index").values())
            target_c = run.path("classification.jsonl")
            tmp_c = target_c.with_suffix(".jsonl.tmp")
            with tmp_c.open("w", encoding="utf-8") as handle:
                for value in sorted(
                    classifications + [row],
                    key=lambda x: int(x["clause_index"]),
                ):
                    if int(value["clause_index"]) == idx and value is not row:
                        continue
                    handle.write(json.dumps(value, ensure_ascii=False) + "\n")
            tmp_c.replace(target_c)
            results_by_index[idx] = row

        all_risk_findings = [
            finding for finding in run.read_jsonl_index("risk_findings.jsonl", "finding_id").values()
            if not _is_contract_header_metadata(str(finding.get("clause_text") or ""), int(finding.get("clause_index", -1)))
        ]
        clause_rows = [
            row for row in sorted(results_by_index.values(), key=lambda x: int(x["clause_index"]))
            if not _is_contract_header_metadata(str(row.get("clause_text") or ""), int(row.get("clause_index", -1)))
            and row.get("classification_status") != "DOCUMENT_METADATA"
        ]

        deterministic_signals = run.read_json("deterministic_cross_checks.json", None)
        if deterministic_signals is None:
            deterministic_signals = run_deterministic_cross_checks(clause_rows)
            run.write_json("deterministic_cross_checks.json", deterministic_signals)

        contract_checks_path = run.root / "contract_checks.json"
        effective_playbook = dict(playbook)
        if not RISK_ENABLE_CROSS_CLAUSE:
            effective_playbook["cross_clause_checks"] = []
        if not RISK_ENABLE_DOCUMENT_CHECKS:
            effective_playbook["document_level_checks"] = []

        cached_contract_checks = (
            run.read_json("contract_checks.json", {}) or {}
            if contract_checks_path.exists()
            else {}
        )
        contract_checks_refreshed = False
        if contract_checks_path.exists() and _contract_checks_checkpoint_is_complete(
            cached_contract_checks,
            effective_playbook,
            model=RISK_MODEL,
            cross_clause_enabled=RISK_ENABLE_CROSS_CLAUSE,
            document_checks_enabled=RISK_ENABLE_DOCUMENT_CHECKS,
        ):
            cross_findings = cached_contract_checks.get("cross_clause_findings", [])
            document_findings = cached_contract_checks.get("document_findings", [])
        else:
            trace({
                "type": "progress",
                "stage": "cross_clause",
                "message": (
                    "Retrying incomplete cross-clause/document checks"
                    if contract_checks_path.exists()
                    else "Running configured cross-clause/document checks"
                ),
                "total": 1,
            })
            cross_findings, document_findings = analyze_contract_checks(
                clause_rows,
                playbook=effective_playbook,
                progress_callback=trace,
                deterministic_signals=deterministic_signals,
            )
            run.write_json(
                "contract_checks.json",
                {
                    "cross_clause_findings": cross_findings,
                    "document_findings": document_findings,
                    "deterministic_cross_checks": deterministic_signals,
                    "playbook_hash": playbook.get("playbook_hash"),
                    "model": RISK_MODEL,
                    "cross_clause_enabled": RISK_ENABLE_CROSS_CLAUSE,
                    "document_checks_enabled": RISK_ENABLE_DOCUMENT_CHECKS,
                },
            )
            contract_checks_refreshed = True

        aggregate_path = run.root / "contract_risk.json"
        if aggregate_path.exists() and not clause_risks_refreshed and not contract_checks_refreshed:
            assessment = run.read_json("contract_risk.json", {}) or {}
        else:
            assessment = aggregate_clause_risks(
                all_risk_findings + cross_findings + document_findings,
                playbook=playbook,
            )
            assessment["cross_clause_findings"] = cross_findings
            assessment["document_findings"] = document_findings
            assessment["risk_only"] = build_risk_only_view(all_risk_findings + cross_findings + document_findings)
            assessment["deterministic_cross_checks"] = deterministic_signals
            run.write_json("contract_risk.json", assessment)
        # Export stable CSV views in addition to the raw JSON/JSONL audit artifacts.
        clause_rows = sorted(results_by_index.values(), key=lambda x: int(x["clause_index"]))
        clause_csv = run.path("clauses.csv")
        with clause_csv.open("w", newline="", encoding="utf-8") as handle:
            fields = [
                "clause_index", "clause_text", "predicted_label", "classification_status",
                "classification_confidence", "risk_status", "risk", "risk_type",
                "risk_level", "risk_confidence", "risk_confidence_status",
                "risk_severity_signal", "risk_severity_status", "risk_evidence_clause_index",
                "risk_evidence_scope", "risk_evidence_source_status", "risk_evidence_clause_candidates",
                "risk_supporting_sources", "risk_score_interpretation", "risk_provenance",
                "why_flagged", "evidence",
            ]
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(_csv_safe_rows(clause_rows))

        risk_csv = run.path("risk_findings.csv")
        with risk_csv.open("w", newline="", encoding="utf-8") as handle:
            fields = [
                "finding_id", "scope", "clause_index", "clause_ids", "evidence_clause_index",
                "evidence_scope", "evidence_source_status", "evidence_clause_candidates",
                "predicted_label", "check_id", "risk_domain", "risk_subdomain", "question",
                "answer", "risk_status", "risk_type", "risk_level", "raw_support_score",
                "confidence", "confidence_status", "severity_signal", "severity_status",
                "ground_truth_status", "source_tier", "jurisdiction", "effective_date",
                "contract_type", "source_title", "source_url", "retrieval_date",
                "supporting_quote_or_paraphrase", "supporting_sources", "provenance",
                "score_component_source", "score_interpretation", "score_version",
                "base_score", "final_score", "score_components_raw", "score_modifiers",
                "human_review_required", "review_escalation", "why_flagged", "evidence",
            ]
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(_csv_safe_rows(all_risk_findings + cross_findings + document_findings))

        # Persist final status and a compact machine-readable result snapshot.
        clauses_out = []
        for item in sorted(results_by_index.values(), key=lambda x: int(x["clause_index"])):
            if _is_contract_header_metadata(str(item.get("clause_text") or ""), int(item.get("clause_index", -1))) or item.get("classification_status") == "DOCUMENT_METADATA":
                continue
            if item.get("classification_status") == "NO_APPLICABLE_LABEL":
                item = {
                    **item,
                    "risk_findings": [],
                    "risk_status": "NOT_ANALYZED",
                }
            clauses_out.append(item)

        run.write_json(
            "result.json",
            {
                "analysis_id": run.analysis_id,
                "filename": filename,
                "total_clauses": len(clauses_out),
                "clauses": clauses_out,
                "contract_risk_assessment": assessment,
                "contract_coverage": contract_coverage,
                "deterministic_cross_checks": deterministic_signals,
                "contract_metadata": {
                    **extract_contract_metadata(filename, segments_json),
                    "document_hash": _file_hash(file_path),
                    "document_version": _file_hash(file_path),
                },
            },
        )
        mark_run_complete(
            run,
            total_clauses=len(clauses_out),
            valid_clauses=len(valid_items),
            playbook_hash=playbook.get("playbook_hash"),
        )
        trace({
            "type": "progress",
            "stage": "complete",
            "message": "Contract analysis complete",
            "analysis_id": run.analysis_id,
            "total": len(segments_json),
        })
        return {
            "analysis_id": run.analysis_id,
            "filename": filename,
            "clauses": clauses_out,
            "contract_risk_assessment": assessment,
            "contract_metadata": extract_contract_metadata(filename, segments_json),
            "contract_coverage": contract_coverage,
            "deterministic_cross_checks": deterministic_signals,
            "run_dir": str(run.root),
        }

    except Exception as exc:
        mark_run_failed(run, str(exc))
        trace({
            "type": "progress",
            "stage": "failed",
            "message": f"Analysis failed: {exc}",
            "analysis_id": run.analysis_id,
        })
        raise