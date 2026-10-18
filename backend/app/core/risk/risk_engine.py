"""Phase 2 clause-level risk engine with explicit playbook rules and evidence provenance."""
from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter, defaultdict
from typing import Callable

from ..config import (
    RISK_CONTEXT_TOP_K,
    RISK_MAX_TOKENS,
    RISK_MODEL,
    RISK_NUM_CTX,
    RISK_SELF_CONSISTENCY_PASSES,
    RISK_TEMPERATURE,
    RISK_USE_CONTEXT,
    RISK_USE_LEGAL_GUIDANCE,
    LEGAL_KNOWLEDGE_TOP_K,
)
from ..rag.generator import call_ollama
from .risk_playbook import applicable_checks, load_playbook, source_records
from .contract_context import retrieve_related_contract_context
from .knowledge_base import match_risk_domains, risk_guidance_for_prompt
from ..legal_knowledge.retriever import retrieve_legal_guidance
from .risk_detector import detect_legal_indicators
from .confidence_calibration import confidence_from_support_score, SUPPORT_SCORE_VERSION
from .deterministic_rules import RULE_ENGINE_VERSION, evaluate_playbook_rules

ProgressCallback = Callable[[dict], None]

VALID_STATUS = {"POTENTIAL_RISK", "NO_RISK", "INSUFFICIENT_EVIDENCE", "ERROR"}
VALID_ANSWER = {"YES", "NO", "DON'T KNOW", "UNKNOWN"}


def _emit(callback: ProgressCallback | None, stage: str, message: str, **details) -> None:
    if callback:
        callback({"type": "progress", "stage": stage, "message": message, **details})


def _evidence_valid(evidence: str, clause_text: str, context: list[dict]) -> bool:
    evidence = str(evidence or "").strip()
    # One-word or token-sized snippets are too weak to support a legal-risk finding,
    # even if the characters happen to occur in the contract.
    if len(evidence) < 8 or len(re.findall(r"\b[\w]{2,}\b", evidence)) < 2:
        return False
    if evidence in str(clause_text or ""):
        return True
    return any(
        evidence in str(item.get("clause_text") or "")
        for item in context
    )


def _evidence_source(evidence: str, clause_text: str, clause_index: int, context: list[dict]) -> dict:
    """Resolve an exact quote to one source clause, or mark its provenance ambiguous."""
    quote = str(evidence or "").strip()
    if quote and quote in str(clause_text or ""):
        return {
            "evidence_clause_index": clause_index,
            "evidence_scope": "target_clause",
            "evidence_source_status": "VERIFIED",
            "evidence_clause_candidates": [clause_index],
        }

    matches: list[int] = []
    unindexed_match = False
    for item in context or []:
        text = str(item.get("clause_text") or "")
        if not quote or quote not in text:
            continue
        try:
            source_index = int(item.get("clause_index"))
        except (TypeError, ValueError):
            unindexed_match = True
            continue
        matches.append(source_index)

    candidates = sorted(set(matches))
    if unindexed_match:
        return {
            "evidence_clause_index": None,
            "evidence_scope": "ambiguous_related_contract_clause" if candidates else "related_contract_clause",
            "evidence_source_status": "AMBIGUOUS" if candidates else "UNVERIFIABLE",
            "evidence_clause_candidates": candidates,
        }
    if len(candidates) == 1:
        return {
            "evidence_clause_index": candidates[0],
            "evidence_scope": "related_contract_clause",
            "evidence_source_status": "VERIFIED",
            "evidence_clause_candidates": candidates,
        }
    if len(candidates) > 1:
        return {
            "evidence_clause_index": None,
            "evidence_scope": "ambiguous_related_contract_clause",
            "evidence_source_status": "AMBIGUOUS",
            "evidence_clause_candidates": candidates,
        }
    return {
        "evidence_clause_index": None,
        "evidence_scope": None,
        "evidence_source_status": "NOT_FOUND",
        "evidence_clause_candidates": [],
    }


