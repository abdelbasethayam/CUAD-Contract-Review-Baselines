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


def aggregate_clause_risks(findings: list[dict], playbook: dict | None = None) -> dict:
    playbook = playbook or load_playbook()
    positive = _valid_positive(findings)
    insufficient = [f for f in findings if f.get("risk_status") == "INSUFFICIENT_EVIDENCE"]

    domain_items = defaultdict(list)
    for finding in positive:
        matches = match_risk_domains(
            str(finding.get("clause_text") or finding.get("risk_type") or finding.get("question") or ""),
            str(finding.get("predicted_label") or finding.get("risk_type") or ""),
            finding.get("provenance", {}).get("deterministic_indicators", []),
        )
        domains = [item.get("risk_domain") for item in matches if item.get("risk_domain")]
        finding["risk_domains"] = list(dict.fromkeys(domains))

        for domain in finding["risk_domains"]:
            domain_items[domain].append(finding)

    key_risks = [
        {
            "clause_id": finding.get("clause_index") if finding.get("clause_index") is not None else finding.get("clause_ids"),
            "check_id": finding.get("check_id"),
            "risk_type": finding.get("risk_type"),
            "raw_support_score": finding.get("raw_support_score"),
            "severity_signal": finding.get("severity_signal"),
            "confidence": finding.get("confidence"),
            "confidence_status": finding.get("confidence_status"),
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
                float(item.get("raw_support_score") or 0.0),
                float(item.get("severity_signal") or 0.0),
            ),
            reverse=True,
        )
    ]

    if positive:
        status = "POTENTIAL_RISK"
        overall_raw_score = round(
            max(float(item.get("raw_support_score") or 0.0) for item in positive),
            4,
        )
        overall_confidence = None
        confidence_status = "UNCALIBRATED"
        overall_risk = None
        reason = (
            "One or more contract provisions contain evidence-supported "
            "playbook findings. Severity and probability are intentionally "
            "uncalibrated until a manual gold set is used."
        )
    elif insufficient:
        status = "INSUFFICIENT_EVIDENCE"
        overall_raw_score = 0.0
        overall_confidence = None
        confidence_status = "UNCALIBRATED"
        overall_risk = None
        reason = (
            "The available evidence did not support a positive risk finding, "
            "but one or more applicable checks could not be resolved reliably."
        )
    else:
        status = "NO_RISK"
        overall_raw_score = 0.0
        overall_confidence = None
        confidence_status = "UNCALIBRATED"
        overall_risk = None
        reason = "No evidence-supported playbook risk finding was identified."

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
            "clauses": sorted({item.get("clause_index") for item in items}),
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
        "overall_raw_risk_score": overall_raw_score,
        "overall_raw_score_semantics": "maximum evidence-support diagnostic; not a probability",
        "severity_status": "UNCALIBRATED",
        "risk_domains": domain_summary,
        "key_risks": key_risks,
        "affected_clauses": affected,
        "reason": reason,
        "gold_status": "PLAYBOOK_DERIVED",
        "playbook_hash": playbook.get("playbook_hash"),
        "clause_findings": findings,
        "unresolved_check_count": len(insufficient),
    }


def build_risk_only_view(findings: list[dict]) -> list[dict]:
    return [
        {
            "clause_id": item.get("clause_index"),
            "clause_type": item.get("predicted_label"),
            "check_id": item.get("check_id"),
            "risk_type": item.get("risk_type"),
            "status": item.get("risk_status"),
            "raw_support_score": item.get("raw_support_score"),
            "confidence": item.get("confidence"),
            "confidence_status": item.get("confidence_status"),
            "severity_signal": item.get("severity_signal"),
            "severity_status": "UNCALIBRATED",
            "why_flagged": item.get("why_flagged"),
            "evidence": item.get("evidence"),
            "ground_truth_status": item.get("ground_truth_status"),
            "provenance": item.get("provenance"),
            "supporting_sources": item.get("supporting_sources"),
        }
        for item in findings
        if item.get("risk_status") != "NO_RISK"
    ]
