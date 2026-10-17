"""Contract-level Phase 2 risk aggregation with no fake probability or severity."""
from __future__ import annotations

from collections import defaultdict
from typing import Callable

from .knowledge_base import match_risk_domains
from .risk_playbook import load_playbook
from .risk_engine import _evidence_valid, _emit

ProgressCallback = Callable[[dict], None]


def _valid_positive(findings: list[dict]) -> list[dict]:
    return [
        finding
        for finding in findings
        if finding.get("risk_status") == "POTENTIAL_RISK"
        and bool(finding.get("risk"))
        and (
            bool(finding.get("evidence"))
            if finding.get("scope") in {"cross_clause", "document"}
            else _evidence_valid(
                str(finding.get("evidence") or ""),
                str(finding.get("clause_text") or ""),
                finding.get("related_contract_context") or [],
            )
        )
    ]


def _domain_clause_ids(findings: list[dict]) -> list[int]:
    clause_ids: set[int] = set()
    for finding in findings:
        candidates = []
        if finding.get("clause_index") is not None:
            candidates.append(finding.get("clause_index"))
        candidates.extend(finding.get("clause_ids") or [])
        for candidate in candidates:
            try:
                clause_ids.add(int(candidate))
            except (TypeError, ValueError):
                continue
    return sorted(clause_ids)


