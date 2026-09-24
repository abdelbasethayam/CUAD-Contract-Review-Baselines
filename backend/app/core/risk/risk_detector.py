"""Evidence-grounded clause-level risk analysis.

CUAD classification remains candidate-constrained and separate from risk. Risk
reasoning uses the current clause and semantically related clauses from the
same uploaded contract as primary evidence. Curated legal guidance and regex
indicators are supporting signals only.
"""

from __future__ import annotations

import json
import re
from typing import Callable

from ..legal_knowledge.retriever import map_clause_category, retrieve_legal_guidance
from ..rag.generator import call_ollama
from .knowledge_base import match_risk_domains, risk_guidance_for_prompt

EMPTY_SOURCE = {"name": None, "url": None, "title": None}
ProgressCallback = Callable[[dict], None]
VALID_RISK_STATUSES = {
    "POTENTIAL_RISK",
    "NO_RISK",
    "INSUFFICIENT_EVIDENCE",
    "ERROR",
}
VALID_RISK_LEVELS = {"HIGH", "MEDIUM", "LOW", "NONE"}
VALID_CLASSIFICATION_STATUS = "VALID_CANDIDATE"

RISK_INDICATOR_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "Limitation of Liability": [
        ("uncapped or unlimited liability wording", r"\b(?:uncapped|unlimited|without limitation)\b"),
        ("broad damages exclusion", r"\b(?:indirect|consequential|incidental|special|punitive)\s+damages\b"),
        ("carve-out language", r"\b(?:except|excluding|carve[- ]?out|not apply|shall not apply)\b"),
        ("indemnity coordination reference", r"\b(?:indemnif(?:y|ication)|defend|hold harmless)\b"),
    ],
    "Indemnification": [
        ("defend, indemnify, or hold harmless obligation", r"\b(?:defend|indemnif(?:y|ies|ication)|hold harmless)\b"),
        ("third-party claim scope", r"\bthird[- ]party\s+claims?\b"),
        ("settlement control or approval", r"\b(?:settle|settlement|consent|approval)\b"),
        ("notice procedure", r"\bnotice\b"),
    ],
    "Termination": [
        ("immediate termination", r"\bterminat(?:e|ion)\b.{0,80}\b(?:immediately|without notice)\b"),
        ("termination without cause or stated process", r"\bterminat(?:e|ion)\b.{0,120}\b(?:without cause|at any time)\b"),
        ("cure period", r"\b(?:cure period|opportunity to cure|\d+\s+days?\s+(?:to\s+)?cure)\b"),
        ("notice period", r"\b\d+\s+days?\s+(?:prior\s+)?(?:written\s+)?notice\b"),
        ("renewal window", r"\b(?:renewal|auto[- ]?renew|non[- ]?renewal)\b"),
    ],
    "Intellectual Property": [
        ("ownership allocation wording", r"\b(?:own|owns|owned|ownership|belong|belongs|vest|vests)\b.{0,160}\b(?:intellectual property|ip|rights?|technology|inventions?|work product)\b"),
        ("assignment of IP rights", r"\bassign(?:s|ed|ment)?\b.{0,160}\b(?:intellectual property|ip|patents?|copyrights?|trademarks?|technology)\b"),
        ("broad license scope", r"\blicen[cs](?:e|es|ed|ing)?\b.{0,260}\b(?:worldwide|perpetual|irrevocable|exclusive|sublicen[cs]e|transferable|any purpose)\b"),
        ("unclear license rights", r"\blicen[cs](?:e|es|ed|ing)?\b"),
    ],
    "Confidentiality": [
        ("unclear confidential information definition", r"\bconfidential(?: information)?\b.{0,180}\b(?:all information|anything|any information)\b"),
        ("unclear access restrictions", r"\bconfidential\b.{0,220}\b(?:disclose|access|use|third part(?:y|ies))\b"),
        ("unclear confidentiality duration", r"\bconfidential\b.{0,260}\b(?:forever|perpetual|indefinite|years?|months?)\b"),
    ],
    "Payment": [
        ("unclear payment terms", r"\b(?:pay(?:ment)?|invoice|fees?|charges?)\b.{0,180}\b(?:promptly|reasonable time|as agreed|upon receipt)\b"),
        ("unclear late payment consequences", r"\b(?:late|overdue|delinquent)\b.{0,120}\b(?:interest|suspend|terminate|fee|charge|remedy)\b"),
    ],
    "Force Majeure": [
        ("broad force majeure definition", r"\bforce majeure\b.{0,220}\b(?:any event|all events|anything|without limitation)\b"),
        ("unclear force majeure notice requirement", r"\bforce majeure\b.{0,220}\b(?:notice|notify|inform)\b"),
        ("unclear mitigation obligation", r"\bforce majeure\b.{0,260}\b(?:mitigat|overcome|reasonable efforts|alternative)\w*\b"),
    ],
    "Dispute Resolution": [
        ("unclear arbitration or ADR mechanics", r"\b(?:arbitrat(?:e|ion)|mediat(?:e|ion)|adr)\b.{0,260}\b(?:place|seat|rules?|number|appoint|notice|costs?)\b"),
    ],
    "Insurance": [
        ("unclear insurance coverage", r"\binsurance\b.{0,240}\b(?:coverage|limit|policy|certificate|additional insured|maintain)\b"),
    ],
    "Warranties": [
        ("unclear warranty scope or disclaimer", r"\bwarrant(?:y|ies)\b.{0,220}\b(?:as is|disclaim|excluded|limited|remedy|duration)\b"),
    ],
    "Assignment": [
        ("unclear assignment or change-of-control scope", r"\bassign(?:ment|ed|s)?\b.{0,220}\b(?:affiliate|control|consent|without consent|all rights)\b"),
    ],
}

