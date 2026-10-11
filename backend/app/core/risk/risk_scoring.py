"""Deterministic Phase 2 risk triage score, overrides, aggregation, and escalation.

The numeric score is an internal review-prioritization instrument. It is not a
legal standard and is not a probability. Probability is calibrated separately
against a locked human-adjudicated set.
"""
from __future__ import annotations

from typing import Any

SCORE_VERSION = "commercial-risk-score-v2"
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

JURISDICTION_SENSITIVE_RISK_TYPES = {
    "non-compete",
    "noncompete",
    "no-solicit",
    "nonsolicit",
    "exclusivity",
    "price restriction",
    "resale price maintenance",
    "competition restriction",
}
CRITICAL_RISK_TEXT = (
    "uncapped core exposure",
    "effectively uncapped core exposure",
    "core intellectual property loss",
    "core ip loss",
    "core data ownership loss",
    "defeats the central bargain",
    "business-critical service cannot terminate",
    "business-critical service cannot transition",
    "existential exposure",
)
HIGH_RISK_TEXT = (
    "missing ownership chain",
    "no practical remedy",
    "business-critical warranty",
    "business-critical security",
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
        key: next(
            (
                _number(raw.get(alias))
                for alias in aliases[key]
                if _number(raw.get(alias)) is not None
            ),
            None,
        )
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
        for key in (
            "risk_type",
            "question",
            "check_id",
            "clause_type",
            "evidence",
            "why_flagged",
        )
    ).lower()


def _explicit_override(finding: dict[str, Any], key: str) -> bool:
    raw = finding.get("override_flags")
    return isinstance(raw, dict) and bool(raw.get(key))


def is_jurisdiction_sensitive(finding: dict[str, Any]) -> bool:
    if bool(finding.get("jurisdiction_sensitive")):
        return True
    risk_type = str(finding.get("risk_type") or "").strip().lower()
    if risk_type in JURISDICTION_SENSITIVE_RISK_TYPES:
        return True
    # Only a small, controlled topic set triggers the modifier. In particular,
    # liquidated damages alone does NOT receive a jurisdiction modifier.
    return any(
        term in _text_blob(finding)
        for term in ("competition restriction", "resale price maintenance", "noncompete", "non-compete", "no-solicit", "nonsolicit")
    )


def deterministic_modifiers(
    finding: dict[str, Any],
    *,
    extraction_confidence: float | None = None,
    dependency_missing: bool = False,
    clear_bounded_control: bool = False,
) -> tuple[int, list[dict[str, Any]]]:
    modifiers: list[dict[str, Any]] = {}
    entries: list[dict[str, Any]] = []
    scope = str(finding.get("scope") or "").lower()

    cross_clause_conflict = bool(
        finding.get("validated_cross_clause_conflict")
        or (
            scope == "cross_clause"
            and finding.get("deterministic_cross_check")
            and finding.get("conflict_confirmed")
        )
    )
    if cross_clause_conflict:
        entries.append({
            "name": "cross_clause_conflict",
            "delta": 2,
            "reason": "independently validated cross-clause conflict",
        })

    if is_jurisdiction_sensitive(finding):
        entries.append({
            "name": "jurisdiction_sensitive",
            "delta": 2,
            "reason": "jurisdiction/competition-sensitive topic",
        })

    if extraction_confidence is not None and extraction_confidence < 0.75:
        entries.append({
            "name": "low_extraction_confidence",
            "delta": 1,
            "reason": "material clause extraction confidence below 0.75",
        })

    if dependency_missing:
        entries.append({
            "name": "missing_dependency",
            "delta": 1,
            "reason": "defined or incorporated dependency is missing",
        })

    if clear_bounded_control:
        entries.append({
            "name": "effective_control",
            "delta": -2,
            "reason": "clear cap/control/remedy bounds the same exposure",
        })

    delta = sum(int(item["delta"]) for item in entries)
    return max(-20, min(20, delta)), entries


