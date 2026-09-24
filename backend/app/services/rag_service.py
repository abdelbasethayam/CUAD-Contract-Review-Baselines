"""
Application service layer for contract classification.

Ties together the RAG building blocks in core/rag/ into the full pipeline:

    uploaded contract (PDF/.txt)
        -> structured hybrid parser + contract-aware clause segmenter
        -> embedder.embed_queries          (Cohere, batched)
        -> per clause: generator.classify_clause (CUAD only)
        -> compact evidence aggregation
        -> one contract-level legal-guidance retrieval/risk assessment
        -> labeled clauses plus contract-level risk report

Route handlers (api/routes/documents.py) call classify_contract() and
should not talk to core/rag/ directly -- that keeps the HTTP layer free of
pipeline details and makes this logic reusable (e.g. from a CLI script or
a background job later) without depending on FastAPI.
"""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Callable

from ..core.config import load_labels, TOP_K
from ..core.rag import (
    make_cohere_client,
    embed_queries,
    make_qdrant_client,
    classify_clause,
    load_label_definitions,
)
from ..core.rag.clause_segmenter import segment_document
from ..core.rag.segmenter import is_definition
from ..core.rag.validator import is_real_clause
from ..core.risk.contract_assessor import assess_contract_risk
from ..core.risk.evidence_compressor import compress_cuad_evidence

ProgressCallback = Callable[[dict], None]
_CLASSIFICATION_LOCK = Lock()


def _emit(
    callback: ProgressCallback | None,
    stage: str,
    message: str,
    **details,
) -> None:
    if callback:
        callback({"type": "progress", "stage": stage, "message": message, **details})