GENERIC_RISK_INDICATOR_PATTERNS: list[tuple[str, str]] = [
    ("liquidated damages or penalty exposure", r"\b(?:liquidated damages?|penalt(?:y|ies)|fine)\b"),
    ("uncapped monetary exposure", r"\b(?:uncapped|unlimited|without limitation)\b"),
    ("broad damages language", r"\b(?:indirect|consequential|incidental|special|punitive)\s+damages\b"),
    ("indemnification language", r"\b(?:indemnif(?:y|ies|ication)|hold harmless|defend)\b"),
    ("termination language", r"\bterminat(?:e|ed|ing|ion)\b"),
    ("insurance requirement", r"\binsurance\b"),
    ("assignment or control language", r"\b(?:assign(?:ment|ed|s)?|transfer|change of control)\b"),
]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")


def _rule_id(category: str, indicator: str) -> str:
    return f"risk:{_slug(category)}:{_slug(indicator)}"


def _risk_result(
    *,
    risk: bool,
    status: str,
    reason: str,
    source: dict | None = None,
    legal_knowledge: list[dict] | None = None,
    risk_type: str | None = None,
    evidence: str = "",
    rule_id: str | None = None,
    rule: str | None = None,
    matched_indicators: list[str] | None = None,
    risk_rules: list[dict] | None = None,
    risk_level: str | None = None,
    related_contract_context: list[dict] | None = None,
    risk_domains: list[str] | None = None,
) -> dict:
    safe_positive = bool(risk and status == "POTENTIAL_RISK" and evidence)
    return {
        "risk": safe_positive,
        "risk_status": status,
        "risk_level": risk_level if safe_positive else None,
        "risk_type": risk_type if safe_positive else None,
        "rule_id": rule_id if safe_positive else None,
        "rule": rule if safe_positive else None,
        "matched_indicators": matched_indicators or [],
        "risk_rules": risk_rules or [],
        "reason": reason,
        "evidence": evidence if safe_positive else "",
        "source": source or EMPTY_SOURCE.copy(),
        "legal_knowledge": legal_knowledge or [],
        "related_contract_context": related_contract_context or [],
        "risk_domains": risk_domains or [],
    }


def _source_from_guidance(guidance: list[dict]) -> dict:
    if not guidance:
        return EMPTY_SOURCE.copy()
    first = guidance[0]
    return {
        "name": first.get("source_name"),
        "url": first.get("source_url"),
        "title": first.get("title"),
    }


