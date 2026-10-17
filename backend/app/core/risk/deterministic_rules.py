"""Deterministic, playbook-authored screening rules for contract risk review.

These predicates inspect only clauses from the currently uploaded contract. They
never load CUAD/retrieved training examples and never claim legal correctness:
a match is a review trigger with an exact quote, not a legal conclusion.
"""
from __future__ import annotations

import re
from typing import Any

from .risk_playbook import source_records

RULE_ENGINE_VERSION = "playbook-rules-1.0"


def _compile(pattern: str) -> re.Pattern[str]:
    return re.compile(str(pattern), re.IGNORECASE | re.DOTALL)


def evaluate_playbook_rules(
    *,
    clause_text: str,
    clause_index: int,
    clause_type: str = "",
    playbook: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Evaluate executable predicates declared in the risk playbook.

    Positive findings are emitted only if a predicate matches the uploaded clause
    and the matched text does not satisfy a rule-specific exclusion. No match is
    deliberately *not* converted into NO_RISK: an absent trigger is not proof that
    the rest of a legal risk question was resolved.
    """
    text = str(clause_text or "")
    if not text.strip():
        return []
    rules = (playbook or {}).get("deterministic_rules") or []
    findings: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rule_id = str(rule.get("id") or "").strip()
        pattern = str(rule.get("pattern") or "").strip()
        if not rule_id or rule_id in seen_ids or not pattern:
            continue
        seen_ids.add(rule_id)

        try:
            match = _compile(pattern).search(text)
        except re.error:
            # Invalid rules are caught by the release validator. Runtime remains
            # fail-safe for a malformed optional rule: never fabricate a finding.
            continue
        if match is None:
            continue

        evidence = match.group(0).strip()
        if not evidence or evidence not in text:
            continue

        # Exclusions may describe negation or a carve-out just before/after
        # the matched phrase. Test a bounded context window, not only the quote.
        # This avoids counting "may not terminate immediately" or "no perpetual
        # license" as positive triggers while limiting unrelated distant text.
        context_start = max(0, match.start() - 180)
        context_end = min(len(text), match.end() + 180)
        match_context = text[context_start:context_end]
        excluded = False
        for exclusion in rule.get("exclude_patterns") or []:
            try:
                if _compile(str(exclusion)).search(match_context):
                    excluded = True
                    break
            except re.error:
                # A malformed exclusion must not silently suppress a valid match.
                continue
        if excluded:
            continue

        check_id = rule_id
        domain = str(rule.get("risk_domain") or "Commercial Risk").strip()
        risk_type = str(rule.get("risk_type") or "Contract wording requires review").strip()
        supporting_sources = source_records(playbook or {}, rule.get("sources") or [])
        primary_source = supporting_sources[0] if supporting_sources else {}
        question = str(rule.get("question") or "Does this wording trigger a contract-review rule?").strip()
        explanation = str(
            rule.get("explanation")
            or "The uploaded clause matched an explicit playbook rule and should be reviewed."
        ).strip()
        findings.append(
            {
                "clause_index": int(clause_index),
                "clause_text": text,
                "predicted_label": str(clause_type or "UNCLASSIFIED"),
                "check_id": check_id,
                "risk_domain": domain,
                "risk_subdomain": None,
                "question": question,
                "answer": "YES",
                "risk_status": "POTENTIAL_RISK",
                "risk_type": risk_type,
                "risk": True,
                "risk_level": None,
                "severity": None,
                "confidence": None,
                "confidence_status": "UNCALIBRATED",
                "severity_status": "DEPRECATED_NOT_USED",
                "ground_truth_status": "PLAYBOOK_DERIVED",
                "evidence": evidence,
                "why_flagged": explanation,
                "reason": explanation,
                "raw_support_score": None,
                "severity_score": None,
                "severity_signal": None,
                "score_components": {},
                "base_score": None,
                "score_modifiers": [],
                "final_score": None,
                "score_override_reason": None,
                "human_review_required": True,
                "review_escalation": "LEGAL_REVIEW",
                "supporting_sources": supporting_sources,
                "legal_guidance_sources": [],
                "related_contract_context": [],
                "source_tier": primary_source.get("source_tier", "D"),
                "jurisdiction": primary_source.get("jurisdiction"),
                "effective_date": primary_source.get("effective_date"),
                "contract_type": primary_source.get("contract_type"),
                "source_url": primary_source.get("source_url") or primary_source.get("url"),
                "source_title": primary_source.get("source_title") or primary_source.get("citation"),
                "retrieval_date": primary_source.get("retrieval_date"),
                "supporting_quote_or_paraphrase": primary_source.get("supporting_quote_or_paraphrase") or primary_source.get("citation"),
                "transferability": primary_source.get("transferability"),
                "provenance": {
                    "source": "DETERMINISTIC_PLAYBOOK_RULE",
                    "rule_engine_version": RULE_ENGINE_VERSION,
                    "playbook_hash": (playbook or {}).get("playbook_hash"),
                    "check_id": check_id,
                    "rule_pattern": pattern,
                    "source_ids": [str(x) for x in (rule.get("sources") or [])],
                    "evaluation_claim": "RULE_TRIGGER_CONFORMANCE_ONLY",
                    "rule_registry_metadata": rule.get("rule_registry_metadata", {}),
                },
                "risk_domains": [domain],
                "matched_indicators": [check_id],
            }
        )
    return findings