def score_finding(
    finding: dict[str, Any],
    *,
    extraction_confidence: float | None = None,
    dependency_missing: bool = False,
    clear_bounded_control: bool = False,
) -> dict[str, Any]:
    components = normalize_components(
        finding.get("score_components") or finding.get("severity_factors")
    )
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

    critical_override = (
        _explicit_override(finding, "uncapped_core_exposure")
        or _explicit_override(finding, "core_ip_or_data_loss")
        or _explicit_override(finding, "business_critical_exit_failure")
        or _explicit_override(finding, "credible_prohibited_or_antitrust_concern")
        or _explicit_override(finding, "central_bargain_failure")
        or any(term in blob for term in CRITICAL_RISK_TEXT)
    )
    high_override = (
        _explicit_override(finding, "missing_ownership_chain")
        or _explicit_override(finding, "business_critical_no_practical_remedy")
        or is_jurisdiction_sensitive(finding)
        or any(term in blob for term in HIGH_RISK_TEXT)
    )

    severity = default_severity(final_score)
    override_reason = None
    if critical_override:
        severity = "CRITICAL"
        override_reason = "critical_override"
    elif high_override and severity in {"INFORMATIONAL", "LOW", "MEDIUM"}:
        severity = "HIGH"
        override_reason = "high_override"

    human_review_required = severity in {"HIGH", "CRITICAL"} or is_jurisdiction_sensitive(finding)
    review_escalation = "LEGAL_REVIEW" if severity in {"HIGH", "CRITICAL"} else "STANDARD_REVIEW"

    if bool(finding.get("source_conflict")) or bool(finding.get("unsupported_legal_claim")):
        human_review_required = True
        review_escalation = "HIGH_REVIEW"

    calibrated_confidence = finding.get("confidence")
    if calibrated_confidence is not None and float(calibrated_confidence) < 0.75:
        human_review_required = True
        review_escalation = "HIGH_REVIEW"
        if severity in {"INFORMATIONAL", "LOW", "MEDIUM"}:
            override_reason = "minimum_evidence_override"
            severity = "HIGH"

    if finding.get("risk_domains") and any(
        str(domain).lower() in {"privacy risk", "security risk"} for domain in finding["risk_domains"]
    ):
        review_escalation = "PRIVACY_SECURITY_REVIEW"

    if any(term in blob for term in ("spend", "revenue", "capacity", "exit timing")):
        if review_escalation == "STANDARD_REVIEW":
            review_escalation = "BUSINESS_OWNER_REVIEW"

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
        "escalation": review_escalation,
        "missing_score_components": [],
    }


