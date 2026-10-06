"""Compatibility shim for the Phase 2 contract risk engine.

The previous single-pass assessor is intentionally no longer used by the main
pipeline. Keep this import path working for callers that still import
assess_contract_risk, but delegate to the new deterministic aggregation layer.
"""
from __future__ import annotations

from .contract_risk_engine import aggregate_clause_risks


def assess_contract_risk(
    clauses: list[dict],
    *,
    cohere_client=None,
    qdrant_client=None,
    progress_callback=None,
) -> dict:
    return aggregate_clause_risks(clauses)
