"""Single-pass, evidence-grounded contract-level risk assessment."""

from __future__ import annotations

import json
import re
from typing import Callable

from ..config import LEGAL_KNOWLEDGE_TOP_K
from ..config import OLLAMA_MODEL
from ..legal_knowledge.retriever import (
    CATEGORY_QUERY_TERMS,
    map_clause_category,
    retrieve_legal_guidance,
)
from ..rag.generator import call_ollama
from .knowledge_base import match_risk_domains, risk_guidance_for_prompt
from .evidence_compressor import compress_cuad_evidence, compress_legal_guidance

ProgressCallback = Callable[[dict], None]
UNAVAILABLE = "RISK_ANALYSIS_UNAVAILABLE"
VALID_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL", "NO_SIGNIFICANT_RISK"}
VALID_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def _compact_supporting_evidence(items: list[dict]) -> list[dict]:
    """Keep only the fields needed by the contract-risk prompt."""
    return [
        {
            **({"source_id": item["source_id"]} if item.get("source_id") else {}),
            "label": item.get("label") or item.get("clause_type"),
            "score": item.get("score"),
            "quote": item.get("quote") or item.get("clause_text"),
        }
        for item in items[:2]
        if item.get("quote") or item.get("clause_text")
    ]


def _emit(callback: ProgressCallback | None, stage: str, message: str, **details) -> None:
    if callback:
        callback({"type": "progress", "stage": stage, "message": message, **details})


def extract_contract_metadata(clauses: list[dict]) -> dict:
    text = "\n".join(str(item.get("clause_text") or "") for item in clauses)
    metadata: dict[str, object] = {}
    parties = re.findall(
        r"(?:between|by and between)\s+(.{2,120}?)\s+and\s+(.{2,120}?)(?:\.|,|\s+as of\b)",
        text,
        re.IGNORECASE,
    )
    if parties:
        metadata["parties"] = list(dict.fromkeys(parties[0]))
    effective = re.search(
        r"(?:effective date|entered into on|dated as of)\s*[:\-]?\s*([^.;\n]{3,60})",
        text,
        re.IGNORECASE,
    )
    if effective:
        metadata["effective_date"] = effective.group(1).strip()
    governing = re.search(
        r"governed by(?: and construed in accordance with)?\s+(?:the laws of\s+)?([^.;\n]{3,100})",
        text,
        re.IGNORECASE,
    )
    if governing:
        metadata["governing_law"] = governing.group(1).strip()
    duration = re.findall(
        r"(?:term|renew|renewal).{0,180}?\b\d+\s+(?:days?|months?|years?)\b[^.;\n]*",
        text,
        re.IGNORECASE,
    )
    if duration:
        metadata["duration_or_renewal"] = list(dict.fromkeys(item.strip() for item in duration[:5]))
    return metadata


def build_contract_evidence(clauses: list[dict]) -> dict:
    classified = []
    domains = []
    for clause in clauses:
        label = str(clause.get("predicted_label") or "NO_APPLICABLE_LABEL")
        text = str(clause.get("clause_text") or "")
        if label == "NO_APPLICABLE_LABEL":
            category = None
        else:
            category = map_clause_category(label)
        taxonomy = match_risk_domains(text, label)
        domains.extend(item.get("risk_domain") for item in taxonomy if item.get("risk_domain"))
        supporting_evidence = clause.get("compressed_evidence")
        if supporting_evidence is None:
            supporting_evidence = compress_cuad_evidence(
                clause_id=clause.get("clause_index"),
                final_label=label,
                contract_text=text,
                retrieved_examples=clause.get("retrieved_examples") or [],
            )
        classified.append(
            {
                "clause_id": clause.get("clause_index"),
                "contract_text": text,
                "label": label,
                "classification_status": clause.get("classification_status"),
                "classification_confidence": clause.get("classification_confidence"),
                "category": category,
                "supporting_evidence": _compact_supporting_evidence(supporting_evidence),
            }
        )
    risk_relevant = [
        item for item in classified
        if item["category"] or item["label"] != "NO_APPLICABLE_LABEL"
    ]
    return {
        "contract_metadata": extract_contract_metadata(clauses),
        "classified_clauses": classified,
        "risk_relevant_evidence": risk_relevant,
        "risk_domains": list(dict.fromkeys(domain for domain in domains if domain)),
    }


def retrieve_contract_guidance(
    evidence: dict,
    *,
    cohere_client=None,
    qdrant_client=None,
    progress_callback: ProgressCallback | None = None,
) -> list[dict]:
    categories = list(dict.fromkeys(
        item["category"]
        for item in evidence.get("classified_clauses", [])
        if item.get("category")
    ))[:6]
    guidance: list[dict] = []
    _emit(progress_callback, "legal_guidance", "Selecting contract-level legal guidance domains", total=len(categories))
    for category in categories:
        relevant_text = " ".join(
            item["contract_text"][:700]
            for item in evidence["classified_clauses"]
            if item.get("category") == category
        )
        query = f"{category} {CATEGORY_QUERY_TERMS.get(category, '')} {relevant_text}".strip()
        items = retrieve_legal_guidance(
            query,
            category,
            cohere_client=cohere_client,
            qdrant_client=qdrant_client,
            top_k=LEGAL_KNOWLEDGE_TOP_K,
            progress_callback=progress_callback,
        )
        for item in items:
            key = (item.get("source_url"), item.get("title"), item.get("retrieved_text"))
            if not any((old.get("source_url"), old.get("title"), old.get("retrieved_text")) == key for old in guidance):
                guidance.append(item)
    guidance.sort(key=lambda item: float(item.get("relevance_score") or 0), reverse=True)
    return compress_legal_guidance(
        guidance,
        max_items=max(1, LEGAL_KNOWLEDGE_TOP_K * 2),
    )


