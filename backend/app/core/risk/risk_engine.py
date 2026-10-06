"""Evidence-grounded Phase 2 clause risk engine.

The LLM proposes structured review findings; deterministic validators and the
risk policy decide what is accepted. Model self-consistency is a diagnostic,
not a probability. Calibrated probability is fitted only from adjudicated gold.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Callable, Any

from ..config import (
    LEGAL_KNOWLEDGE_TOP_K,
    RISK_CONTEXT_TOP_K,
    RISK_MAX_TOKENS,
    RISK_MODEL,
    RISK_NUM_CTX,
    RISK_SELF_CONSISTENCY_PASSES,
    RISK_TEMPERATURE,
    RISK_USE_CONTEXT,
    RISK_USE_LEGAL_GUIDANCE,
    RISK_USE_PLAYBOOK,
)
from ..rag.generator import call_ollama
from ..legal_knowledge.retriever import retrieve_legal_guidance
from .calibration import calibrate_risk_probability, calibrate_severity, load_calibration
from .contract_context import retrieve_related_contract_context
from .evidence_policy import legal_claim_supported, normalize_source_record, source_is_eligible
from .knowledge_base import match_risk_domains, risk_guidance_for_prompt
from .risk_detector import detect_legal_indicators
from .risk_playbook import applicable_checks, load_playbook, source_records
from .risk_scoring import score_finding

ProgressCallback = Callable[[dict], None]

VALID_STATUS = {"POTENTIAL_RISK", "NO_RISK", "INSUFFICIENT_EVIDENCE", "ERROR"}
VALID_ANSWER = {"YES", "NO", "DON'T KNOW", "UNKNOWN"}
VALID_FINDING_STATUS = {"PRESENT", "NOT_FOUND", "NOT_APPLICABLE", "UNCERTAIN", "CONFLICT"}

RISK_PROMPT_VERSION = "risk-prompt-v3"
REVIEW_STATUSES = {"HIGH_REVIEW", "LEGAL_REVIEW", "PRIVACY_SECURITY_REVIEW", "BUSINESS_OWNER_REVIEW"}


def _emit(callback: ProgressCallback | None, stage: str, message: str, **details) -> None:
    if callback:
        callback({"type": "progress", "stage": stage, "message": message, **details})


def _evidence_valid(evidence: str, clause_text: str, context: list[dict]) -> bool:
    evidence = str(evidence or "").strip()
    if not evidence:
        return False
    if evidence in str(clause_text or ""):
        return True
    return any(evidence in str(item.get("clause_text") or "") for item in context)


def _evidence_valid_in_clause(evidence: str, clause_text: str) -> bool:
    evidence = str(evidence or "").strip()
    return bool(evidence and evidence in str(clause_text or ""))


def _factor(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if 0.0 <= number <= 5.0 else None


def _severity_signal(final_score: float | None) -> float | None:
    if final_score is None:
        return None
    return round(float(final_score) / 20.0, 4)


def _support_score(*, answer: str, evidence_ok: bool, agreement: float, indicator_match: bool) -> float:
    """Diagnostic only. Never use this as a calibrated probability."""
    if answer not in {"YES", "NO", "DON'T KNOW"}:
        return 0.0
    base = 1.0 if answer == "YES" else (0.55 if answer == "DON'T KNOW" else 0.25)
    evidence_component = 0.30 if evidence_ok else 0.0
    indicator_component = 0.10 if indicator_match else 0.0
    return round(min(1.0, 0.60 * base + evidence_component + 0.10 * agreement + indicator_component), 4)


def _normalize_answer(value: object) -> str:
    answer = str(value or "").strip().upper()
    return "DON'T KNOW" if answer == "UNKNOWN" else answer


def _normalize_finding_status(answer: str, raw_status: object) -> str:
    status = str(raw_status or "").strip().upper().replace(" ", "_")
    aliases = {
        "POTENTIAL_RISK": "PRESENT",
        "NO_RISK": "NOT_FOUND",
        "INSUFFICIENT_EVIDENCE": "UNCERTAIN",
        "NOT_APPLICABLE": "NOT_APPLICABLE",
        "PRESENT": "PRESENT",
        "NOT_FOUND": "NOT_FOUND",
        "UNCERTAIN": "UNCERTAIN",
        "CONFLICT": "CONFLICT",
    }
    if status in aliases:
        return aliases[status]
    if answer == "YES":
        return "PRESENT"
    if answer == "NO":
        return "NOT_FOUND"
    return "UNCERTAIN"


def _prompt(
    *,
    clause_text: str,
    clause_type: str,
    checks: list[dict],
    indicators: dict,
    context: list[dict],
    playbook: dict,
    guidance: list[dict] | None = None,
    contract_type: str | None = None,
    jurisdiction: str | None = None,
    clause_structure: dict | None = None,
) -> str:
    checklist = [
        {
            "id": item["id"],
            "risk_domain": item.get("risk_domain"),
            "risk_type": item.get("risk_type"),
            "perspective": item.get("perspective") or playbook.get("perspective"),
            "applies_when": item.get("applies_when", []),
            "question": item["question"],
            "flag_if": item["flag_if"],
            "do_not_flag_if": item.get("do_not_flag_if", []),
            "required_evidence": item.get("required_evidence", []),
            "evidence_location": item.get("evidence_location", "clause"),
            "dependencies": item.get("dependencies", []),
            "jurisdiction_scope": item.get("jurisdiction_scope", ["unspecified"]),
            "sources": item.get("sources", []),
        }
        for item in checks
    ]

    return f"""You are a commercial contract risk reviewer operating inside a reproducible research pipeline.

