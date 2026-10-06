"""Deterministic risk severity scoring and escalation policy.

Scores are internal triage signals, not legal standards or probabilities.
"""

from __future__ import annotations

from typing import Any

SCORE_VERSION = "commercial-risk-score-v1"

DIMENSIONS = (
    "exposure_magnitude",
    "likelihood_uncertainty",
    "scope_duration",
    "control_weakness",
)

DEFAULT_SEVERITY_BANDS = (
    (16, "CRITICAL"),
    (12, "HIGH"),
    (8, "MEDIUM"),
    (4, "LOW"),
    (0, "INFORMATIONAL"),
)

JURISDICTION_SENSITIVE_TERMS = (
    "non-compete", "noncompete", "no-solicit", "nonsolicit", "exclusivity",
    "price restriction", "resale price", "competition", "enforceability",
    "liquidated damages",
)

CRITICAL_TERMS = (
    "uncapped", "unlimited liability", "without limitation",
    "loss of core intellectual property", "loss of core ip",
    "loss of core data rights", "perpetual transfer of all data rights",
    "defeats the central bargain", "cannot terminate", "cannot transition",
    "existential",
)

HIGH_TERMS = (
    "missing ownership chain", "no practical remedy", "perpetual", "irrevocable",
    "business-critical", "security obligation without remedy",
)


def _number(value: Any) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if 0.0 <= x <= 5.0 else None


def normalize_components(raw: dict[str, Any] | None) -> dict[str, float | None]:
    raw = raw or {}
    aliases = {
        "exposure_magnitude": ("exposure_magnitude", "impact"),
        "likelihood_uncertainty": ("likelihood_uncertainty", "likelihood", "uncertainty"),
        "scope_duration": ("scope_duration", "scope"),
        "control_weakness": ("control_weakness", "control"),
    }
    return {
        key: next((_number(raw.get(alias)) for alias in aliases[key] if _number(raw.get(alias)) is not None), None)
        for key in DIMENSIONS
    }


def default_severity(score: int) -> str:
    for minimum, label in DEFAULT_SEVERITY_BANDS:
        if score >= minimum:
            return label
    return "INFORMATIONAL"


def _text_blob(finding: dict[str, Any]) -> str:
    return " ".join(
        str(finding.get(key) or "")
        for key in ("risk_type", "question", "check_id", "clause_type", "evidence", "why_flagged")
    ).lower()


def deterministic_modifiers(
    finding: dict[str, Any],
    *,
    extraction_confidence: float | None = None,
    dependency_missing: bool = False,
    clear_bounded_control: bool = False,
) -> tuple[int, list[dict[str, Any]]]:
    blob = _text_blob(finding)
    modifiers: list[dict[str, Any]] = []
    scope = str(finding.get("scope") or "").lower()

    if scope == "cross_clause" and bool(finding.get("deterministic_cross_check")):
        modifiers.append({"name": "cross_clause_conflict", "delta": 2, "reason": "deterministic interaction signal"})
    if any(term in blob for term in JURISDICTION_SENSITIVE_TERMS):
        modifiers.append({"name": "jurisdiction_sensitive", "delta": 2, "reason": "jurisdiction/competition-sensitive topic"})
    if extraction_confidence is not None and extraction_confidence < 0.75:
        modifiers.append({"name": "low_extraction_confidence", "delta": 1, "reason": "material clause extraction confidence below 0.75"})
    if dependency_missing:
        modifiers.append({"name": "missing_dependency", "delta": 1, "reason": "defined or incorporated dependency is missing"})
    if clear_bounded_control:
        modifiers.append({"name": "effective_control", "delta": -2, "reason": "clear cap/control/remedy bounds the same exposure"})

    return max(-20, min(20, sum(int(item["delta"]) for item in modifiers))), modifiers


