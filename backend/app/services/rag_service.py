"""End-to-end, resumable contract classification + risk analysis service."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from threading import Lock
import hashlib
from typing import Callable

import numpy as np

from ..core.config import (
    RISK_CONTEXT_TOP_K,
    RISK_MODEL,
    RISK_SELF_CONSISTENCY_PASSES,
    RISK_PLAYBOOK_PATH,
    RISK_CALIBRATION_PATH,
    RISK_ENABLE_CROSS_CLAUSE,
    RISK_ENABLE_DOCUMENT_CHECKS,
    LEGAL_KNOWLEDGE_CORPUS_VERSION,
    RUNS_DIR,
    RISK_USE_CONTEXT,
    RISK_USE_LEGAL_GUIDANCE,
    RISK_USE_PLAYBOOK,
    TOP_K,
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
from ..core.risk.contract_structure import extract_clause_structure
from ..core.risk.contract_coverage import build_contract_coverage
from ..core.risk.contract_risk_engine import aggregate_clause_risks, build_risk_only_view
from ..core.risk.risk_engine import RISK_PROMPT_VERSION, analyze_clause_risk
from ..core.risk.risk_playbook import load_playbook
from ..core.risk.run_store import AnalysisRun, create_or_resume_run, mark_run_complete, mark_run_failed
from ..core.rag.evidence_compressor import compress_cuad_evidence

ProgressCallback = Callable[[dict], None]
_CLASSIFICATION_LOCK = Lock()


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
    def emit(event: dict) -> None:
        run.append_jsonl("trace.jsonl", event)
        run.write_json(
            "status.json",
            {
                "analysis_id": run.analysis_id,
                "status": "RUNNING",
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


def _pipeline_config(top_k: int, playbook: dict) -> dict:
    return {
        "phase": 2,
        "top_k": int(top_k),
        "risk_model": RISK_MODEL,
        "risk_context_top_k": RISK_CONTEXT_TOP_K,
        "risk_self_consistency_passes": RISK_SELF_CONSISTENCY_PASSES,
        "playbook_hash": playbook.get("playbook_hash"),
        "playbook_path": str(RISK_PLAYBOOK_PATH),
        "calibration_hash": _file_hash(RISK_CALIBRATION_PATH),
        "use_playbook": RISK_USE_PLAYBOOK,
        "use_context": RISK_USE_CONTEXT,
        "use_legal_guidance": RISK_USE_LEGAL_GUIDANCE,
        "enable_cross_clause": RISK_ENABLE_CROSS_CLAUSE,
        "enable_document_checks": RISK_ENABLE_DOCUMENT_CHECKS,
        "prompt_version": RISK_PROMPT_VERSION,
        "legal_knowledge_corpus_version": LEGAL_KNOWLEDGE_CORPUS_VERSION,
    }


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
    # playbook/model/calibration file starts a new run instead of mixing artifacts.
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
                if item.get("metadata", {}).get("is_signature_metadata"):
                    status = "DOCUMENT_METADATA"
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
            structure = extract_clause_structure(
                item["clause_text"],
                section_path=segment_info.get("heading") or segment_info.get("clause_id"),
                page_start=segment_info.get("page_start"),
                page_end=segment_info.get("page_end"),
            )
            row = {
                "clause_index": idx,
                "clause_id": segment_info.get("clause_id"),
                "clause_text": item["clause_text"],
                "section_path": structure.get("section_path"),
                "page_start": structure.get("page_start"),
                "page_end": structure.get("page_end"),
                "parent_clause": segment_info.get("parent_clause"),
                "depth": segment_info.get("depth"),
                "source_blocks": segment_info.get("source_blocks", []),
                "heading": segment_info.get("heading"),
                "defined_terms_used": structure.get("defined_terms_used", []),
                "linked_sections": structure.get("linked_sections", []),
                "parties_affected": [],
                "beneficiary": None,
                "direction_of_obligation": structure.get("direction_of_obligation"),
                "transaction_role": structure.get("transaction_role"),
                "commercial_purpose": None,
                "operational_trigger": None,
                "scope": structure.get("scope", {}),
                "rights_and_duties": structure.get("rights_and_duties", []),
                "exceptions_carveouts": structure.get("exceptions_carveouts", []),
                "economic_effect": {},
                "dependencies": structure.get("dependencies", []),
                "dependency_missing": structure.get("dependency_missing", []),
                "structure_status": structure.get("structure_status", "DETERMINISTIC_PARTIAL"),
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

        contract_metadata = extract_contract_metadata(
            filename,
            clause_rows_for_coverage,
            document_hash=(run.read_json("manifest.json", {}) or {}).get("source", {}).get("sha256"),
            document_version="1",
        )
        contract_jurisdiction = (
            contract_metadata.get("jurisdiction_candidates") or [None]
        )[0]

        # Phase 2 clause risk: each clause is checkpointed separately.
        risk_index = run.read_jsonl_index("risk_findings.jsonl", "finding_id")
        for pos, item in enumerate(valid_items):
            idx = int(item["clause_index"])
            label = str(results_by_index[idx].get("predicted_label") or "")
            finding_ids = {
                str(key)
                for key, value in risk_index.items()
                if int(value.get("clause_index", -1)) == idx
            }
            checks_expected = {
                str(c.get("id"))
                for c in (playbook.get("clause_types", {}).get(label, {}).get("checklist") or [])
            }
            if checks_expected and len(finding_ids) >= len(checks_expected):
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
                contract_type=contract_metadata.get("contract_type"),
                jurisdiction=contract_jurisdiction,
                clause_structure=results_by_index[idx],
            )
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

            row = results_by_index[idx]
            row["risk_findings"] = findings
            positives = [x for x in findings if x.get("risk_status") == "POTENTIAL_RISK" and x.get("risk")]
            unresolved = [x for x in findings if x.get("risk_status") == "INSUFFICIENT_EVIDENCE"]
            row["risk_status"] = "POTENTIAL_RISK" if positives else (
                "INSUFFICIENT_EVIDENCE" if unresolved else "NO_RISK"
            )
            if positives:
                best = max(
                    positives,
                    key=lambda x: (
                        float(x.get("final_score") or 0.0),
                        float(x.get("raw_support_score") or 0.0),
                    ),
                )
                row["risk"] = True
                row["risk_type"] = best.get("risk_type")
                row["risk_level"] = best.get("risk_level")
                row["risk_confidence"] = best.get("confidence")
                row["risk_confidence_status"] = best.get("confidence_status", "UNCALIBRATED")
                row["risk_severity_signal"] = best.get("severity_signal")
                row["risk_severity_status"] = best.get("severity_status", "UNCALIBRATED")
                row["risk_provenance"] = best.get("provenance", {})
                row["why_flagged"] = best.get("why_flagged", "")
                row["evidence"] = best.get("evidence", "")
            else:
                row["risk"] = False

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

        all_risk_findings = list(run.read_jsonl_index("risk_findings.jsonl", "finding_id").values())
        clause_rows = sorted(results_by_index.values(), key=lambda x: int(x["clause_index"]))

        deterministic_signals = run.read_json("deterministic_cross_checks.json", None)
        if deterministic_signals is None:
            deterministic_signals = run_deterministic_cross_checks(clause_rows)
            run.write_json("deterministic_cross_checks.json", deterministic_signals)

        contract_checks_path = run.root / "contract_checks.json"
        if contract_checks_path.exists():
            contract_checks = run.read_json("contract_checks.json", {}) or {}
            cross_findings = contract_checks.get("cross_clause_findings", [])
            document_findings = contract_checks.get("document_findings", [])
        else:
            trace({
                "type": "progress",
                "stage": "cross_clause",
                "message": "Running configured cross-clause/document checks",
                "total": 1,
            })
            effective_playbook = dict(playbook)
            if not RISK_ENABLE_CROSS_CLAUSE:
                effective_playbook["cross_clause_checks"] = []
            if not RISK_ENABLE_DOCUMENT_CHECKS:
                effective_playbook["document_level_checks"] = []
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

        aggregate_path = run.root / "contract_risk.json"
        if aggregate_path.exists():
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
                "risk_severity_signal", "risk_severity_status", "why_flagged", "evidence",
            ]
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(clause_rows)

        risk_csv = run.path("risk_findings.csv")
        with risk_csv.open("w", newline="", encoding="utf-8") as handle:
            fields = [
                "finding_id", "clause_index", "predicted_label", "check_id", "question",
                "answer", "risk_status", "risk_type", "risk_level", "raw_support_score",
                "confidence", "confidence_status", "severity_signal", "severity_status",
                "ground_truth_status", "why_flagged", "evidence",
            ]
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_risk_findings + cross_findings + document_findings)

        # Persist final status and a compact machine-readable result snapshot.
        clauses_out = []
        for item in sorted(results_by_index.values(), key=lambda x: int(x["clause_index"])):
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
                "total_clauses": len(segments_json),
                "clauses": clauses_out,
                "contract_risk_assessment": assessment,
                "contract_coverage": contract_coverage,
                "deterministic_cross_checks": deterministic_signals,
                "contract_metadata": {
                    **extract_contract_metadata(filename, clauses_out),
                    "document_hash": _file_hash(file_path),
                    "document_version": _file_hash(file_path),
                },
            },
        )
        mark_run_complete(
            run,
            total_clauses=len(segments_json),
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
            "contract_metadata": extract_contract_metadata(filename, clauses_out),
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
