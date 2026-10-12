"""Compatibility shim for the Phase 2 contract risk engine.

The previous single-pass assessor is intentionally no longer used by the main
pipeline. Keep this import path working for callers that still import
assess_contract_risk, but delegate to the new deterministic aggregation layer.
"""
from __future__ import annotations

import json

from .contract_risk_engine import aggregate_clause_risks
from .evidence_compressor import compress_cuad_evidence


def build_contract_evidence(clauses: list[dict]) -> dict:
    """Build the compact compatibility payload used by older integrations."""
    return {
        "classified_clauses": [
            {
                "clause_id": clause.get("clause_index"),
                "contract_text": clause.get("clause_text", ""),
                "label": clause.get("predicted_label"),
                "supporting_evidence": compress_cuad_evidence(
                    clause_id=clause.get("clause_index"),
                    final_label=clause.get("predicted_label"),
                    contract_text=clause.get("clause_text", ""),
                    retrieved_examples=clause.get("retrieved_examples"),
                ),
            }
            for clause in clauses
        ]
    }


def _prompt(evidence: dict, guidance: list[dict], checks: list[dict]) -> str:
    """Return a bounded prompt for legacy callers without raw retrieval dumps."""
    return "COMPACT CONTRACT RISK CONTEXT\n" + json.dumps(
        {"evidence": evidence, "guidance": guidance, "checks": checks},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def assess_contract_risk(
    clauses: list[dict],
    *,
    cohere_client=None,
    qdrant_client=None,
    progress_callback=None,
) -> dict:
    return aggregate_clause_risks(clauses)