def score_finding(
    finding: dict[str, Any],
    *,
    extraction_confidence: float | None = None,
    dependency_missing: bool = False,
    clear_bounded_control: bool = False,
) -> dict[str, Any]:
    components = normalize_components(finding.get("score_components") or finding.get("severity_factors"))
    missing = [name for name, value in components.items() if value is None]
    if missing:
        return {
            "score_version": SCORE_VERSION,
            "score_components": components,
            "base_score": None,
            "modifiers": [],
            "modifier_total": 0,
            "final_score": None,
            "default_severity": None,
            "severity": None,
            "override_reason": None,
            "human_review_required": True,
            "escalation": "HIGH_REVIEW",
            "missing_score_components": missing,
        }

    base_score = int(round(sum(float(components[name]) for name in DIMENSIONS)))
    delta, modifiers = deterministic_modifiers(
        finding,
        extraction_confidence=extraction_confidence,
        dependency_missing=dependency_missing,
        clear_bounded_control=clear_bounded_control,
    )
    final_score = max(0, min(20, base_score + delta))

    blob = _text_blob(finding)
    critical_override = any(term in blob for term in CRITICAL_TERMS)
    high_override = any(term in blob for term in HIGH_TERMS) or any(
        name == "jurisdiction_sensitive" for name in (m["name"] for m in modifiers)
    )

    override_reason = None
    severity = default_severity(final_score)
    if critical_override:
        severity = "CRITICAL"
        override_reason = "critical_override"
    elif high_override and severity in {"INFORMATIONAL", "LOW", "MEDIUM"}:
        severity = "HIGH"
        override_reason = "high_override"

    human_review_required = severity in {"HIGH", "CRITICAL"} or bool(
        any(m["name"] == "jurisdiction_sensitive" for m in modifiers)
    )
    if "conflict" in blob:
        human_review_required = True

    return {
        "score_version": SCORE_VERSION,
        "score_components": {k: round(float(v), 2) for k, v in components.items()},
        "base_score": base_score,
        "modifiers": modifiers,
        "modifier_total": delta,
        "final_score": final_score,
        "default_severity": default_severity(final_score),
        "severity": severity,
        "override_reason": override_reason,
        "human_review_required": human_review_required,
        "escalation": "LEGAL_REVIEW" if severity in {"HIGH", "CRITICAL"} else (
            "BUSINESS_OWNER_REVIEW" if any(term in blob for term in ("spend", "revenue", "exclusivity", "capacity", "exit")) else "STANDARD_REVIEW"
        ),
        "missing_score_components": missing,
    }


def aggregate_contract_triage(findings: list[dict[str, Any]]) -> dict[str, Any]:
    positive = [f for f in findings if f.get("risk_status") == "POTENTIAL_RISK" and f.get("risk")]
    if not positive:
        return {
            "overall_score": 0,
            "overall_severity": None,
            "aggregation_adjustments": [],
            "human_review_required": False,
        }

    scored = sorted(
        [(int(f["final_score"]), f) for f in positive if f.get("final_score") is not None],
        key=lambda x: x[0],
        reverse=True,
    )
    adjustments: list[dict[str, Any]] = []

    blob = " ".join(_text_blob(f) for f in positive)
    stack_terms = {
        "exclusivity": "exclusivity" in blob,
        "minimum_commitment": "minimum commitment" in blob,
        "termination": "termination" in blob,
        "volume_restriction": "volume restriction" in blob,
        "price_restriction": "price restriction" in blob,
        "mfn": "most favored nation" in blob or "mf n" in blob,
        "revenue_share": "revenue share" in blob or "profit share" in blob,
    }
    if sum(stack_terms.values()) >= 2:
        adjustments.append({
            "name": "economic_or_exit_stack",
            "delta": 2,
            "reason": "multiple interacting commercial constraints detected",
            "signals": [k for k,v in stack_terms.items() if v],
        })

    high_count = sum(1 for _, item in scored if item.get("severity") == "HIGH")
    critical_count = sum(1 for _, item in scored if item.get("severity") == "CRITICAL")
    if critical_count:
        adjustments.append({"name": "critical_override", "delta": 20, "reason": "critical finding exists"})
    if high_count >= 3:
        adjustments.append({"name": "multiple_high_findings", "delta": 2, "reason": "three or more high findings overall"})

    domain_counts: dict[str, int] = {}
    for item in positive:
        for domain in item.get("risk_domains", []) or []:
            domain_counts[str(domain)] = domain_counts.get(str(domain), 0) + (1 if item.get("severity") == "HIGH" else 0)
    high_domain = [k for k,v in domain_counts.items() if v >= 2]
    if high_domain:
        adjustments.append({"name": "high_domain_cluster", "delta": 2, "reason": "two or more high findings in one risk domain", "domains": high_domain})

    incomplete_scores = len(scored) < len(positive)
    if not scored:
        overall = None
        severity = None
    else:
        overall = min(20, max(0, scored[0][0] + sum(int(x["delta"]) for x in adjustments)))
        severity = "CRITICAL" if critical_count else default_severity(overall)
    human = incomplete_scores or severity in {"HIGH", "CRITICAL"} or any(item.get("human_review_required") for item in positive)

    return {
        "overall_score": overall,
        "overall_severity": severity,
        "aggregation_adjustments": adjustments,
        "human_review_required": human,
        "high_count": high_count,
        "critical_count": critical_count,
        "two_high_same_domain": bool(high_domain),
    }


__all__ = ["SCORE_VERSION", "score_finding", "aggregate_contract_triage"]
