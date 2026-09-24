"""Evidence-constrained contract-level risk aggregation."""

from __future__ import annotations

import json

from ..rag.generator import call_ollama
from .knowledge_base import match_risk_domains

LEVEL_RANK = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}


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
    evidence = str(evidence or "").strip()
    return bool(evidence and any(evidence in text for text in _contract_texts(findings)))


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
        valid.append(
            {
                "clause_id": finding.get("clause_index"),
                "clause_text": finding.get("clause_text", ""),
                "evidence": evidence,
                "risk_type": finding.get("risk_type") or "Contract Risk Finding",
                "risk_level": finding.get("risk_level") if finding.get("risk_level") in LEVEL_RANK else None,
                "risk_domains": list(dict.fromkeys(domains)),
                "reason": finding.get("reason", ""),
                "legal_knowledge": finding.get("legal_knowledge") or [],
            }
        )
    return valid


def _deterministic_level(positive: list[dict]) -> str | None:
    explicit = [item["risk_level"] for item in positive if item.get("risk_level")]
    if explicit:
        return max(explicit, key=lambda level: LEVEL_RANK[level])

    domains = {domain for item in positive for domain in item.get("risk_domains", [])}
    types = {item.get("risk_type") for item in positive}
    financial_interaction = {"Financial Risk", "Liability Risk"}.issubset(domains)
    if financial_interaction or len(positive) >= 3 or len(types) >= 3:
        return "HIGH"
    if len(positive) >= 2 or len(domains) >= 2:
        return "MEDIUM"
    return "LOW"


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
            "reason": item.get("reason") or "",
        }
        for item in findings
    ]


def _synthesis_prompt(positive: list[dict], deterministic_level: str) -> str:
    return f"""You are synthesizing a contract-level risk assessment from validated evidence.
Return JSON only. Do not add evidence, clause IDs, or risk domains that are not present below.
Legal guidance is context only, never contract evidence. Do not expose reasoning_details or hidden reasoning.

Deterministic evidence-backed findings:
{json.dumps(positive, indent=2, ensure_ascii=False)}

Evidence-backed deterministic level: {deterministic_level}

Return:
{{
  "overall_risk": "HIGH | MEDIUM | LOW",
  "reason": "concise synthesis grounded only in the listed findings",
  "recommendations": ["review point"]
}}
"""


def _safe_llm_synthesis(positive: list[dict], deterministic_level: str) -> dict | None:
    try:
        raw = call_ollama(_synthesis_prompt(positive, deterministic_level))
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None
        level = parsed.get("overall_risk")
        reason = str(parsed.get("reason") or "").strip()
        recommendations = parsed.get("recommendations")
        if level not in {"HIGH", "MEDIUM", "LOW"} or not reason:
            return None
        if not isinstance(recommendations, list):
            recommendations = []
        return {
            "overall_risk": level,
            "reason": reason,
            "recommendations": [str(item) for item in recommendations if str(item).strip()],
        }
    except Exception:
        return None


def aggregate_contract_risk(findings: list[dict], *, use_llm: bool = True) -> dict:
    """Aggregate clause findings without averaging scores or trusting prose.

    Only exact evidence already validated against uploaded-contract text is
    eligible for a positive contract-level result.
    """
    positive = _positive_findings(findings)
    insufficient = any(item.get("risk_status") == "INSUFFICIENT_EVIDENCE" for item in findings)
    if not positive:
        status = "INSUFFICIENT_EVIDENCE" if insufficient else "NO_RISK"
        return {
            "overall_status": status,
            "overall_risk": None,
            "risk_domains": [],
            "key_risks": [],
            "risk_summary": [],
            "evidence": [],
            "affected_clauses": [],
            "reason": (
                "Available contract evidence was insufficient to support a contract-level risk finding."
                if insufficient
                else "No evidence-supported contract-level risk finding was identified."
            ),
            "recommendations": [],
            "supporting_legal_guidance": [],
            "supporting_clause_findings": _supporting_clause_findings(findings),
            "synthesis_provider": "none",
        }

    deterministic_level = _deterministic_level(positive)
    risk_domains = list(dict.fromkeys(domain for item in positive for domain in item.get("risk_domains", [])))
    evidence = [
        {
            "clause_id": item["clause_id"],
            "text": item["evidence"],
            "risk_type": item["risk_type"],
        }
        for item in positive
    ]
    key_risks = [
        {
            "risk_type": item["risk_type"],
            "level": item.get("risk_level") or deterministic_level,
            "reason": item["reason"],
            "evidence": [
                {"clause_id": item["clause_id"], "text": item["evidence"]}
            ],
            "risk_domains": item["risk_domains"],
        }
        for item in positive
    ]
    guidance = []
    for item in positive:
        for guidance_item in item.get("legal_knowledge", []):
            if guidance_item not in guidance:
                guidance.append(guidance_item)

    synthesis = _safe_llm_synthesis(positive, deterministic_level) if use_llm else None
    return {
        "overall_status": "POTENTIAL_RISK",
        "overall_risk": synthesis["overall_risk"] if synthesis else deterministic_level,
        "risk_domains": risk_domains,
        "key_risks": key_risks,
        "risk_summary": key_risks,
        "evidence": evidence,
        "affected_clauses": [item["clause_id"] for item in positive],
        "reason": synthesis["reason"] if synthesis else "Multiple evidence-backed clause findings were aggregated using severity, domain interaction, and supporting-clause count.",
        "recommendations": synthesis["recommendations"] if synthesis and synthesis["recommendations"] else _recommendations(positive),
        "supporting_legal_guidance": guidance,
        "supporting_clause_findings": _supporting_clause_findings(findings),
        "synthesis_provider": "ollama" if synthesis else "deterministic_fallback",
    }