def _legal_knowledge_from_guidance(guidance: list[dict]) -> list[dict]:
    return [
        {
            "source_name": item.get("source_name"),
            "source_url": item.get("source_url"),
            "title": item.get("title"),
            "clause_category": item.get("clause_category"),
            "relevance_score": item.get("relevance_score"),
            "retrieved_text": str(item.get("retrieved_text") or "")[:700],
        }
        for item in guidance
    ]


def _build_risk_rules(category: str, indicators: dict, guidance: list[dict]) -> list[dict]:
    rules = []
    for item in guidance:
        source_key = ":".join(
            str(item.get(key) or "")
            for key in ("source_name", "title", "clause_category")
        )
        rules.append(
            {
                "rule_id": item.get("rule_id") or f"guidance:{_slug(source_key)}",
                "category": item.get("clause_category") or category,
                "rule": item.get("title") or category,
                "source_name": item.get("source_name"),
                "source_url": item.get("source_url"),
            }
        )
    for indicator in indicators.get("matched_indicators", []):
        rules.append(
            {
                "rule_id": _rule_id(category, indicator),
                "category": category,
                "rule": indicator,
                "indicator": indicator,
                "source_name": "Documented deterministic indicator",
                "source_url": None,
            }
        )
    return rules


def detect_legal_indicators(clause_text: str, clause_type: str) -> dict[str, list[str]]:
    category = map_clause_category(clause_type)
    patterns = list(RISK_INDICATOR_PATTERNS.get(category or "", []))
    if not category:
        patterns.extend(GENERIC_RISK_INDICATOR_PATTERNS)
    matches = [
        label
        for label, pattern in patterns
        if re.search(pattern, str(clause_text or ""), re.IGNORECASE | re.DOTALL)
    ]
    return {
        "clause_category": [category] if category else [],
        "matched_indicators": matches,
        "source_documentation": ["backend/data/legal_knowledge/risk_indicators.md"],
    }


def _format_guidance(guidance: list[dict]) -> str:
    if not guidance:
        return "None"
    return "\n\n".join(
        f"{index}. Source: {item.get('source_name')}\n"
        f"   Title: {item.get('title')}\n"
        f"   Category: {item.get('clause_category')}\n"
        f"   Guidance: {item.get('retrieved_text')}"
        for index, item in enumerate(guidance, start=1)
    )


def _format_contract_context(context: list[dict]) -> str:
    if not context:
        return "None"
    return "\n\n".join(
        f"{index}. Chunk ID: {item.get('chunk_id')} | score: {item.get('similarity_score')}\n"
        f"   Exact contract text: {item.get('clause_text')}"
        for index, item in enumerate(context, start=1)
    )


def _format_cuad_evidence(evidence: list[dict]) -> str:
    if not evidence:
        return "None"
    return "\n\n".join(
        f"{index}. Label: {item.get('clause_type')} | score: {item.get('score')}\n"
        f"   Example: {item.get('clause_text')}"
        for index, item in enumerate(evidence, start=1)
    )