This is REVIEW PRIORITIZATION, not legal advice and not a definitive legal conclusion.

CONTRACT CONTEXT
contract_type: {contract_type or "unknown"}
jurisdiction: {jurisdiction or "unknown"}

CURRENT CLAUSE
clause_type: {clause_type}
text:
{clause_text}

CLAUSE STRUCTURE METADATA
{json.dumps(clause_structure or {}, indent=2, ensure_ascii=False)}

RELATED SAME-CONTRACT CLAUSES
{json.dumps(context, indent=2, ensure_ascii=False)}

DETERMINISTIC INDICATORS
{json.dumps(indicators, indent=2, ensure_ascii=False)}

PLAYBOOK CHECKS
{json.dumps(checklist, indent=2, ensure_ascii=False)}

LEGAL / PRACTICE GUIDANCE (NOT CONTRACT EVIDENCE)
{json.dumps(guidance or [], indent=2, ensure_ascii=False)}

Rules:
1. Evaluate the actual contract text first.
2. Legal/practice sources explain why a review question matters. They never prove that the contract contains a risk.
3. For a positive finding, every evidence quote must be an exact contiguous substring of the current clause or an explicitly supplied same-contract context clause.
4. Do not invent facts that are not visible.
5. Use NOT_APPLICABLE when the check does not apply; use UNCERTAIN when evidence is insufficient; use CONFLICT when the supplied contract provisions conflict.
6. Do not state that a provision is illegal, unlawful, prohibited, void, invalid, or unenforceable unless the supplied authority actually supports that claim for the stated jurisdiction and contract type. Prefer "jurisdiction-sensitive" or "requires legal review" otherwise.
7. Score each potential risk on the four 0-5 dimensions. These are raw triage components, not probabilities.
8. Return JSON only. Do not include hidden reasoning or reasoning_details.

Return:
{{
  "checks": [
    {{
      "check_id": "one supplied check id",
      "answer": "YES | NO | DON'T KNOW",
      "finding_status": "PRESENT | NOT_FOUND | NOT_APPLICABLE | UNCERTAIN | CONFLICT",
      "risk_type": "specific exposure or null",
      "why_flagged": "concise audit explanation",
      "evidence": "exact contiguous quote or empty string",
      "jurisdiction_sensitive": false,
      "override_flags": {{
        "uncapped_core_exposure": false,
        "core_ip_or_data_loss": false,
        "business_critical_exit_failure": false,
        "credible_prohibited_or_antitrust_concern": false,
        "central_bargain_failure": false,
        "missing_ownership_chain": false,
        "business_critical_no_practical_remedy": false
      }},
      "control_assessments": {{
        "cap": {{"present": false, "evidence": ""}},
        "cure": {{"present": false, "evidence": ""}},
        "approval": {{"present": false, "evidence": ""}},
        "audit": {{"present": false, "evidence": ""}},
        "insurance": {{"present": false, "evidence": ""}},
        "escrow": {{"present": false, "evidence": ""}},
        "objective_measurement": {{"present": false, "evidence": ""}},
        "remedy": {{"present": false, "evidence": ""}}
      }},
      "score_components": {{
        "exposure_magnitude": 0,
        "likelihood_uncertainty": 0,
        "scope_duration": 0,
        "control_weakness": 0
      }},
      "economic_effect": {{
        "price": null,
        "volume": null,
        "minimum_spend": null,
        "revenue_base": null,
        "damages_or_cap": null,
        "open_ended_exposure": false
      }}
    }}
  ]
}}