def aggregate_contract_triage(
    findings: list[dict[str, Any]],
    *,
    contract_metadata: dict[str, Any] | None = None,
    deterministic_signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    positive = [
        f for f in findings
        if f.get("risk_status") == "POTENTIAL_RISK" and f.get("risk")
    ]
    if not positive:
        return {
            "overall_score": 0,
            "overall_severity": None,
            "aggregation_adjustments": [],
            "human_review_required": False,
            "legal_review_required": False,
            "business_owner_review_required": False,
            "privacy_security_review_required": False,
            "exposure_concentration": [],
            "control_gap_count": 0,
            "unreviewed_assumption_count": 0,
            "high_count": 0,
            "critical_count": 0,
            "two_high_same_domain": False,
        }

    scored = [
        (int(f["final_score"]), f)
        for f in positive
        if f.get("final_score") is not None
    ]
    adjustments: list[dict[str, Any]] = []

    # Risk concentration is based on triage-score mass, not raw finding count.
    domain_scores: dict[str, float] = {}
    for _, finding in scored:
        for domain in finding.get("risk_domains", []) or []:
            domain_scores[str(domain)] = domain_scores.get(str(domain), 0.0) + float(finding.get("final_score") or 0)
    total_domain_score = sum(domain_scores.values())
    exposure_concentration = [
        {
            "domain": domain,
            "score": round(score, 2),
            "share": round(score / total_domain_score, 4) if total_domain_score else 0.0,
        }
        for domain, score in sorted(domain_scores.items(), key=lambda item: item[1], reverse=True)
    ]

    control_gap_count = sum(
        1 for _, finding in scored
        if float((finding.get("score_components") or {}).get("control_weakness") or 0) >= 3
    )

    blob = " ".join(_text_blob(f) for f in positive)
    stack_terms = {
        "exclusivity": "exclusivity" in blob,
        "minimum_commitment": "minimum commitment" in blob,
        "termination": "termination" in blob,
        "volume_restriction": "volume restriction" in blob,
        "price_restriction": "price restriction" in blob,
        "mfn": "most favored nation" in blob,
        "revenue_share": "revenue share" in blob or "profit share" in blob,
    }
    named_stack = sum(stack_terms.values()) >= 2

    medium_stack_count = sum(1 for _, finding in scored if finding.get("severity") == "MEDIUM") if named_stack else 0
    if named_stack:
        adjustments.append({
            "name": "economic_or_exit_stack",
            "delta": 2,
            "reason": "multiple interacting commercial constraints detected",
            "signals": [key for key, value in stack_terms.items() if value],
        })
    if medium_stack_count >= 5:
        adjustments.append({
            "name": "five_medium_cross_clause_stack",
            "delta": 2,
            "reason": "five or more medium findings participate in a named interaction stack",
        })

    high_count = sum(1 for _, item in scored if item.get("severity") == "HIGH")
    critical_count = sum(1 for _, item in scored if item.get("severity") == "CRITICAL")
    if critical_count:
        adjustments.append({"name": "critical_override", "delta": 20, "reason": "critical finding exists"})
    if high_count >= 3:
        adjustments.append({"name": "multiple_high_findings", "delta": 2, "reason": "three or more high findings overall"})

    domain_high_counts: dict[str, int] = {}
    for _, item in scored:
        if item.get("severity") != "HIGH":
            continue
        for domain in item.get("risk_domains", []) or []:
            domain_high_counts[str(domain)] = domain_high_counts.get(str(domain), 0) + 1
    high_domain = [domain for domain, count in domain_high_counts.items() if count >= 2]
    if high_domain:
        adjustments.append({
            "name": "high_domain_cluster",
            "delta": 2,
            "reason": "two or more high findings in one risk domain",
            "domains": high_domain,
        })

    missing_core_metadata = []
    metadata = contract_metadata or {}
    for field in ("parties", "governing_law"):
        value = metadata.get(field)
        if not value:
            missing_core_metadata.append(field)
    if missing_core_metadata and any(
        item.get("severity") in {"HIGH", "CRITICAL"} for _, item in scored
    ):
        adjustments.append({
            "name": "missing_core_contract_metadata",
            "delta": 1,
            "reason": "high/critical finding with missing party or governing-law metadata",
            "fields": missing_core_metadata,
        })

    incomplete_scores = len(scored) < len(positive)
    if not scored:
        overall, severity = None, None
    else:
        overall = min(20, max(0, scored[0][0] + sum(int(x["delta"]) for x in adjustments)))
        severity = "CRITICAL" if critical_count else default_severity(overall)

    legal_review_required = bool(
        critical_count
        or high_count >= 3
        or high_domain
        or medium_stack_count >= 5
        or (
            any(item.get("severity") in {"HIGH", "CRITICAL"} for _, item in scored)
            and bool(missing_core_metadata)
        )
    )
    business_owner_review_required = bool(
        any(
            term in blob
            for term in ("minimum commitment", "revenue share", "spend", "capacity", "exclusivity", "exit timing")
        )
    )
    privacy_security_review_required = bool(
        any(
            term in blob
            for term in ("data", "privacy", "security", "confidentiality", "ai-use")
        )
    )

    unreviewed_assumption_count = sum(
        1 for finding in findings
        if str(finding.get("risk_status") or "").upper() in {"INSUFFICIENT_EVIDENCE", "CONFLICT"}
        or str(finding.get("finding_status") or "").upper() in {"UNCERTAIN", "CONFLICT"}
    )

    return {
        "overall_score": overall,
        "overall_severity": severity,
        "aggregation_adjustments": adjustments,
        "human_review_required": incomplete_scores or legal_review_required or business_owner_review_required or privacy_security_review_required,
        "legal_review_required": legal_review_required,
        "business_owner_review_required": business_owner_review_required,
        "privacy_security_review_required": privacy_security_review_required,
        "exposure_concentration": exposure_concentration,
        "control_gap_count": control_gap_count,
        "unreviewed_assumption_count": unreviewed_assumption_count,
        "high_count": high_count,
        "critical_count": critical_count,
        "two_high_same_domain": bool(high_domain),
    }


__all__ = [
    "SCORE_VERSION",
    "score_finding",
    "aggregate_contract_triage",
    "default_severity",
]