def build_risk_prompt(
    clause_text: str,
    clause_type: str,
    legal_indicators: dict[str, list[str]],
    guidance: list[dict],
    contract_context: list[dict] | None = None,
    cuad_evidence: list[dict] | None = None,
    candidate_labels: list[str] | None = None,
    risk_taxonomy: list[dict] | None = None,
) -> str:
    return f"""You are an evidence-grounded contract risk reviewer. This is not legal advice.

Analyze the actual current contract clause first. Related contract chunks are additional contract evidence. CUAD retrieval and legal guidance provide context only; neither is evidence that a risk exists.

Rules:
- Return JSON only.
- Do not infer a risk solely from a CUAD label, legal guidance, or indicator name.
- Regex indicators are supporting signals, not a final decision gate.
- A positive risk finding requires an exact contiguous evidence string copied from the current clause or a related contract chunk.
- If evidence is missing or insufficient, return INSUFFICIENT_EVIDENCE with risk_level null.
- Use HIGH, MEDIUM, or LOW only for a validated POTENTIAL_RISK finding; otherwise risk_level must be null.
- Never include hidden reasoning or reasoning_details in the response.

Current contract clause:
{clause_text}

Final CUAD classification: {clause_type}
Candidate CUAD labels: {json.dumps(candidate_labels or [], ensure_ascii=False)}

CUAD retrieval evidence:
{_format_cuad_evidence(cuad_evidence or [])}

Related contract context:
{_format_contract_context(contract_context or [])}

Supporting Risk Knowledge Base guidance (not contract evidence):
{json.dumps(risk_taxonomy or [], indent=2, ensure_ascii=False)}

Supporting Legal Knowledge Base guidance (not contract evidence):
{_format_guidance(guidance)}

Deterministic supporting indicators:
{json.dumps(legal_indicators, indent=2, ensure_ascii=False)}

Return exactly this shape:
{{
  "risk_status": "POTENTIAL_RISK | NO_RISK | INSUFFICIENT_EVIDENCE",
  "risk_type": "specific risk type or null",
  "risk_level": "HIGH | MEDIUM | LOW | null",
  "reason": "concise explanation grounded in contract evidence",
  "evidence": "exact contiguous contract text or empty string",
  "source": {{"name": null, "url": null, "title": null}}
}}
"""