def aggregate_clause_risks(findings: list[dict], playbook: dict | None = None) -> dict:
    playbook = playbook or load_playbook()
    positive = _valid_positive(findings)
    insufficient = [f for f in findings if f.get("risk_status") == "INSUFFICIENT_EVIDENCE"]

    # A check's declared playbook domain is authoritative. Taxonomy keyword
    # matching remains a fallback and is retained separately for audit/debugging;
    # it must not silently relabel a finding when a domain is explicitly declared.
    check_by_id = {}
    for payload in (playbook.get("clause_types") or {}).values():
        for check in payload.get("checklist") or []:
            check_by_id[str(check.get("id"))] = check
    for check in (playbook.get("cross_clause_checks") or []):
        check_by_id[str(check.get("id"))] = check
    for check in (playbook.get("document_level_checks") or []):
        check_by_id[str(check.get("id"))] = check

    domain_items = defaultdict(list)
    for finding in positive:
        check = check_by_id.get(str(finding.get("check_id") or ""), {})
        declared_domain = finding.get("risk_domain") or check.get("risk_domain")
        matches = match_risk_domains(
            str(finding.get("clause_text") or finding.get("risk_type") or finding.get("question") or ""),
            str(finding.get("predicted_label") or finding.get("risk_type") or ""),
            finding.get("provenance", {}).get("deterministic_indicators", []),
        )
        taxonomy_domains = list(dict.fromkeys(
            item.get("risk_domain") for item in matches if item.get("risk_domain")
        ))
        if declared_domain:
            domains = [str(declared_domain)]
            finding["taxonomy_suggested_domains"] = [
                domain for domain in taxonomy_domains if domain != declared_domain
            ]
        else:
            domains = taxonomy_domains
            finding["taxonomy_suggested_domains"] = []
        finding["risk_domain"] = declared_domain
        finding["risk_subdomain"] = finding.get("risk_subdomain") or check.get("risk_subdomain")
        finding["risk_domains"] = list(dict.fromkeys(domains))

        for domain in finding["risk_domains"]:
            domain_items[domain].append(finding)

    # Contract-level confidence is not inferred by averaging clause confidence.
    # The product reports categorical review status and only exposes clause-level
    # confidence when a separate adjudicated calibrator has passed a locked test.
    key_risks = [
        {
            "clause_id": finding.get("clause_index") if finding.get("clause_index") is not None else finding.get("clause_ids"),
            "check_id": finding.get("check_id"),
            "risk_type": finding.get("risk_type"),
            "evidence_clause_index": finding.get("evidence_clause_index"),
            "evidence_scope": finding.get("evidence_scope"),
            "risk_domain": finding.get("risk_domain"),
            "risk_subdomain": finding.get("risk_subdomain"),
            "taxonomy_suggested_domains": finding.get("taxonomy_suggested_domains", []),
            "raw_support_score": finding.get("raw_support_score"),
            "confidence": finding.get("confidence"),
            "confidence_status": finding.get("confidence_status"),
            "confidence_target": finding.get("confidence_target", "PREDICTION_CORRECTNESS"),
            "confidence_calibration_version": finding.get("confidence_calibration_version"),
            "ground_truth_status": finding.get("ground_truth_status"),
            "evidence": finding.get("evidence"),
            "why_flagged": finding.get("why_flagged"),
            "risk_domains": finding.get("risk_domains", []),
            "provenance": finding.get("provenance", {}),
            "supporting_sources": finding.get("supporting_sources", []),
        }
        for finding in sorted(
            positive,
            key=lambda item: (
                int(item.get("clause_index") or min(item.get("clause_ids") or [0])),
                str(item.get("check_id") or ""),
            ),
        )
    ]

    if positive:
        status = "POTENTIAL_RISK"
        overall_risk = status
        overall_confidence = None
        confidence_status = "NOT_CALIBRATED_FOR_CONTRACT_LEVEL"
        reason = (
            "One or more evidence-supported review findings were identified. "
            "Confidence, when available, applies to each individual YES/NO prediction; "
            "no contract-level probability or ordinal severity is calculated."
        )
    elif insufficient:
        status = "INSUFFICIENT_EVIDENCE"
        overall_risk = status
        overall_confidence = None
        confidence_status = "NOT_CALIBRATED_FOR_CONTRACT_LEVEL"
        reason = (
            "One or more applicable checks remain unresolved. An unresolved check "
            "must not be interpreted as a no-risk conclusion."
        )
    else:
        status = "NO_RISK"
        overall_risk = status
        overall_confidence = None
        confidence_status = "NOT_CALIBRATED_FOR_CONTRACT_LEVEL"
        reason = (
            "No evidence-supported playbook risk finding was identified by the completed checks. "
            "This is not a guarantee that the contract is risk-free."
        )

    affected_set = set()
    for finding in positive:
        if finding.get("clause_index") is not None:
            affected_set.add(int(finding["clause_index"]))
        for clause_id in finding.get("clause_ids") or []:
            try:
                affected_set.add(int(clause_id))
            except (TypeError, ValueError):
                continue
    affected = sorted(affected_set)

    domain_summary = [
        {
            "domain": domain,
            "finding_count": len(items),
            "clauses": _domain_clause_ids(items),
            "max_raw_support_score": max(
                float(item.get("raw_support_score") or 0.0) for item in items
            ),
        }
        for domain, items in sorted(domain_items.items())
    ]

    return {
        "status": status,
        "overall_risk": overall_risk,
        "overall_confidence": overall_confidence,
        "confidence_status": confidence_status,
        "confidence_target": "PREDICTION_CORRECTNESS",
        "overall_raw_risk_score": None,
        "overall_raw_score_semantics": "DEPRECATED_NOT_USED",
        "severity_status": "DEPRECATED_NOT_USED",
        "risk_domains": domain_summary,
        "key_risks": key_risks,
        "affected_clauses": affected,
        "reason": reason,
        "gold_status": "PLAYBOOK_DERIVED",
        "playbook_hash": playbook.get("playbook_hash"),
        "rule_registry": playbook.get("rule_registry", {}),
        "clause_findings": findings,
        "unresolved_check_count": len(insufficient),
        "overall_score": None,
        "overall_severity": None,
        "aggregation_adjustments": [],
        "human_review_required": bool(positive or insufficient),
        "high_count": 0,
        "critical_count": 0,
        "two_high_same_domain": False,
    }


def build_risk_only_view(findings: list[dict]) -> list[dict]:
    return [
        {
            "clause_id": item.get("clause_index"),
            "clause_type": item.get("predicted_label"),
            "check_id": item.get("check_id"),
            "risk_type": item.get("risk_type"),
            "evidence_clause_index": item.get("evidence_clause_index"),
            "evidence_scope": item.get("evidence_scope"),
            "risk_domain": item.get("risk_domain"),
            "risk_subdomain": item.get("risk_subdomain"),
            "status": item.get("risk_status"),
            "raw_support_score": item.get("raw_support_score"),
            "confidence": item.get("confidence"),
            "confidence_status": item.get("confidence_status"),
            "confidence_target": item.get("confidence_target", "PREDICTION_CORRECTNESS"),
            "confidence_calibration_version": item.get("confidence_calibration_version"),
            "why_flagged": item.get("why_flagged"),
            "evidence": item.get("evidence"),
            "ground_truth_status": item.get("ground_truth_status"),
            "provenance": item.get("provenance"),
            "supporting_sources": item.get("supporting_sources"),
        }
        for item in findings
        if item.get("risk_status") != "NO_RISK"
    ]