def _prompt(evidence: dict, guidance: list[dict], taxonomy: list[dict]) -> str:
    schema = {
        "overall_risk": "LOW|MEDIUM|HIGH|CRITICAL|NO_SIGNIFICANT_RISK",
        "summary": "Short contract-level summary.",
        "risk_domains": [{
            "domain": "Liability",
            "severity": "LOW|MEDIUM|HIGH|CRITICAL",
            "title": "specific finding",
            "description": "what the provision does",
            "evidence": [{"clause_id": 0, "quote": "exact short quote"}],
            "impact": "potential impact",
            "likelihood": "LOW|MEDIUM|HIGH",
            "exposure": "financial or operational exposure",
            "reasoning": "why this is a risk rather than a normal obligation",
            "recommendation": "focused review point",
        }],
        "positive_protections": [],
        "missing_protections": [],
        "cross_clause_findings": [{"clauses": [0, 1], "finding": "combined exposure", "severity": "HIGH"}],
        "limitations": [],
    }
    return f"""You are performing contract risk assessment, not contract classification. This is not legal advice.
Return exactly one valid JSON object and nothing else.
Do not use Markdown, code fences, comments, explanations, or text outside the JSON object.
Use only the clause IDs and exact contract text supplied in this prompt.
Do not invent facts, obligations, clause IDs, quotes, or enforceability conclusions.
Every risk finding must cite one or more existing clause IDs and short exact quotes copied from the contract evidence.
A CUAD category alone does not establish risk. Distinguish normal obligations from meaningful contractual exposure.
Consider asymmetry, financial magnitude, scope, missing protections only when supported, and cross-clause interactions.
Prefer precise findings over many weak findings. If there is no supported risk, use overall_risk NO_SIGNIFICANT_RISK and an empty risk_domains array.
Use valid JSON double quotes, no trailing commas, and arrays for every list field. Keep the response concise.

CONTRACT CONTEXT
{json.dumps(evidence.get('contract_metadata', {}), indent=2, ensure_ascii=False)}

COMPACT CONTRACT RISK CONTEXT
{json.dumps(evidence.get('risk_relevant_evidence', []), separators=(',', ':'), ensure_ascii=False)}

LEGAL GUIDANCE
{json.dumps(guidance, indent=2, ensure_ascii=False)}

RISK TAXONOMY GUIDANCE
{json.dumps(taxonomy, indent=2, ensure_ascii=False)}

ANALYSIS TASK
Assess liability, indemnification, termination, penalties, insurance, assignment/change of control, renewal, disputes, payment, IP, confidentiality/data protection, and performance obligations only when supported by evidence.

OUTPUT SCHEMA
{json.dumps(schema, indent=2, ensure_ascii=False)}
"""


def _parse(raw: str, clauses: list[dict]) -> dict | None:
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict) or parsed.get("overall_risk") not in VALID_LEVELS:
        return None
    if not isinstance(parsed.get("summary"), str) or not parsed["summary"].strip():
        return None
    clause_ids = {item.get("clause_index") for item in clauses}
    domains = parsed.get("risk_domains")
    if not isinstance(domains, list):
        return None
    for domain in domains:
        if not isinstance(domain, dict) or domain.get("severity") not in VALID_SEVERITIES:
            return None
        citations = domain.get("evidence")
        if not isinstance(citations, list) or not citations:
            return None
        for citation in citations:
            if citation.get("clause_id") not in clause_ids or not str(citation.get("quote") or "").strip():
                return None
            source = next((item.get("clause_text", "") for item in clauses if item.get("clause_index") == citation["clause_id"]), "")
            if citation["quote"] not in source:
                return None
    for key in ("positive_protections", "missing_protections", "cross_clause_findings", "limitations"):
        if not isinstance(parsed.get(key), list):
            return None
    return parsed


def unavailable(reason: str, guidance: list[dict] | None = None) -> dict:
    return {
        "status": UNAVAILABLE,
        "overall_risk": None,
        "summary": reason,
        "risk_domains": [],
        "positive_protections": [],
        "missing_protections": [],
        "cross_clause_findings": [],
        "limitations": [reason],
        "supporting_legal_guidance": guidance or [],
    }


def assess_contract_risk(
    clauses: list[dict],
    *,
    cohere_client=None,
    qdrant_client=None,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    evidence = build_contract_evidence(clauses)
    taxonomy = risk_guidance_for_prompt(
        [item for item in match_risk_domains(
            " ".join(item["contract_text"] for item in evidence["classified_clauses"]),
            indicators=evidence.get("risk_domains", []),
        )]
    )
    try:
        guidance = retrieve_contract_guidance(
            evidence,
            cohere_client=cohere_client,
            qdrant_client=qdrant_client,
            progress_callback=progress_callback,
        )
    except Exception as exc:
        return unavailable(f"Contract-level legal guidance retrieval failed: {exc}")
    _emit(progress_callback, "risk_assessment", "Running one contract-level risk assessment")
    prompt = _prompt(evidence, guidance, taxonomy)
    try:
        parsed = _parse(call_ollama(prompt, model=OLLAMA_MODEL), clauses)
    except Exception as exc:
        return unavailable(f"Contract-level risk assessment failed: {exc}", guidance)
    if parsed is None:
        return unavailable("The risk-analysis model returned malformed or unsupported JSON.", guidance)
    parsed["status"] = "COMPLETED"
    parsed["supporting_legal_guidance"] = guidance
    _emit(progress_callback, "risk_assessment", "Contract-level risk assessment complete")
    return parsed