def classify_contract(
    file_path: Path,
    top_k: int = TOP_K,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    # Local Qdrant storage is single-owner. Serialize complete analyses so a
    # second upload cannot open the same local collection while the first one
    # is still embedding, searching, or generating results.
    with _CLASSIFICATION_LOCK:
        return _classify_contract(
            file_path,
            top_k=top_k,
            progress_callback=progress_callback,
        )


def _classify_contract(
    file_path: Path,
    top_k: int = TOP_K,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    """Run the full pipeline on one uploaded contract file. Returns a list
    of per-clause classification results, in document order.

    Raises:
        ValueError: no clauses could be extracted from the document.
        RuntimeError: an upstream dependency (Cohere, Qdrant, or model provider) failed.
    """
    _emit(progress_callback, "extract", "Extracting document structure")
    segments = segment_document(file_path)
    _emit(
        progress_callback,
        "extract",
        "Document structure extracted",
        parser=segments[0].parser if segments else None,
        total_blocks=len(segments),
    )

    _emit(progress_callback, "segment", "Detecting contract clause boundaries")
    clauses = [segment.text for segment in segments]
    _emit(progress_callback, "segment", "Clause segmentation complete", total=len(clauses))

    if not clauses:
        raise ValueError(
            "No clauses were detected in this document. It may be empty, "
            "scanned/image-only (needs OCR), or use a layout the "
            "segmentation heuristic doesn't handle."
        )

    _emit(progress_callback, "setup", "Loading CUAD labels and model configuration")
    labels = load_labels()
    label_definitions = load_label_definitions(labels)

    cohere_client = make_cohere_client()
    qdrant_client = make_qdrant_client()

    # Lightweight validation pass: catch boundary errors (stray fragments,
    # footnote-like remnants the pattern-based filter missed) BEFORE
    # spending a Cohere embedding call + Qdrant lookup + full classification
    # prompt on something that isn't actually a clause. See validator.py
    # for why this doesn't let the LLM do segmentation itself.
    #
    # Original document position (clause_index) is preserved through
    # filtering so the final output stays in document order regardless of
    # what got validated vs. rejected.
    results: list[dict] = []
    validated: list[tuple[int, str]] = []  # (original_index, clause_text)

    _emit(progress_callback, "validate", "Validating extracted clauses", total=len(clauses))
    for index, clause_text in enumerate(clauses):
        if segments[index].metadata.get("is_signature_metadata"):
            results.append(
                {
                        "clause_index": index,
                        "clause_text": clause_text,
                        "predicted_label": "DOCUMENT_METADATA",
                        "clause_type": "DOCUMENT_METADATA",
                        "retrieved_labels": [],
                        "retrieved_scores": [],
                        "classification_status": "NO_APPLICABLE_LABEL",
                        "classification_source": "metadata_filter",
                        "fallback_used": False,
                        "candidate_labels": [],
                        "retrieved_examples": [],
                    }
            )
            continue
        if is_real_clause(clause_text):
            validated.append((index, clause_text))
        else:
            results.append(
                {
                        "clause_index": index,
                        "clause_text": clause_text,
                        "predicted_label": "NO_APPLICABLE_LABEL",
                        "clause_type": "NO_APPLICABLE_LABEL",
                        "retrieved_labels": [],
                        "retrieved_scores": [],
                        "classification_status": "NO_APPLICABLE_LABEL",
                        "classification_source": "validator",
                        "fallback_used": False,
                        "candidate_labels": [],
                        "retrieved_examples": [],
                    }
            )

    if not validated:
        raise ValueError(
            "All extracted fragments were rejected by the clause validator. "
            "The document may not contain recognizable contract clauses."
        )

    validated_texts = [text for _, text in validated]

    # Batch-embed all clauses in one call instead of one request per clause.
    _emit(
        progress_callback,
        "embedding",
        "Creating Cohere embeddings for validated clauses",
        current=0,
        total=len(validated_texts),
    )
    query_vectors = embed_queries(cohere_client, validated_texts)
    _emit(
        progress_callback,
        "embedding",
        "Clause embeddings complete",
        current=len(validated_texts),
        total=len(validated_texts),
    )

    total_validated = len(validated)
    context_clauses = [
        {
            "clause_index": original_index,
            "clause_text": clause_text,
            "vector": vector,
        }
        for (original_index, clause_text), vector in zip(validated, query_vectors)
    ]
    for clause_number, ((original_index, clause_text), query_vector) in enumerate(
        zip(validated, query_vectors), start=1
    ):
        _emit(
            progress_callback,
            "clause",
            f"Processing clause {clause_number} of {total_validated}",
            current=clause_number,
            total=total_validated,
            clause_index=original_index,
        )
        # Definitions still receive the same clause-level CUAD classification.
        if is_definition(clause_text):
            _emit(
                progress_callback,
                "clause",
                f"Clause {clause_number} is a definition; classifying against CUAD candidates",
                current=clause_number,
                total=total_validated,
                clause_index=original_index,
            )
        result = classify_clause(
            clause_text=clause_text,
            query_vector=query_vector,
            qdrant_client=qdrant_client,
            labels=labels,
            label_definitions=label_definitions,
            top_k=top_k,
            progress_callback=progress_callback,
        )
        classification_result = {
            "clause_index": original_index,
            "clause_text": clause_text,
            "predicted_label": result["predicted_label"],
            "retrieved_labels": [],
            "retrieved_scores": [],
            "candidate_labels": result.get("candidate_labels", []),
            "raw_retrieved_labels": result["retrieved_labels"],
            "raw_retrieved_scores": result["retrieved_scores"],
            "raw_retrieved_examples": result.get("retrieved_examples", []),
            "classification_status": result["prediction_status"],
            "classification_source": result.get("classification_source", "ollama"),
            "fallback_used": bool(result.get("fallback_used", False)),
            "fallback_reason": result.get("fallback_reason"),
            "classification_confidence": result.get("classification_confidence"),
            "retrieval_status": result.get("retrieval_status", "ok"),
            "retrieval_error": result.get("retrieval_error"),
        }
        compressed_evidence = compress_cuad_evidence(
            clause_id=original_index,
            final_label=classification_result["predicted_label"],
            contract_text=clause_text,
            retrieved_examples=classification_result["raw_retrieved_examples"],
        )
        classification_result["compressed_evidence"] = compressed_evidence
        classification_result["retrieved_examples"] = compressed_evidence
        classification_result["retrieved_labels"] = [item.get("label") for item in compressed_evidence]
        classification_result["retrieved_scores"] = [item.get("score") for item in compressed_evidence]
        results.append(classification_result)
        _emit(
            progress_callback,
            "clause",
            f"Clause {clause_number} complete",
            current=clause_number,
            total=total_validated,
            clause_index=original_index,
        )

    results.sort(key=lambda r: r["clause_index"])
    _emit(progress_callback, "evidence_aggregation", "Aggregating contract-level CUAD evidence", total=len(results))
    assessment = assess_contract_risk(
        results,
        cohere_client=cohere_client,
        qdrant_client=qdrant_client,
        progress_callback=progress_callback,
    )
    _emit(progress_callback, "complete", "Contract analysis complete", total=len(results))
    return {"clauses": results, "contract_risk_assessment": assessment}
