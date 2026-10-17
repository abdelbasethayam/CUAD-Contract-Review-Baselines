"""Evidence-constrained contract-level review status aggregation.

This module intentionally does not assign ordinal severity labels or infer a
contract-level confidence probability. Those quantities were not supported by
an adjudicated benchmark. Confidence, if calibrated, belongs to individual
YES/NO predictions and is not an impact score.
"""
from __future__ import annotations

from .knowledge_base import match_risk_domains


def _contract_texts(findings: list[dict]) -> list[str]:
    texts: list[str] = []
    for finding in findings:
        text = str(finding.get("clause_text") or "")
        if text:
            texts.append(text)
        for context in finding.get("related_contract_context") or []:
            context_text = str(context.get("clause_text") or "")
            if context_text:
                texts.append(context_text)
    return texts


def _valid_evidence(evidence: str, findings: list[dict]) -> bool:
    quote = str(evidence or "").strip()
    return bool(quote and any(quote in text for text in _contract_texts(findings)))


def _positive_findings(findings: list[dict]) -> list[dict]:
    valid: list[dict] = []
    for finding in findings:
        if finding.get("risk_status") != "POTENTIAL_RISK" or not finding.get("risk"):
            continue
        evidence = str(finding.get("evidence") or "").strip()
        if not _valid_evidence(evidence, findings):
            continue
        domains = finding.get("risk_domains") or []
        if not domains:
            domains = [
                item.get("risk_domain")
                for item in match_risk_domains(
                    finding.get("clause_text", ""),
                    finding.get("predicted_label", ""),
                    finding.get("matched_indicators", []),
                )
                if item.get("risk_domain")
            ]
        valid.append({
            "clause_id": finding.get("clause_index"),
            "clause_text": finding.get("clause_text", ""),
            "evidence": evidence,
            "risk_type": finding.get("risk_type") or "Contract Risk Finding",
            "risk_domains": list(dict.fromkeys(domains)),
            "reason": finding.get("reason") or finding.get("why_flagged") or "",
            "legal_knowledge": finding.get("legal_knowledge") or [],
            "confidence": finding.get("confidence"),
            "confidence_status": finding.get("confidence_status", "UNCALIBRATED"),
            "confidence_target": finding.get("confidence_target", "PREDICTION_CORRECTNESS"),
            "provenance": finding.get("provenance") or {},
            "supporting_sources": finding.get("supporting_sources") or [],
        })
    return valid


def _recommendations(positive: list[dict]) -> list[str]:
    recommendations: list[str] = []
    domains = {domain for item in positive for domain in item.get("risk_domains", [])}
    for item in match_risk_domains(
        " ".join(str(finding.get("clause_text") or "") for finding in positive),
        indicators=[str(domain) for domain in domains],
    ):
        guidance = item.get("mitigation_guidance")
        if guidance and guidance not in recommendations:
            recommendations.append(guidance)
    return recommendations


def _supporting_clause_findings(findings: list[dict]) -> list[dict]:
    return [
        {
            "clause_id": item.get("clause_index"),
            "classification_status": item.get("classification_status"),
            "predicted_label": item.get("predicted_label"),
            "risk": bool(item.get("risk")),
            "risk_status": item.get("risk_status"),
            "risk_type": item.get("risk_type"),
            "risk_domains": item.get("risk_domains") or [],
            "evidence": item.get("evidence") or "",
            "reason": item.get("reason") or item.get("why_flagged") or "",
            "confidence": item.get("confidence"),
            "confidence_status": item.get("confidence_status", "UNCALIBRATED"),
            "confidence_target": item.get("confidence_target", "PREDICTION_CORRECTNESS"),
        }
        for item in findings
    ]


def aggregate_contract_risk(findings: list[dict], *, use_llm: bool = False) -> dict:
    """Return evidence-supported categorical status without severity synthesis.

    The legacy use_llm argument is accepted for compatibility but deliberately
    ignored: free-form LLM synthesis must not invent severity or contract-level
    probabilities. This summary is not a legal opinion or a risk-free guarantee.
    """
    del use_llm
    positive = _positive_findings(findings)
    insufficient = any(item.get("risk_status") == "INSUFFICIENT_EVIDENCE" for item in findings)
    if not positive:
        status = "INSUFFICIENT_EVIDENCE" if insufficient else "NO_RISK"
        return {
            "overall_status": status,
            "overall_risk": status,
            "overall_confidence": None,
            "confidence_status": "NOT_CALIBRATED_FOR_CONTRACT_LEVEL",
            "confidence_target": "PREDICTION_CORRECTNESS",
            "risk_domains": [],
            "key_risks": [],
            "risk_summary": [],
            "evidence": [],
            "affected_clauses": [],
            "reason": (
                "Available contract evidence was insufficient to resolve one or more applicable checks."
                if insufficient
                else "No evidence-supported contract-level risk finding was identified by the completed checks. This is not a guarantee that the contract is risk-free."
            ),
            "recommendations": [],
            "supporting_legal_guidance": [],
            "supporting_clause_findings": _supporting_clause_findings(findings),
            "synthesis_provider": "categorical_evidence_aggregation",
            "severity_status": "DEPRECATED_NOT_USED",
        }

    risk_domains = list(dict.fromkeys(domain for item in positive for domain in item.get("risk_domains", [])))
    evidence = [
        {"clause_id": item["clause_id"], "text": item["evidence"], "risk_type": item["risk_type"]}
        for item in positive
    ]
    key_risks = [
        {
            "risk_type": item["risk_type"],
            "reason": item["reason"],
            "evidence": [{"clause_id": item["clause_id"], "text": item["evidence"]}],
            "risk_domains": item["risk_domains"],
            "confidence": item.get("confidence"),
            "confidence_status": item.get("confidence_status"),
            "confidence_target": item.get("confidence_target"),
            "provenance": item.get("provenance"),
            "supporting_sources": item.get("supporting_sources"),
        }
        for item in positive
    ]
    guidance = []
    for item in positive:
        for guidance_item in item.get("legal_knowledge", []):
            if guidance_item not in guidance:
                guidance.append(guidance_item)

    return {
        "overall_status": "POTENTIAL_RISK",
        "overall_risk": "POTENTIAL_RISK",
        "overall_confidence": None,
        "confidence_status": "NOT_CALIBRATED_FOR_CONTRACT_LEVEL",
        "confidence_target": "PREDICTION_CORRECTNESS",
        "risk_domains": risk_domains,
        "key_risks": key_risks,
        "risk_summary": key_risks,
        "evidence": evidence,
        "affected_clauses": [item["clause_id"] for item in positive],
        "reason": "One or more evidence-supported review findings were identified. Clause-level confidence, when calibrated, estimates prediction correctness only; this contract summary does not estimate severity or aggregate probability.",
        "recommendations": _recommendations(positive),
        "supporting_legal_guidance": guidance,
        "supporting_clause_findings": _supporting_clause_findings(findings),
        "synthesis_provider": "categorical_evidence_aggregation",
        "severity_status": "DEPRECATED_NOT_USED",
    }