def _parse_json_object(raw_response: str) -> dict | None:
    try:
        parsed = json.loads(str(raw_response or "").strip())
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, TypeError):
        match = re.search(r"\{.*\}", str(raw_response or ""), re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None


def parse_risk_response(raw_response: str, fallback_source: dict) -> dict:
    parsed = _parse_json_object(raw_response)
    if parsed is None:
        return _risk_result(
            risk=False,
            status="ERROR",
            reason="Risk detector returned malformed JSON; no risk conclusion was accepted.",
            source=fallback_source,
        )

    raw_status = str(parsed.get("risk_status") or "").strip().upper()
    risk_value = parsed.get("risk")
    if risk_value is not None and not isinstance(risk_value, bool):
        return _risk_result(
            risk=False,
            status="ERROR",
            reason="Risk detector returned a malformed response: risk must be a JSON boolean.",
            source=fallback_source,
        )
    if raw_status not in VALID_RISK_STATUSES:
        raw_status = "POTENTIAL_RISK" if risk_value is True else "NO_RISK"
    risk = raw_status == "POTENTIAL_RISK" or risk_value is True
    if risk and raw_status != "POTENTIAL_RISK":
        raw_status = "POTENTIAL_RISK"

    raw_level = parsed.get("risk_level")
    risk_level = str(raw_level).strip().upper() if raw_level else None
    if risk_level not in VALID_RISK_LEVELS:
        risk_level = None
    source = parsed.get("source") if isinstance(parsed.get("source"), dict) else {}
    return {
        "risk": risk,
        "risk_status": raw_status,
        "risk_level": risk_level if risk else None,
        "risk_type": (
            str(parsed.get("risk_type") or "").strip() or None
            if risk
            else None
        ),
        "reason": str(parsed.get("reason") or "").strip(),
        "evidence": str(parsed.get("evidence") or "").strip(),
        "source": {
            "name": source.get("name") or fallback_source.get("name"),
            "url": source.get("url") or fallback_source.get("url"),
            "title": source.get("title") or fallback_source.get("title"),
        },
    }


def no_risk_result(
    reason: str,
    source: dict | None = None,
    legal_knowledge: list[dict] | None = None,
    *,
    status: str = "NO_RISK",
    risk_rules: list[dict] | None = None,
    matched_indicators: list[str] | None = None,
    related_contract_context: list[dict] | None = None,
    risk_domains: list[str] | None = None,
) -> dict:
    return _risk_result(
        risk=False,
        status=status,
        reason=reason,
        source=source,
        legal_knowledge=legal_knowledge,
        risk_rules=risk_rules,
        matched_indicators=matched_indicators,
        related_contract_context=related_contract_context,
        risk_domains=risk_domains,
    )


def _is_clear_limited_ip_license_without_indicator(clause_text: str, clause_type: str) -> bool:
    if map_clause_category(clause_type) != "Intellectual Property":
        return False
    text = str(clause_text or "")
    return bool(
        re.search(r"\blicen[cs](?:e|es|ed|ing)?\b", text, re.IGNORECASE)
        and re.search(r"\bnon[- ]?exclusive\b", text, re.IGNORECASE)
        and re.search(r"\b(?:limited to|solely for|only for|internal use|territory)\b", text, re.IGNORECASE)
        and re.search(r"\b(?:\d+\s+years?|for\s+three\s+years?|valid for)\b", text, re.IGNORECASE)
        and not re.search(r"\b(?:irrevocable|worldwide|perpetual|(?<!non-)exclusive|sublicen[cs]e|any purpose|transferable)\b", text, re.IGNORECASE)
    )


def _is_clear_ip_assignment_without_indicator(clause_text: str, clause_type: str) -> bool:
    if map_clause_category(clause_type) != "Intellectual Property":
        return False
    return bool(
        re.search(r"\bassign(?:s|ed|ment)?\b", clause_text, re.IGNORECASE)
        and re.search(r"\b(?:described in|set forth in|listed in|identified in|schedule|exhibit|patent|copyright|trademark|technology|source code|software)\b", clause_text, re.IGNORECASE)
    )


def _strong_ip_indicator_result(
    clause_text: str,
    clause_type: str,
    indicators: dict[str, list[str]],
    source: dict,
    parsed_result: dict,
    legal_knowledge: list[dict] | None = None,
    risk_rules: list[dict] | None = None,
) -> dict | None:
    if map_clause_category(clause_type) != "Intellectual Property" or parsed_result.get("risk"):
        return None
    if "broad license scope" not in indicators.get("matched_indicators", []):
        return None
    return _risk_result(
        risk=True,
        status="POTENTIAL_RISK",
        risk_level=None,
        risk_type="Broad IP License Scope",
        rule_id=_rule_id("Intellectual Property", "broad license scope"),
        rule="broad license scope",
        matched_indicators=indicators.get("matched_indicators", []),
        risk_rules=risk_rules,
        reason="The contract clause contains a broad IP license scope that warrants review.",
        evidence=str(clause_text or "").strip(),
        source=source,
        legal_knowledge=legal_knowledge,
    )


def _normalize_ip_risk_type(result: dict, indicators: dict[str, list[str]], clause_type: str) -> dict:
    if not result.get("risk") or map_clause_category(clause_type) != "Intellectual Property":
        return result
    if str(result.get("risk_type") or "").strip().lower() not in {
        "",
        "potential risk",
        "potential risk indicator",
        "risk indicator",
    }:
        return result
    labels = indicators.get("matched_indicators", [])
    mapping = {
        "broad license scope": "Broad IP License Scope",
        "assignment of IP rights": "Unclear Assignment Scope",
        "ownership allocation wording": "Unclear IP Ownership",
        "unclear license rights": "Unclear License Rights",
    }
    for label, risk_type in mapping.items():
        if label in labels:
            return {**result, "risk_type": risk_type}
    return result


def detect_clause_risk(
    clause_text: str,
    clause_type: str,
    *,
    classification_status: str | None = VALID_CLASSIFICATION_STATUS,
    cuad_evidence: list[dict] | None = None,
    candidate_labels: list[str] | None = None,
    contract_context: list[dict] | None = None,
    cohere_client=None,
    qdrant_client=None,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    context = contract_context or []
    if not str(clause_text or "").strip():
        return _risk_result(
            risk=False,
            status="INSUFFICIENT_EVIDENCE",
            reason="The clause contains no usable contract text for risk analysis.",
            related_contract_context=context,
        )
    category = map_clause_category(clause_type)
    category_label = category or "Unclassified Contract Provision"

    if progress_callback:
        progress_callback({
            "type": "progress",
            "stage": "risk_context",
            "message": "Retrieving related clauses from the uploaded contract",
        })
    try:
        guidance = retrieve_legal_guidance(
            clause_text,
            clause_type,
            cohere_client=cohere_client,
            qdrant_client=qdrant_client,
            progress_callback=progress_callback,
        )
    except Exception as exc:
        # Legal guidance is supporting knowledge. Keep contract-first risk
        # reasoning available when that secondary dependency is unavailable.
        guidance = []
        if progress_callback:
            progress_callback({
                "type": "progress",
                "stage": "risk_context",
                "message": f"Legal guidance unavailable; continuing with contract evidence ({exc})",
            })

    source = _source_from_guidance(guidance)
    legal_knowledge = _legal_knowledge_from_guidance(guidance)
    indicators = detect_legal_indicators(clause_text, clause_type)
    risk_domains = match_risk_domains(
        clause_text,
        clause_type,
        indicators.get("matched_indicators", []),
    )
    risk_domain_names = [item.get("risk_domain") for item in risk_domains if item.get("risk_domain")]
    risk_rules = _build_risk_rules(category_label, indicators, guidance)
    prompt = build_risk_prompt(
        clause_text=clause_text,
        clause_type=clause_type,
        legal_indicators=indicators,
        guidance=guidance,
        contract_context=context,
        cuad_evidence=cuad_evidence,
        candidate_labels=candidate_labels,
        risk_taxonomy=risk_guidance_for_prompt(risk_domains),
    )
    if progress_callback:
        progress_callback({
            "type": "progress",
            "stage": "risk",
            "message": "Running evidence-grounded Ollama risk reasoning",
        })
    try:
        raw_response = call_ollama(prompt)
    except Exception as exc:
        return _risk_result(
            risk=False,
            status="ERROR",
            reason=f"Risk assessment failed: {exc}",
            source=source,
            legal_knowledge=legal_knowledge,
            matched_indicators=indicators.get("matched_indicators", []),
            risk_rules=risk_rules,
            related_contract_context=context,
            risk_domains=risk_domain_names,
        )

    parsed = parse_risk_response(raw_response, source)
    common = {
        "source": source,
        "legal_knowledge": legal_knowledge,
        "matched_indicators": indicators.get("matched_indicators", []),
        "risk_rules": risk_rules,
        "related_contract_context": context,
        "risk_domains": risk_domain_names,
    }
    if parsed.get("risk_status") == "ERROR":
        return _risk_result(risk=False, status="ERROR", reason=parsed["reason"], **common)
    if parsed.get("risk_status") == "INSUFFICIENT_EVIDENCE":
        return _risk_result(
            risk=False,
            status="INSUFFICIENT_EVIDENCE",
            reason=parsed.get("reason") or "Available contract evidence is insufficient to support a risk finding.",
            **common,
        )
    if not parsed.get("risk"):
        return no_risk_result(
            parsed.get("reason") or "No evidence-supported risk was identified.",
            status="NO_RISK",
            **common,
        )

    evidence = str(parsed.get("evidence") or "").strip()
    contract_texts = [str(clause_text or "")] + [
        str(item.get("clause_text") or "") for item in context
    ]
    if (
        not parsed.get("reason")
        or not parsed.get("risk_type")
        or not evidence
        or not any(evidence in text for text in contract_texts)
    ):
        return _risk_result(
            risk=False,
            status="INSUFFICIENT_EVIDENCE",
            reason="The proposed risk did not include valid exact evidence from the uploaded contract.",
            **common,
        )

    result = _risk_result(
        risk=True,
        status="POTENTIAL_RISK",
        risk_level=parsed.get("risk_level"),
        risk_type=parsed.get("risk_type"),
        rule_id=_rule_id(category_label, (indicators.get("matched_indicators") or [parsed["risk_type"]])[0]),
        rule=(indicators.get("matched_indicators") or [parsed["risk_type"]])[0],
        reason=parsed["reason"],
        evidence=evidence,
        **common,
    )
    result = _normalize_ip_risk_type(result, indicators, clause_type)
    if progress_callback:
        progress_callback({
            "type": "progress",
            "stage": "risk",
            "message": "Risk analysis complete",
            "risk": True,
        })
    return result