def _factor(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if 0.0 <= number <= 5.0 else None


def _severity_signal(factors: dict) -> float | None:
    """Deprecated compatibility shim. Severity signals are no longer emitted."""
    del factors
    return None


def _support_score(*, answer: str, evidence_ok: bool, agreement: float, indicator_match: bool) -> float:
    """Uncalibrated evidence-support feature; deliberately independent of YES/NO direction."""
    if answer not in {"YES", "NO"}:
        return 0.0
    try:
        agreement_value = float(agreement)
    except (TypeError, ValueError):
        agreement_value = 0.0
    if not math.isfinite(agreement_value):
        agreement_value = 0.0
    agreement_value = max(0.0, min(1.0, agreement_value))
    evidence_component = 0.50 if evidence_ok else 0.0
    agreement_component = 0.30 * agreement_value
    indicator_component = 0.20 if indicator_match else 0.0
    return round(min(1.0, evidence_component + agreement_component + indicator_component), 4)


_NEGATIVE_FLAG_PREFIXES = (
    "no", "none", "missing", "absent", "absence", "lack", "lacks", "lacking",
    "without", "silent", "unclear", "not", "future-tense only", "future tense only",
    "looks punitive", "over-broad", "overbroad", "very long", "limits far below",
    "one-sided protecting only the counterparty",
)
_NEGATIVE_TRIGGER_OVERRIDES = {("Cap On Liability", "LOL-2")}
_BINARY_QUESTION_OVERRIDES = {
    ("Anti-Assignment", "AA-2"): (
        "Does the consent standard impose an absolute assignment ban or require consent "
        "without a reasonableness standard?"
    ),
    ("Change Of Control", "COC-1"): (
        "Does a change of control trigger automatic termination or another materially adverse effect?"
    ),
    ("Ip Ownership Assignment", "IP-1"): (
        "Does the vendor retain ownership of newly created or deliverable IP paid for by the customer "
        "without a clear license-back?"
    ),
}
TRIGGER_POLARITY_POLICY_VERSION = "flag-if-answer-polarity-v1"


def _check_key(check: dict) -> tuple[str, str]:
    category = str(check.get("_playbook_category") or check.get("clause_type") or "").strip()
    base_id = str(check.get("_base_check_id") or check.get("id") or "").strip()
    if "@" in base_id:
        base_id = base_id.split("@", 1)[0]
    return category, base_id


def _expected_trigger_answer(check: dict) -> str:
    """Infer the YES/NO answer polarity implied by legacy flag_if wording."""
    explicit = str(check.get("risk_trigger_answer") or "").strip().upper()
    if explicit in {"YES", "NO"}:
        return explicit
    key = _check_key(check)
    if key in _NEGATIVE_TRIGGER_OVERRIDES:
        return "NO"
    flag_if = str(check.get("flag_if") or "").strip().lower()
    negative_prefix = any(
        flag_if == prefix
        or flag_if.startswith(prefix + " ")
        or flag_if.startswith(prefix + "/")
        or flag_if.startswith(prefix + ",")
        or flag_if.startswith(prefix + "—")
        or flag_if.startswith(prefix + "-")
        for prefix in _NEGATIVE_FLAG_PREFIXES
    )
    return "NO" if negative_prefix else "YES"


def _question_for_check(check: dict) -> str:
    """Normalize legacy open-ended items to answerable binary predicates."""
    key = _check_key(check)
    return _BINARY_QUESTION_OVERRIDES.get(key, str(check.get("question") or "").strip())


def _prompt(
    *,
    clause_text: str,
    clause_type: str,
    checks: list[dict],
    indicators: dict,
    context: list[dict],
    playbook: dict,
    guidance: list[dict] | None = None,
    deterministic_rule_hits: list[dict] | None = None,
) -> str:
    checklist = [
        {
            "id": item["id"],
            "risk_domain": item.get("risk_domain"),
            "risk_subdomain": item.get("risk_subdomain"),
            "risk_type": item.get("risk_type"),
            "perspective": item.get("perspective"),
            "applies_when": item.get("applies_when", []),
            "question": _question_for_check(item),
            "source_question": item.get("question") if _question_for_check(item) != item.get("question") else None,
            "risk_trigger_answer": _expected_trigger_answer(item),
            "flag_if": item["flag_if"],
            "do_not_flag_if": item.get("do_not_flag_if", []),
            "required_evidence": item.get("required_evidence", []),
            "evidence_location": item.get("evidence_location", "clause"),
            "dependencies": item.get("dependencies", []),
            "jurisdiction_scope": item.get("jurisdiction_scope", ["UNSPECIFIED"]),
            "rule_registry_metadata": item.get("rule_registry_metadata", {}),
            "sources": item.get("sources", []),
        }
        for item in checks
    ]
    return f"""You are a commercial contract risk reviewer operating inside a reproducible analysis pipeline.

This is a REVIEW-PRIORITIZATION task, not a legal conclusion. The playbook is policy/guidance, not ground truth.

Rules:
1. Evaluate only the supplied current clause and same-contract context.
2. A playbook source, legal guidance, CUAD label, keyword, or retrieved example can suggest a question but cannot be used as contract evidence.
3. For YES, quote an exact contiguous substring from the current clause or related contract context.
4. For NO, do not invent a protective fact not visible in the evidence.
5. For DON'T KNOW, explain what evidence is missing.
6. Risk type must identify the concrete exposure, not just "risk".
7. Keep reasons concise and audit-friendly.
8. No clause-category training examples or retrieved risk text spans are provided to this risk stage; do not invent examples.
9. Return JSON only. No hidden reasoning, no markdown, no extra text.
10. Each checklist item is a RISK PREDICATE: answer the supplied question as written.
11. Apply the supplied flag_if and do_not_flag_if rules when setting status. Do not treat every YES as a risk.
12. Each check includes risk_trigger_answer, the answer polarity implied by flag_if. A supported risk trigger may be YES or NO; do not force all positive findings to answer YES.
13. Emit POTENTIAL_RISK only when the answer matches risk_trigger_answer, the trigger condition is satisfied, and exact evidence supports it. If the answer contradicts trigger polarity, use INSUFFICIENT_EVIDENCE.
14. A mutual/reciprocal clause must not be labeled one-sided when the contract text itself applies the protection to both parties.
15. Treat the registry status as binding pipeline governance: unapproved rules are review triggers only, not approved legal policy.
16. If jurisdiction scope is unresolved or the source citation is incomplete, describe a commercial review concern; do not assert enforceability, illegality, or governing-law doctrine.
17. Never emit ordinal severity, numerical severity scores, or self-reported confidence. Confidence is computed separately only after adjudicated calibration.

CURRENT CLAUSE
ID: {clause_type}
TEXT:
{clause_text}

DETERMINISTIC INDICATORS
{json.dumps(indicators, indent=2, ensure_ascii=False)}

RELATED SAME-CONTRACT CLAUSES
{json.dumps(context, indent=2, ensure_ascii=False)}

PLAYBOOK GOVERNANCE
{json.dumps(playbook.get("rule_registry", {"status": "UNAPPROVED"}), indent=2, ensure_ascii=False)}

PLAYBOOK CHECKS
{json.dumps(checklist, indent=2, ensure_ascii=False)}

LEGAL GUIDANCE (not contract evidence)
{json.dumps(guidance or [], indent=2, ensure_ascii=False)}

DETERMINISTIC PLAYBOOK RULE MATCHES FOR THIS UPLOADED CLAUSE
{json.dumps(deterministic_rule_hits or [], indent=2, ensure_ascii=False)}

These direct pattern matches are review triggers generated from the playbook and exact uploaded clause text. They do not establish enforceability. Do not erase a matching trigger by asserting a legal conclusion; the deterministic rule finding is preserved independently of your answer to the checklist questions.

Return:
{{
  "checks": [
    {{
      "check_id": "one of the supplied ids",
      "answer": "YES | NO | DON'T KNOW",
      "status": "POTENTIAL_RISK | NO_RISK | INSUFFICIENT_EVIDENCE",
      "risk_type": "specific risk type or null",
      "evidence": "exact contiguous quote or empty string",
      "why_flagged": "concise explanation or empty string"
    }}
  ]
}}

Do not emit a severity scale or probability. If the policy scope or evidence is unresolved, return INSUFFICIENT_EVIDENCE and identify the missing dependency.
"""
    

def _parse(raw: str, valid_ids: set[str]) -> list[dict]:
    try:
        parsed = json.loads(str(raw or "").strip())
    except (TypeError, json.JSONDecodeError):
        match = re.search(r"{.*}", str(raw or ""), re.DOTALL)
        if not match:
            return []
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
    if not isinstance(parsed, dict) or not isinstance(parsed.get("checks"), list):
        return []
    raw_id_counts = Counter(
        str(item.get("check_id") or "").strip()
        for item in parsed["checks"]
        if isinstance(item, dict)
        and str(item.get("check_id") or "").strip() in valid_ids
    )
    out = []
    for item in parsed["checks"]:
        if not isinstance(item, dict):
            continue
        check_id = str(item.get("check_id") or "").strip()
        answer = str(item.get("answer") or "").strip().upper()
        status = str(item.get("status") or "").strip().upper()
        # A duplicated checklist ID in one response is ambiguous, not multiple votes.
        if check_id not in valid_ids or answer not in VALID_ANSWER or raw_id_counts[check_id] != 1:
            continue
        if answer == "UNKNOWN":
            answer = "DON'T KNOW"
        if status not in VALID_STATUS:
            status = "POTENTIAL_RISK" if answer == "YES" else ("NO_RISK" if answer == "NO" else "INSUFFICIENT_EVIDENCE")
        out.append(
            {
                "check_id": check_id,
                "answer": answer,
                "status": status,
                "risk_type": str(item.get("risk_type") or "").strip() or None,
                "evidence": str(item.get("evidence") or "").strip(),
                "why_flagged": str(item.get("why_flagged") or "").strip(),
            }
        )
    return out


def _majority(records: list[dict], expected_passes: int | None = None) -> tuple[str, float]:
    """Return a conservative decision while counting missing passes as abstentions.

    Agreement uses the configured number of passes, not only successful parses.
    A single configured pass has no measurable inter-pass agreement, so its
    agreement signal is 0. Ties and results without a strict majority abstain.
    """
    if not records:
        return "DON'T KNOW", 0.0
    total_passes = max(
        len(records),
        int(expected_passes) if expected_passes is not None else len(records),
    )
    votes = Counter(record["answer"] for record in records)
    answer, count = votes.most_common(1)[0]
    agreement = round(count / total_passes, 4)
    if total_passes == 1:
        return answer, 0.0
    if count * 2 <= total_passes:
        return "DON'T KNOW", agreement
    return answer, agreement


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
    clause_position: int | None = None,
    total_clauses: int | None = None,
) -> list[dict]:
    playbook = playbook or load_playbook()
    # Direct uploaded-text predicates execute before optional retrieval and model
    # calls. Their findings survive any later context or generation failure.
    rule_findings = evaluate_playbook_rules(
        clause_text=clause_text,
        clause_index=clause_index,
        clause_type=clause_type,
        playbook=playbook,
    )
    rule_hits = [
        {
            "check_id": item.get("check_id"),
            "risk_domain": item.get("risk_domain"),
            "risk_type": item.get("risk_type"),
            "evidence": item.get("evidence"),
            "why_flagged": item.get("why_flagged"),
        }
        for item in rule_findings
    ]
    _emit(
        progress_callback,
        "deterministic_rules",
        f"Applied {len(rule_findings)} direct playbook rule trigger(s)",
        clause_index=clause_index,
        rule_engine_version=RULE_ENGINE_VERSION,
    )
    checks = applicable_checks(playbook, clause_type, clause_text=clause_text)
    if not checks:
        checks = [{
            "id": "OPEN-RISK-1",
            "question": "Does this clause contain a concrete customer/buyer exposure that warrants review?",
            "flag_if": "Yes, with exact evidence",
            "sources": [],
        }]

    context = []
    if RISK_USE_CONTEXT and query_vector and contract_clauses:
        try:
            context = retrieve_related_contract_context(
                target_clause_index=clause_index,
                target_vector=query_vector,
                clauses=contract_clauses,
                top_k=RISK_CONTEXT_TOP_K,
            )
        except Exception as exc:
            # Same-contract retrieval is useful context, but direct playbook
            # rules still need to run when the retrieval index is unavailable.
            _emit(
                progress_callback,
                "contract_context",
                f"Related-clause retrieval unavailable; direct rules remain active: {exc}",
                clause_index=clause_index,
            )

    indicators = (
        detect_legal_indicators(clause_text, clause_type)
        if RISK_USE_LEGAL_GUIDANCE
        else {"matched_indicators": []}
    )
    guidance = (
        risk_guidance_for_prompt(
            match_risk_domains(
                clause_text,
                clause_type,
                indicators.get("matched_indicators", []),
            )
        )
        if RISK_USE_LEGAL_GUIDANCE
        else []
    )
    if RISK_USE_LEGAL_GUIDANCE:
        try:
            guidance.extend(
                retrieve_legal_guidance(
                    clause_text,
                    clause_type,
                    cohere_client=cohere_client,
                    qdrant_client=qdrant_client,
                    top_k=LEGAL_KNOWLEDGE_TOP_K,
                    progress_callback=progress_callback,
                )
            )
        except Exception as exc:
            _emit(
                progress_callback,
                "legal_guidance",
                f"Legal knowledge retrieval unavailable: {exc}",
                clause_index=clause_index,
            )
    # Deduplicate guidance records before placing them in the prompt.
    deduped = []
    seen = set()
    for item in guidance:
        key = (
            item.get("source_name"),
            item.get("title"),
            item.get("retrieved_text"),
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
        deterministic_rule_hits=rule_hits,
    )

    n_passes = max(1, int(passes if passes is not None else RISK_SELF_CONSISTENCY_PASSES))
    outputs: list[list[dict]] = []
    valid_ids = {str(item["id"]) for item in checks}
    _emit(
        progress_callback,
        "risk_clause",
        f"Evaluating risk checks for clause {clause_position or clause_index} of {total_clauses or '?'}",
        clause_index=clause_index,
        current=clause_position,
        total=total_clauses,
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
        except Exception:
            logging.getLogger(__name__).exception(
                "Clause risk model pass failed (clause_index=%s, pass=%d/%d)",
                clause_index,
                pass_index + 1,
                n_passes,
            )
            parsed = []
        outputs.append(parsed)
        _emit(
            progress_callback,
            "risk_pass",
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
    findings: list[dict] = []
    for check_id, records in by_check.items():
        answer, agreement = _majority(records, expected_passes=n_passes)
        representative = next((x for x in records if x["answer"] == answer), records[0])
        evidence = representative["evidence"]
        evidence_location = _evidence_source(evidence, clause_text, clause_index, context)
        evidence_ok = (
            _evidence_valid(evidence, clause_text, context)
            and evidence_location.get("evidence_source_status") == "VERIFIED"
        )
        indicator_match = bool(indicators.get("matched_indicators"))
        check = checks_by_id[check_id]
        status = "INSUFFICIENT_EVIDENCE" if answer == "DON'T KNOW" else representative["status"]
        # Trigger polarity is rule-specific: missing protections, unclear terms, and
        # one-sided rights may correctly be answered NO. A positive finding must match
        # the rule's expected polarity and retain verified contract evidence.
        expected_trigger_answer = _expected_trigger_answer(check)
        if status == "POTENTIAL_RISK" and (answer != expected_trigger_answer or not evidence_ok):
            status = "INSUFFICIENT_EVIDENCE"
        elif status not in {"POTENTIAL_RISK", "NO_RISK", "INSUFFICIENT_EVIDENCE", "ERROR"}:
            status = "INSUFFICIENT_EVIDENCE"

        raw_support = _support_score(
            answer=answer,
            evidence_ok=evidence_ok,
            agreement=agreement,
            indicator_match=indicator_match,
        )
        confidence_details = (
            confidence_from_support_score(raw_support, playbook_hash=playbook.get("playbook_hash"))
            if status in {"POTENTIAL_RISK", "NO_RISK"}
            else {"confidence": None, "confidence_status": "NOT_ESTIMATED", "confidence_target": "PREDICTION_CORRECTNESS", "confidence_calibration_version": None}
        )
        source_ids = checks_by_id[check_id].get("sources", [])
        supporting_sources = source_records(playbook, source_ids)
        primary_source = supporting_sources[0] if supporting_sources else {}
        findings.append(
            {
                "clause_index": clause_index,
                "clause_text": clause_text,
                "predicted_label": clause_type,
                "check_id": check_id,
                **evidence_location,
                "risk_domain": checks_by_id[check_id].get("risk_domain"),
                "risk_subdomain": checks_by_id[check_id].get("risk_subdomain"),
                "question": _question_for_check(check),
                "source_question": check.get("question") if _question_for_check(check) != check.get("question") else None,
                "answer": answer,
                "risk_status": status,
                "risk_type": representative.get("risk_type") if status == "POTENTIAL_RISK" else None,
                "risk": status == "POTENTIAL_RISK",
                "risk_level": None,
                "severity": None,
                "raw_support_score": raw_support if status in {"POTENTIAL_RISK", "NO_RISK"} else None,
                "severity_score": None,
                "severity_signal": None,
                "score_components": {},
                "base_score": None,
                "score_modifiers": [],
                "final_score": None,
                "score_override_reason": None,
                "human_review_required": status in {"POTENTIAL_RISK", "INSUFFICIENT_EVIDENCE"},
                "review_escalation": "LEGAL_REVIEW" if status in {"POTENTIAL_RISK", "INSUFFICIENT_EVIDENCE"} else "STANDARD_REVIEW",
                "confidence": confidence_details.get("confidence"),
                "confidence_status": confidence_details.get("confidence_status", "UNCALIBRATED"),
                "confidence_target": confidence_details.get("confidence_target", "PREDICTION_CORRECTNESS"),
                "confidence_calibration_version": confidence_details.get("confidence_calibration_version"),
                "severity_status": "DEPRECATED_NOT_USED",
                "severity_probabilities": {},
                "ground_truth_status": "PLAYBOOK_DERIVED",
                "provenance": {
                    "playbook_hash": playbook.get("playbook_hash"),
                    "rule_engine_version": RULE_ENGINE_VERSION,
                    "check_id": check_id,
                    "base_check_id": check.get("_base_check_id") or check.get("id") or check_id,
                    "playbook_category": check.get("_playbook_category"),
                    "risk_trigger_answer": expected_trigger_answer,
                    "trigger_polarity_policy_version": TRIGGER_POLARITY_POLICY_VERSION,
                    "source_ids": source_ids,
                    "model": RISK_MODEL,
                    "passes": len(records),
                    "expected_passes": n_passes,
                    "missing_passes": max(0, n_passes - len(records)),
                    "agreement": agreement,
                    "support_score_version": SUPPORT_SCORE_VERSION,
                    "support_score_interpretation": "Uncalibrated diagnostic only; not a probability.",
                    "confidence_target": confidence_details.get("confidence_target", "PREDICTION_CORRECTNESS"),
                    "confidence_calibration_version": confidence_details.get("confidence_calibration_version"),
                    "rule_registry_metadata": checks_by_id[check_id].get("rule_registry_metadata", {}),
                    "deterministic_indicators": indicators.get("matched_indicators", []),
                },
                "why_flagged": representative.get("why_flagged") if status == "POTENTIAL_RISK" else (
                    representative.get("why_flagged") or "No evidence-supported issue identified by the check."
                ),
                "evidence": evidence if evidence_ok and status == "POTENTIAL_RISK" else "",
                "supporting_sources": supporting_sources,
                "legal_guidance_sources": guidance,
                "related_contract_context": context,
                "severity_factors": {},
                "source_tier": primary_source.get("source_tier"),
                "jurisdiction": primary_source.get("jurisdiction"),
                "effective_date": primary_source.get("effective_date"),
                "contract_type": primary_source.get("contract_type"),
                "source_url": primary_source.get("source_url"),
                "source_title": primary_source.get("source_title"),
                "retrieval_date": primary_source.get("retrieval_date"),
                "supporting_quote_or_paraphrase": primary_source.get("supporting_quote_or_paraphrase"),
                "transferability": primary_source.get("transferability"),
            }
        )

    # Preserve checks that received no usable model answer as explicit uncertainty.
    returned = {item["check_id"] for item in findings}
    for check in checks:
        if check["id"] in returned:
            continue
        findings.append(
            {
                "clause_index": clause_index,
                "clause_text": clause_text,
                "predicted_label": clause_type,
                "check_id": check["id"],
                "risk_domain": check.get("risk_domain"),
                "risk_subdomain": check.get("risk_subdomain"),
                "question": _question_for_check(check),
                "source_question": check.get("question") if _question_for_check(check) != check.get("question") else None,
                "answer": "DON'T KNOW",
                "risk_status": "INSUFFICIENT_EVIDENCE",
                "risk_type": None,
                "risk": False,
                "risk_level": None,
                "severity": None,
                "raw_support_score": None,
                "severity_signal": None,
                "confidence": None,
                "confidence_status": "UNCALIBRATED",
                "severity_status": "DEPRECATED_NOT_USED",
                "severity_probabilities": {},
                "ground_truth_status": "PLAYBOOK_DERIVED",
                "base_score": None,
                "final_score": None,
                "score_components": {},
                "score_modifiers": [],
                "score_override_reason": None,
                "human_review_required": True,
                "review_escalation": "LEGAL_REVIEW",
                "provenance": {
                    "playbook_hash": playbook.get("playbook_hash"),
                    "rule_engine_version": RULE_ENGINE_VERSION,
                    "check_id": check["id"],
                    "base_check_id": check.get("_base_check_id") or check.get("id"),
                    "playbook_category": check.get("_playbook_category"),
                    "risk_trigger_answer": _expected_trigger_answer(check),
                    "trigger_polarity_policy_version": TRIGGER_POLARITY_POLICY_VERSION,
                    "source_ids": check.get("sources", []),
                    "model": RISK_MODEL,
                    "passes": 0,
                    "expected_passes": n_passes,
                    "missing_passes": n_passes,
                    "agreement": 0.0,
                    "score_component_source": "NONE",
                    "score_interpretation": "Triage heuristic only; not calibrated to real-world legal outcomes.",
                    "deterministic_indicators": indicators.get("matched_indicators", []),
                },
                "why_flagged": "The model did not return a usable evidence-grounded answer for this check.",
                "evidence": "",
                "supporting_sources": source_records(playbook, check.get("sources", [])),
                "related_contract_context": context,
                "severity_factors": {},
            }
        )
    # Keep deterministic playbook flags independently of model answers. A direct
    # lexical trigger must not disappear because the question-answering model said NO.
    findings.extend(rule_findings)
    return sorted(findings, key=lambda item: (item["clause_index"], item["check_id"]))