Score semantics:
0 = none/minor, 1 = low, 2 = bounded, 3 = material, 4 = very material, 5 = extreme/unbounded.
Do not choose the final severity label directly; the deterministic policy computes it outside the model.
"""


def _parse(raw: str, valid_ids: set[str]) -> list[dict]:
    try:
        parsed = json.loads(str(raw or "").strip())
    except (TypeError, json.JSONDecodeError):
        match = re.search(r"\{.*\}", str(raw or ""), re.DOTALL)
        if not match:
            return []
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []

    if not isinstance(parsed, dict) or not isinstance(parsed.get("checks"), list):
        return []

    out: list[dict] = []
    for item in parsed["checks"]:
        if not isinstance(item, dict):
            continue
        check_id = str(item.get("check_id") or "").strip()
        answer = _normalize_answer(item.get("answer"))
        if check_id not in valid_ids or answer not in VALID_ANSWER:
            continue

        controls = item.get("control_assessments") if isinstance(item.get("control_assessments"), dict) else {}
        normalized_controls = {}
        for key in ("cap", "cure", "approval", "audit", "insurance", "escrow", "objective_measurement", "remedy"):
            raw_control = controls.get(key) if isinstance(controls.get(key), dict) else {}
            normalized_controls[key] = {
                "present": bool(raw_control.get("present")),
                "evidence": str(raw_control.get("evidence") or "").strip(),
            }

        override_flags = item.get("override_flags") if isinstance(item.get("override_flags"), dict) else {}
        factors = item.get("score_components") if isinstance(item.get("score_components"), dict) else {}
        economic = item.get("economic_effect") if isinstance(item.get("economic_effect"), dict) else {}

        out.append(
            {
                "check_id": check_id,
                "answer": answer,
                "finding_status": _normalize_finding_status(answer, item.get("finding_status") or item.get("status")),
                "risk_type": str(item.get("risk_type") or "").strip() or None,
                "evidence": str(item.get("evidence") or "").strip(),
                "why_flagged": str(item.get("why_flagged") or "").strip(),
                "jurisdiction_sensitive": bool(item.get("jurisdiction_sensitive")),
                "override_flags": {
                    key: bool(override_flags.get(key))
                    for key in (
                        "uncapped_core_exposure",
                        "core_ip_or_data_loss",
                        "business_critical_exit_failure",
                        "credible_prohibited_or_antitrust_concern",
                        "central_bargain_failure",
                        "missing_ownership_chain",
                        "business_critical_no_practical_remedy",
                    )
                },
                "control_assessments": normalized_controls,
                "score_components": {
                    key: _factor(factors.get(key))
                    for key in (
                        "exposure_magnitude",
                        "likelihood_uncertainty",
                        "scope_duration",
                        "control_weakness",
                    )
                },
                "economic_effect": economic,
            }
        )
    return out


def _majority(records: list[dict]) -> tuple[str, float]:
    if not records:
        return "DON'T KNOW", 0.0
    votes = Counter(record["answer"] for record in records)
    answer, count = votes.most_common(1)[0]
    return answer, round(count / len(records), 4)


def _control_evidence_valid(controls: dict, clause_text: str, context: list[dict]) -> dict:
    checked = {}
    for key, item in (controls or {}).items():
        present = bool(item.get("present")) if isinstance(item, dict) else False
        evidence = str(item.get("evidence") or "").strip() if isinstance(item, dict) else ""
        checked[key] = {
            "present": present and bool(evidence) and _evidence_valid(evidence, clause_text, context),
            "evidence": evidence if _evidence_valid(evidence, clause_text, context) else "",
        }
    return checked


def _pick_sources(playbook: dict, source_ids: list[str], guidance: list[dict], *, contract_type: str | None, jurisdiction: str | None) -> list[dict]:
    records: list[dict] = []

    for source in source_records(playbook, source_ids):
        normalized = normalize_source_record(
            str(source.get("id") or source.get("source_id") or "playbook-source"),
            source,
            default_tier="D",
            retrieval_date=datetime.now(timezone.utc).isoformat(),
        )
        records.append(normalized)

    for source in guidance or []:
        normalized = normalize_source_record(
            str(source.get("rule_id") or source.get("source_name") or "legal-source"),
            source,
            default_tier="B",
            retrieval_date=datetime.now(timezone.utc).isoformat(),
        )
        records.append(normalized)

    eligible = []
    for source in records:
        source["transferability"] = (
            "direct"
            if not contract_type or source.get("contract_type") in {None, "commercial_general", contract_type}
            else "limited_by_analogy"
        )
        if source_is_eligible(
            source,
            claim_kind="review_question",
            jurisdiction=jurisdiction,
            contract_type=contract_type,
        ):
            eligible.append(source)

    # Stable order: primary official first, then professional practice, then policy.
    priority = {"A": 0, "B": 1, "C": 2, "D": 3}
    return sorted(
        eligible,
        key=lambda item: (
            priority.get(str(item.get("source_tier") or "D"), 9),
            str(item.get("source_title") or ""),
        ),
    )


def analyze_clause_risk(
    *,
    clause_index: int,
    clause_text: str,
    clause_type: str,
    query_vector: list[float] | None,
    contract_clauses: list[dict],
    cohere_client=None,
    progress_callback: ProgressCallback | None = None,
    playbook: dict | None = None,
    passes: int | None = None,
    qdrant_client=None,
    contract_type: str | None = None,
    jurisdiction: str | None = None,
    clause_structure: dict | None = None,
) -> list[dict]:
    playbook = playbook or load_playbook()
    calibration = load_calibration()

    checks = applicable_checks(playbook, clause_type) if RISK_USE_PLAYBOOK else []
    if not checks:
        checks = [
            {
                "id": "OPEN-RISK-1",
                "risk_domain": "Commercial Risk",
                "risk_type": None,
                "question": "Does this clause contain a concrete customer/buyer exposure that warrants review?",
                "flag_if": "Yes, with exact evidence",
                "sources": [],
            }
        ]

    context = (
        retrieve_related_contract_context(
            target_clause_index=clause_index,
            target_vector=query_vector or [],
            clauses=contract_clauses,
            top_k=RISK_CONTEXT_TOP_K,
        )
        if RISK_USE_CONTEXT and query_vector and contract_clauses
        else []
    )

    indicators = (
        detect_legal_indicators(clause_text, clause_type)
        if RISK_USE_LEGAL_GUIDANCE
        else {"matched_indicators": []}
    )

    guidance: list[dict] = []
    if RISK_USE_LEGAL_GUIDANCE:
        guidance.extend(
            risk_guidance_for_prompt(
                match_risk_domains(
                    clause_text,
                    clause_type,
                    indicators.get("matched_indicators", []),
                )
            )
        )
        try:
            guidance.extend(
                retrieve_legal_guidance(
                    clause_text,
                    clause_type,
                    cohere_client=cohere_client,
                    qdrant_client=qdrant_client,
                    top_k=LEGAL_KNOWLEDGE_TOP_K,
                    progress_callback=progress_callback,
                    jurisdiction=jurisdiction,
                    contract_type=contract_type,
                )
            )
        except Exception as exc:
            _emit(
                progress_callback,
                "legal_guidance",
                f"Legal knowledge retrieval unavailable: {exc}",
                clause_index=clause_index,
            )

    deduped: list[dict] = []
    seen = set()
    for item in guidance:
        key = (
            item.get("source_name"),
            item.get("title") or item.get("source_title"),
            item.get("retrieved_text") or item.get("supporting_quote_or_paraphrase"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    guidance = deduped[: max(1, LEGAL_KNOWLEDGE_TOP_K * 2)]

    prompt = _prompt(
        clause_text=clause_text,
        clause_type=clause_type,
        checks=checks,
        indicators=indicators,
        context=context,
        playbook=playbook,
        guidance=guidance,
        contract_type=contract_type,
        jurisdiction=jurisdiction,
        clause_structure=clause_structure,
    )

    n_passes = max(
        1,
        int(passes if passes is not None else RISK_SELF_CONSISTENCY_PASSES),
    )
    outputs: list[list[dict]] = []
    valid_ids = {str(item["id"]) for item in checks}

    _emit(
        progress_callback,
        "risk_clause",
        f"Evaluating risk checks for clause {clause_index}",
        clause_index=clause_index,
    )

    for pass_index in range(n_passes):
        try:
            raw = call_ollama(
                prompt,
                model=RISK_MODEL,
                temperature=RISK_TEMPERATURE,
                num_ctx=RISK_NUM_CTX,
                max_tokens=RISK_MAX_TOKENS,
                think=False,
            )
            parsed = _parse(raw, valid_ids)
        except Exception as exc:
            parsed = []
            _emit(
                progress_callback,
                "risk_clause",
                f"Risk pass failed: {exc}",
                clause_index=clause_index,
                current=pass_index + 1,
                total=n_passes,
            )
        outputs.append(parsed)
        _emit(
            progress_callback,
            "risk_clause",
            f"Risk pass {pass_index + 1}/{n_passes} complete",
            clause_index=clause_index,
            current=pass_index + 1,
            total=n_passes,
        )

    by_check: dict[str, list[dict]] = defaultdict(list)
    for parsed in outputs:
        for item in parsed:
            by_check[item["check_id"]].append(item)

    checks_by_id = {str(item["id"]): item for item in checks}
    current_retrieval_timestamp = datetime.now(timezone.utc).isoformat()
    findings: list[dict] = []

    for check_id, records in by_check.items():
        answer, agreement = _majority(records)
        representative = next(
            (item for item in records if item["answer"] == answer),
            records[0],
        )
        raw_finding_status = representative.get("finding_status") or "UNCERTAIN"

        if len(records) >= 2 and agreement < 0.5:
            finding_status = "CONFLICT"
        else:
            finding_status = raw_finding_status

        evidence = representative.get("evidence") or ""
        evidence_ok = _evidence_valid(evidence, clause_text, context)

        if answer == "YES":
            risk_status = "POTENTIAL_RISK" if evidence_ok and finding_status == "PRESENT" else "INSUFFICIENT_EVIDENCE"
        elif answer == "NO":
            risk_status = "NO_RISK" if finding_status in {"NOT_FOUND", "NOT_APPLICABLE"} else "INSUFFICIENT_EVIDENCE"
        else:
            risk_status = "INSUFFICIENT_EVIDENCE"

        checked_controls = _control_evidence_valid(
            representative.get("control_assessments") or {},
            clause_text,
            context,
        )
        clear_bounded_control = bool(
            checked_controls.get("cap", {}).get("present")
            and checked_controls.get("remedy", {}).get("present")
        )

        source_ids = list(checks_by_id[check_id].get("sources") or [])
        supporting_sources = _pick_sources(
            playbook,
            source_ids,
            guidance,
            contract_type=contract_type,
            jurisdiction=jurisdiction,
        )

        legal_source_text = " ".join(
            str(item.get(key) or "")
            for item in records
            for key in ("risk_type", "why_flagged")
        )
        source_claim_ok = legal_claim_supported(
            legal_source_text,
            supporting_sources,
            jurisdiction=jurisdiction,
            contract_type=contract_type,
        )
        unsupported_legal_claim = not source_claim_ok

        score_details = None
        if risk_status == "POTENTIAL_RISK":
            score_details = score_finding(
                {
                    "risk_type": representative.get("risk_type"),
                    "question": checks_by_id[check_id].get("question", ""),
                    "check_id": check_id,
                    "clause_type": clause_type,
                    "evidence": evidence,
                    "why_flagged": representative.get("why_flagged"),
                    "scope": "clause",
                    "score_components": representative.get("score_components") or {},
                    "override_flags": representative.get("override_flags") or {},
                    "jurisdiction_sensitive": representative.get("jurisdiction_sensitive"),
                    "unsupported_legal_claim": unsupported_legal_claim,
                    "risk_domains": [
                        item.get("risk_domain")
                        for item in match_risk_domains(
                            clause_text,
                            clause_type,
                            indicators.get("matched_indicators", []),
                        )
                    ],
                },
                extraction_confidence=(clause_structure or {}).get("extraction_confidence"),
                dependency_missing=bool((clause_structure or {}).get("dependency_missing")),
                clear_bounded_control=clear_bounded_control,
            )

        severity_score = (
            float(score_details["final_score"])
            if score_details and score_details.get("final_score") is not None
            else None
        )
        calibrated_confidence = (
            calibrate_risk_probability(severity_score, calibration)
            if risk_status == "POTENTIAL_RISK" and severity_score is not None
            else None
        )
        calibrated_severity = calibrate_severity(severity_score, calibration) if severity_score is not None else None

        review_escalation = (
            score_details["escalation"]
            if score_details
            else "HIGH_REVIEW"
        )
        if calibrated_confidence is not None and calibrated_confidence < 0.75:
            review_escalation = "HIGH_REVIEW"

        if unsupported_legal_claim:
            finding_status = "CONFLICT" if finding_status == "PRESENT" else finding_status
            risk_status = "INSUFFICIENT_EVIDENCE"
            severity_score = None
            calibrated_confidence = None
            calibrated_severity = None
            review_escalation = "HIGH_REVIEW"

        primary_source = supporting_sources[0] if supporting_sources else {}
        severity_status = (
            "CALIBRATED"
            if calibrated_severity and risk_status == "POTENTIAL_RISK"
            else ("RULE_BASED_TRIAGE" if severity_score is not None else "INCOMPLETE")
        )

        finding: dict[str, Any] = {
            "clause_index": clause_index,
            "clause_text": clause_text,
            "predicted_label": clause_type,
            "check_id": check_id,
            "question": checks_by_id[check_id].get("question", ""),
            "answer": answer,
            "finding_status": finding_status,
            "risk_status": risk_status,
            "risk_type": representative.get("risk_type") if risk_status == "POTENTIAL_RISK" else None,
            "risk": risk_status == "POTENTIAL_RISK",
            "evidence_status": "SUPPORTED" if evidence_ok and risk_status == "POTENTIAL_RISK" else (
                finding_status if finding_status in VALID_FINDING_STATUS else "UNCERTAIN"
            ),
            "evidence_span": evidence if evidence_ok and risk_status == "POTENTIAL_RISK" else "",
            "evidence_source": "current_clause_or_same_contract",
            "risk_level": (
                calibrated_severity["level"]
                if calibrated_severity and risk_status == "POTENTIAL_RISK"
                else (score_details["severity"] if score_details and risk_status == "POTENTIAL_RISK" else None)
            ),
            "raw_support_score": _support_score(
                answer=answer,
                evidence_ok=evidence_ok,
                agreement=agreement,
                indicator_match=bool(indicators.get("matched_indicators")),
            ),
            "evidence_support_diagnostic": _support_score(
                answer=answer,
                evidence_ok=evidence_ok,
                agreement=agreement,
                indicator_match=bool(indicators.get("matched_indicators")),
            ),
            "severity_score": severity_score,
            "severity_signal": _severity_signal(severity_score),
            "score_components": score_details["score_components"] if score_details else {},
            "base_score": score_details["base_score"] if score_details else None,
            "score_modifiers": score_details["modifiers"] if score_details else [],
            "final_score": severity_score,
            "score_override_reason": score_details["override_reason"] if score_details else None,
            "human_review_required": bool(
                score_details["human_review_required"] if score_details else True
            ),
            "review_escalation": review_escalation,
            "confidence": calibrated_confidence,
            "confidence_status": (
                "CALIBRATED" if calibrated_confidence is not None else "UNCALIBRATED"
            ),
            "severity_status": severity_status,
            "severity_probabilities": (
                calibrated_severity["probabilities"] if calibrated_severity else {}
            ),
            "ground_truth_status": "PLAYBOOK_DERIVED",
            "provenance": {
                "playbook_hash": playbook.get("playbook_hash"),
                "check_id": check_id,
                "source_ids": source_ids,
                "model": RISK_MODEL,
                "prompt_version": RISK_PROMPT_VERSION,
                "passes": len(records),
                "agreement": agreement,
                "deterministic_indicators": indicators.get("matched_indicators", []),
                "retrieval_timestamp": current_retrieval_timestamp,
                "legal_guidance_source_ids": [
                    str(item.get("id") or item.get("rule_id"))
                    for item in guidance
                    if item.get("id") or item.get("rule_id")
                ],
                "score_version": score_details["score_version"] if score_details else None,
                "calibration_input": severity_score,
                "calibration_status": "CALIBRATED" if calibrated_confidence is not None else "NOT_CALIBRATED",
            },
            "why_flagged": representative.get("why_flagged") if risk_status == "POTENTIAL_RISK" else (
                representative.get("why_flagged")
                or (
                    "The risk condition was not found."
                    if finding_status == "NOT_FOUND"
                    else "The available evidence is insufficient to resolve this check."
                )
            ),
            "evidence": evidence if evidence_ok and risk_status == "POTENTIAL_RISK" else "",
            "supporting_sources": supporting_sources,
            "legal_guidance_sources": guidance,
            "related_contract_context": context,
            "severity_factors": representative.get("score_components") or {},
            "control_assessments": checked_controls,
            "override_flags": representative.get("override_flags") or {},
            "economic_effect": representative.get("economic_effect") or {},
            "jurisdiction_sensitive": bool(representative.get("jurisdiction_sensitive")),
            "unsupported_legal_claim": unsupported_legal_claim,
            "source_conflict": False,
            "source_tier": primary_source.get("source_tier"),
            "jurisdiction": jurisdiction,
            "contract_type": contract_type,
            "source_jurisdiction": primary_source.get("jurisdiction"),
            "source_effective_date": primary_source.get("effective_date"),
            "source_contract_type": primary_source.get("contract_type"),
            "source_url": primary_source.get("source_url"),
            "source_title": primary_source.get("source_title"),
            "retrieval_date": current_retrieval_timestamp,
            "supporting_quote_or_paraphrase": primary_source.get("supporting_quote_or_paraphrase"),
            "transferability": primary_source.get("transferability"),
        }
        findings.append(finding)

    returned = {item["check_id"] for item in findings}
    for check in checks:
        check_id = str(check["id"])
        if check_id in returned:
            continue
        findings.append(
            {
                "clause_index": clause_index,
                "clause_text": clause_text,
                "predicted_label": clause_type,
                "check_id": check_id,
                "question": check.get("question", ""),
                "answer": "DON'T KNOW",
                "finding_status": "UNCERTAIN",
                "risk_status": "INSUFFICIENT_EVIDENCE",
                "risk_type": None,
                "risk": False,
                "evidence_status": "UNCERTAIN",
                "evidence_span": "",
                "evidence_source": "none",
                "risk_level": None,
                "raw_support_score": 0.0,
                "evidence_support_diagnostic": 0.0,
                "severity_score": None,
                "severity_signal": None,
                "score_components": {},
                "base_score": None,
                "score_modifiers": [],
                "final_score": None,
                "score_override_reason": None,
                "human_review_required": True,
                "review_escalation": "HIGH_REVIEW",
                "confidence": None,
                "confidence_status": "UNCALIBRATED",
                "severity_status": "INCOMPLETE",
                "severity_probabilities": {},
                "ground_truth_status": "PLAYBOOK_DERIVED",
                "provenance": {
                    "playbook_hash": playbook.get("playbook_hash"),
                    "check_id": check_id,
                    "source_ids": check.get("sources", []),
                    "model": RISK_MODEL,
                    "prompt_version": RISK_PROMPT_VERSION,
                    "passes": n_passes,
                    "agreement": 0.0,
                    "deterministic_indicators": indicators.get("matched_indicators", []),
                    "retrieval_timestamp": current_retrieval_timestamp,
                    "calibration_status": "NOT_CALIBRATED",
                },
                "why_flagged": "No usable model answer was returned; review remains unresolved.",
                "evidence": "",
                "supporting_sources": _pick_sources(
                    playbook,
                    check.get("sources", []),
                    guidance,
                    contract_type=contract_type,
                    jurisdiction=jurisdiction,
                ),
                "legal_guidance_sources": guidance,
                "related_contract_context": context,
                "severity_factors": {},
                "control_assessments": {},
                "override_flags": {},
                "economic_effect": {},
                "jurisdiction_sensitive": False,
                "unsupported_legal_claim": False,
                "source_conflict": False,
                "source_tier": None,
                "jurisdiction": jurisdiction,
                "effective_date": None,
                "contract_type": contract_type,
                "source_jurisdiction": None,
                "source_effective_date": None,
                "source_contract_type": None,
                "source_url": None,
                "source_title": None,
                "retrieval_date": current_retrieval_timestamp,
                "supporting_quote_or_paraphrase": None,
                "transferability": None,
            }
        )

    return sorted(findings, key=lambda item: (item["clause_index"], item["check_id"]))


__all__ = [
    "RISK_PROMPT_VERSION",
    "analyze_clause_risk",
    "_evidence_valid",
    "_support_score",
    "_severity_signal",
    "_majority",
]
