"""Deprecated compatibility layer for the retired ordinal severity model.

Phase 2 does not publish HIGH/MEDIUM/LOW/CRITICAL labels or numeric severity
scores. Prediction confidence is produced only by confidence_calibration.py and
only when an adjudicated, contract-disjoint calibration artifact passes its
locked-test gates. These compatibility functions intentionally return no score.
"""
from __future__ import annotations

from typing import Any

SCORE_VERSION = "deprecated-no-severity-v1"
DIMENSIONS = (
    "exposure_magnitude",
    "likelihood_uncertainty",
    "scope_duration",
    "control_weakness",
)


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if 0.0 <= result <= 5.0 else None


def normalize_components(raw: dict[str, Any] | None) -> dict[str, float | None]:
    """Compatibility-only validator; these dimensions no longer drive outputs."""
    raw = raw or {}
    return {key: _number(raw.get(key)) for key in DIMENSIONS}


def default_severity(score: int) -> None:
    """Deprecated. Ordinal severity labels are intentionally not generated."""
    del score
    return None


def is_jurisdiction_sensitive(finding: dict[str, Any]) -> bool:
    blob = " ".join(
        str(finding.get(key) or "")
        for key in ("risk_type", "question", "check_id", "clause_type", "evidence", "why_flagged")
    ).lower()
    return bool(finding.get("jurisdiction_sensitive")) or any(
        term in blob
        for term in (
            "non-compete", "noncompete", "no-solicit", "nonsolicit",
            "competition restriction", "resale price maintenance",
            "liquidated damages", "governing law",
        )
    )


def deterministic_modifiers(
    finding: dict[str, Any],
    *,
    extraction_confidence: float | None = None,
    dependency_missing: bool = False,
    clear_bounded_control: bool = False,
) -> tuple[int, list[dict[str, Any]]]:
    """Deprecated compatibility stub; modifiers no longer produce a score."""
    del finding, extraction_confidence, dependency_missing, clear_bounded_control
    return 0, []


def score_finding(
    finding: dict[str, Any],
    *,
    extraction_confidence: float | None = None,
    dependency_missing: bool = False,
    clear_bounded_control: bool = False,
) -> dict[str, Any]:
    """Deprecated compatibility stub that explicitly refuses ordinal scoring."""
    del extraction_confidence, dependency_missing, clear_bounded_control
    components = normalize_components(
        finding.get("score_components") or finding.get("severity_factors")
    )
    return {
        "score_version": SCORE_VERSION,
        "score_status": "DEPRECATED_NOT_USED",
        "score_components": {},
        "base_score": None,
        "modifiers": [],
        "modifier_total": 0,
        "final_score": None,
        "default_severity": None,
        "severity": None,
        "override_reason": None,
        "human_review_required": True,
        "escalation": "LEGAL_REVIEW",
        "missing_score_components": [key for key in DIMENSIONS if components[key] is None],
    }


def aggregate_contract_triage(
    findings: list[dict[str, Any]],
    *,
    contract_metadata: dict[str, Any] | None = None,
    deterministic_signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Deprecated compatibility shim: return review state, never severity."""
    del contract_metadata, deterministic_signals
    positive = [
        item for item in findings
        if item.get("risk_status") == "POTENTIAL_RISK" and item.get("risk")
    ]
    unresolved = [
        item for item in findings
        if item.get("risk_status") == "INSUFFICIENT_EVIDENCE"
    ]
    return {
        "overall_score": None,
        "overall_severity": None,
        "aggregation_adjustments": [],
        "human_review_required": bool(positive or unresolved),
        "legal_review_required": bool(positive or unresolved),
        "business_owner_review_required": False,
        "privacy_security_review_required": False,
        "exposure_concentration": [],
        "control_gap_count": 0,
        "unreviewed_assumption_count": len(unresolved),
        "high_count": 0,
        "critical_count": 0,
        "two_high_same_domain": False,
        "severity_status": "DEPRECATED_NOT_USED",
    }
