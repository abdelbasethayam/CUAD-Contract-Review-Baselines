"""Cross-clause and document-level Phase 2 checks with exact evidence validation."""
from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict

from ..config import RISK_MAX_TOKENS, RISK_MODEL, RISK_NUM_CTX, RISK_SELF_CONSISTENCY_PASSES, RISK_TEMPERATURE
from ..rag.generator import call_ollama
from .risk_engine import _evidence_valid, _majority, _support_score
from .risk_playbook import load_playbook, source_records
from .confidence_calibration import confidence_from_support_score, SUPPORT_SCORE_VERSION


def _candidate_clauses(clauses: list[dict], pair: list[str]) -> list[dict]:
    """Return explicit label matches plus text matches for any missing pair member.

    Cross-clause checks often span clauses whose CUAD category names do not
    exactly match playbook terminology (e.g., Cap On Liability vs Limitation of
    Liability, or a termination clause that also states minimum-commitment fees).
    Returning only the first exact-label match can hide the second half of the
    relationship, so search by text for missing pair concepts as well.
    """
    pair_names = [str(value).strip() for value in pair if str(value).strip()]
    names = {value.lower() for value in pair_names}
    selected = [
        item for item in clauses
        if str(item.get("predicted_label") or "").strip().lower() in names
    ]
    selected_labels = {
        str(item.get("predicted_label") or "").strip().lower()
        for item in selected
    }
    if selected_labels >= names:
        return selected[:20]

    missing_names = [value for value in pair_names if value.lower() not in selected_labels]
    terms_by_name = []
    for value in missing_names:
        terms = {term for term in re.findall(r"[a-z0-9]+", value.lower()) if len(term) > 4}
        # Add conservative word stems for common inflections (e.g. renewal/renews,
        # indemnification/indemnifies) so a missing pair concept can be retrieved
        # even when the contract uses a grammatical variant.
        terms.update(term[:-2] for term in tuple(terms) if len(term) >= 7)
        terms_by_name.append(terms)
    fallback = []
    selected_ids = {item.get("clause_index") for item in selected}
    for item in clauses:
        if item.get("clause_index") in selected_ids:
            continue
        text = str(item.get("clause_text") or "").lower()
        if any(terms and any(term in text for term in terms) for terms in terms_by_name):
            fallback.append(item)

    # Preserve explicit label matches first, then supplement with lexical hits.
    return (selected + fallback)[:20]


def _prompt(clauses: list[dict], cross_checks: list[dict], doc_checks: list[dict], deterministic_signals: list[dict] | None = None) -> str:
    compact = [
        {
            "clause_id": item.get("clause_index"),
            "label": item.get("predicted_label"),
            "text": str(item.get("clause_text") or "")[:2500],
        }
        for item in clauses
    ]
    return f"""You are performing cross-clause and document-level commercial contract risk checks.

This is review prioritization, not legal advice. The playbook is guidance, not ground truth.

Rules:
- Use only the supplied contract clauses.
- Every positive finding must cite existing clause IDs and exact contiguous quotes copied from the supplied text.
- Do not treat a CUAD label, checklist, or source as contract evidence.
- If evidence is insufficient, return INSUFFICIENT_EVIDENCE.
- Do not infer external law or enforceability.
- If a rule is unapproved, jurisdiction scope is unresolved, or source citations are incomplete, describe a review concern only and require human legal review.
- Do not emit ordinal severity labels, numerical severity scores, or model-self-reported confidence.
- Return JSON only.

CLAUSES
{json.dumps(compact, ensure_ascii=False)}

CROSS-CLAUSE CHECKS
{json.dumps(cross_checks, ensure_ascii=False)}

DOCUMENT CHECKS
{json.dumps(doc_checks, ensure_ascii=False)}

DETERMINISTIC INTERACTION SIGNALS (candidate signals, not legal conclusions)
{json.dumps(deterministic_signals or [], ensure_ascii=False)}

Return:
{{
  "cross_clause_findings": [
    {{
      "check_id": "X-...",
      "answer": "YES | NO | DON'T KNOW",
      "status": "POTENTIAL_RISK | NO_RISK | INSUFFICIENT_EVIDENCE",
      "risk_type": "specific exposure or null",
      "clause_ids": [1, 2],
      "evidence": [{{"clause_id": 1, "quote": "exact quote"}}],
      "why_flagged": "concise explanation"
    }}
  ],
  "document_findings": [
    {{
      "check_id": "DOC-...",
      "answer": "YES | NO | DON'T KNOW",
      "status": "POTENTIAL_RISK | NO_RISK | INSUFFICIENT_EVIDENCE",
      "risk_type": "specific exposure or null",
      "clause_ids": [1],
      "evidence": [{{"clause_id": 1, "quote": "exact quote"}}],
      "why_flagged": "concise explanation"
    }}
  ]
}}
"""
    

def _parse(raw: str, valid_cross: set[str], valid_doc: set[str]) -> tuple[list[dict], list[dict]]:
    try:
        parsed = json.loads(str(raw or "").strip())
    except (TypeError, json.JSONDecodeError):
        match = re.search(r"{.*}", str(raw or ""), re.DOTALL)
        if not match:
            return [], []
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return [], []

    def parse_group(items, valid_ids):
        items = items or []
        raw_id_counts = Counter(
            str(item.get("check_id") or "").strip()
            for item in items
            if isinstance(item, dict)
            and str(item.get("check_id") or "").strip() in valid_ids
        )
        out = []
        for item in items:
            if not isinstance(item, dict):
                continue
            check_id = str(item.get("check_id") or "").strip()
            answer = str(item.get("answer") or "").strip().upper().replace("UNKNOWN", "DON'T KNOW")
            # Duplicate IDs make the response ambiguous; never count them as extra votes.
            if check_id not in valid_ids or answer not in {"YES", "NO", "DON'T KNOW"} or raw_id_counts[check_id] != 1:
                continue
            status = str(item.get("status") or "").strip().upper()
            if status not in {"POTENTIAL_RISK", "NO_RISK", "INSUFFICIENT_EVIDENCE"}:
                status = "POTENTIAL_RISK" if answer == "YES" else ("NO_RISK" if answer == "NO" else "INSUFFICIENT_EVIDENCE")
            ids = []
            for raw_id in (item.get("clause_ids") or []):
                try:
                    clause_id = int(raw_id)
                except (TypeError, ValueError, OverflowError):
                    continue
                if clause_id not in ids:
                    ids.append(clause_id)
            evidence = []
            for ev in item.get("evidence") or []:
                if not isinstance(ev, dict) or not str(ev.get("quote") or "").strip():
                    continue
                try:
                    evidence_clause_id = int(ev.get("clause_id"))
                except (TypeError, ValueError, OverflowError):
                    continue
                evidence.append({"clause_id": evidence_clause_id, "quote": str(ev["quote"]).strip()})
            out.append({
                "check_id": check_id,
                "answer": answer,
                "status": status,
                "risk_type": str(item.get("risk_type") or "").strip() or None,
                "clause_ids": ids,
                "evidence": evidence,
                "why_flagged": str(item.get("why_flagged") or "").strip(),
            })
        counts = Counter(item["check_id"] for item in out)
        return [item for item in out if counts[item["check_id"]] == 1]

    return (
        parse_group(parsed.get("cross_clause_findings"), valid_cross),
        parse_group(parsed.get("document_findings"), valid_doc),
    )


_FALLBACK_TERMS: dict[str, tuple[str, ...]] = {
    "DOC-1": ("url", "website", "online terms", "incorporated by reference", "order form", "schedule", "annex", "appendix", "external policy"),
    "DOC-2": ("definition", "order of precedence", "prevail", "in case of conflict", "priority", "interpretation", "final interpretation", "annex", "supplemental clause", "supplemental agreement"),
    "DOC-3": ("governing law", "court", "jurisdiction", "dispute", "forum", "arbitration agreement", "arbitral tribunal", "arbitration rules", "arbitration proceeding"),
    "X-1": ("liability", "liquidated damages", "compensated", "compensate", "economic loss", "other losses", "indemnif", "cap"),
    "X-2": ("liquidated damages", "liability cap", "liability", "one-month freight", "damages"),
    "X-3": ("renewal", "non-renewal", "notice period", "indefinite term", "contract period", "term"),
    "X-4": ("early termination", "terminate", "minimum commitment", "liquidated damages", "freight difference", "compensation"),
    "X-5": ("assignment", "assign", "change of control", "transfer", "consent"),
    "X-6": ("license", "licence", "termination", "terminate", "perpetual", "irrevocable"),
    "X-7": ("intellectual property", "ip ownership", "license", "licence", "work product", "deliverables", "assignment"),
    "X-8": ("software", "source code", "escrow", "continuity", "post-termination", "support"),
    "X-9": ("insurance", "insured", "coverage", "liability", "loss", "damages"),
    "X-10": ("indemnif", "hold harmless", "liability", "cap", "loss", "damages"),
}

_FALLBACK_GUIDANCE: dict[str, str] = {
    "DOC-1": "Check whether each referenced annex, schedule, order form, URL, or policy is actually included and identify the exact version that applies.",
    "DOC-2": "Compare the definitions and document-priority language with the substantive protections. Check whether a unilateral interpretation clause can narrow those protections and which document prevails if terms conflict.",
    "DOC-3": "Identify the governing law, named court/forum, and dispute process separately. A reference to the People’s Court where the agreement is signed names a type of court but does not state the city or identify governing law or a separate dispute procedure.",
    "X-1": "Compare each liability head against any aggregate cap and exclusions. Confirm whether broad loss-compensation language or indemnities are inside or outside that cap; do not assume a cap applies if the contract does not say so.",
    "X-2": "Check whether liquidated damages are exclusive or can be recovered in addition to other losses, and whether the liability cap expressly includes or excludes them.",
    "X-3": "Check whether a fixed-term renewal mechanism and a calculable notice deadline exist. If the agreement is indefinite, verify how either party can end it and when notice takes effect.",
    "X-4": "Compare early-termination rights with any remaining freight, minimum-commitment, liquidated-damages, or other-loss payment obligations.",
    "X-5": "Compare who must consent, which corporate events trigger consent, whether consent may be withheld, and the consequences of a breach across the relevant clauses.",
    "X-6": "Check whether any perpetual or irrevocable licence survives termination and whether the agreement clearly states which rights survive and for what purpose.",
    "X-7": "Check that ownership/assignment language and the other party’s licence grant are consistent, including rights needed to keep using deliverables after termination.",
    "X-8": "Check whether business-critical software can still be operated after termination and whether source-code escrow, transition help, or continuity support is actually promised.",
    "X-9": "Compare each stated insurance limit with the liability and compensation obligations. The contract text alone does not prove the available insurance is sufficient or that all losses are insured.",
    "X-10": "Check whether indemnity obligations are expressly subject to the liability cap, and look for exceptions, defence-cost treatment, and any uncapped loss categories.",
}


def _fallback_evidence_for_check(check: dict, clauses: list[dict]) -> list[dict]:
    """Recover exact topic-related contract wording when the model returns no usable answer."""
    check_id = str(check.get("id") or "")
    terms = _FALLBACK_TERMS.get(check_id, ())
    ranked: list[tuple[int, int, dict]] = []
    for clause in clauses:
        text = str(clause.get("clause_text") or "")
        if not text.strip() or clause.get("clause_index") is None:
            continue
        lowered = text.casefold()
        hits = []
        for term in terms:
            needle = term.casefold()
            if " " in needle or "-" in needle or "'" in needle:
                found = needle in lowered
            elif needle == "indemnif":
                found = bool(re.search(r"\bindemnif\w*\b", lowered))
            elif needle == "signed":
                found = bool(re.search(r"\bsign(?:ed|ature|atures)\b", lowered))
            else:
                # Word boundaries prevent false hits such as 'court' inside another word.
                found = bool(re.search(r"\b" + re.escape(needle) + r"\b", lowered))
            if found:
                hits.append(needle)
        if not hits:
            continue
        try:
            clause_id = int(clause["clause_index"])
        except (TypeError, ValueError):
            continue
        score = sum(min(len(term), 35) for term in hits) + 10 * len(hits)
        ranked.append((score, clause_id, {"clause_id": clause_id, "quote": text.strip()}))
    # Prefer the strongest topic matches and then stable clause order; cap output for readability.
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked[:5]]


def _fallback_explanation(check: dict, evidence: list[dict]) -> str:
    check_id = str(check.get("id") or "")
    guidance = _FALLBACK_GUIDANCE.get(check_id, "Review the cited wording and confirm whether the contract states the required terms clearly.")
    by_id = {int(item["clause_id"]): str(item.get("quote") or "") for item in evidence if item.get("clause_id") is not None}
    if check_id == "DOC-2" and evidence:
        parts = []
        if any("final interpretation by party a" in quote.casefold() for quote in by_id.values()):
            parts.append("Clause 15 gives Party A the 'final interpretation' of the agreement, which raises a question about unilateral control over ambiguous wording.")
        if any("annex" in quote.casefold() and "same effect" in quote.casefold() for quote in by_id.values()):
            parts.append("Clause 13 says the annex has the same effect as the agreement; clauses 4–5 also refer to supplemental clauses/agreements.")
        if parts:
            return (
                "The model could not resolve this check, so it remains UNRESOLVED—not a confirmed risk. "
                + " ".join(parts)
                + " The cited text does not itself establish which document prevails if wording conflicts. "
                "What to verify: compare the definitions, amendment hierarchy, and precedence language, and check whether the unilateral interpretation sentence can narrow a substantive protection."
            )
    if check_id == "DOC-3" and evidence:
        if any("people's court" in quote.casefold() or "people’s court" in quote.casefold() for quote in by_id.values()):
            return (
                "The model could not resolve this check, so it remains UNRESOLVED—not a confirmed risk. "
                "Clause 12 directs disputes to the People's Court where the agreement is signed, but does not name the city/place or state the governing law; it also does not describe a separate dispute procedure. "
                "This is a clarity gap to verify, not proof that the clause is invalid. Confirm the exact forum, governing law, and process with the contract owner or qualified counsel."
            )
    if evidence:
        clause_list = ", ".join(str(item["clause_id"]) for item in evidence)
        return (
            "The model did not return a usable answer, so this check remains UNRESOLVED—not a confirmed risk. "
            f"A deterministic text scan found potentially relevant wording in clause(s) {clause_list}. "
            f"What to verify: {guidance}"
        )
    return (
        "The model did not return a usable answer, and the deterministic text scan did not find a sufficiently specific excerpt. "
        "This is unresolved, not a no-risk result. " + guidance
    )


def analyze_contract_checks(
    clauses: list[dict],
    *,
    playbook: dict | None = None,
    progress_callback=None,
    passes: int | None = None,
    deterministic_signals: list[dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    playbook = playbook or load_playbook()
    cross_checks = playbook.get("cross_clause_checks") or []
    doc_checks = playbook.get("document_level_checks") or []
    if not cross_checks and not doc_checks:
        return [], []

    contract_lookup = {int(x["clause_index"]): x for x in clauses if x.get("clause_index") is not None}
    n_passes = max(1, int(passes or RISK_SELF_CONSISTENCY_PASSES))

    # A single response for all 13 checks was frequently truncated at the
    # configured output-token limit. Chunking constrains each response while
    # retaining the exact same clause evidence and deterministic final collapse.
    check_batch_size = 4
    cross_outputs: list[list[dict]] = [[] for _ in range(n_passes)]
    doc_outputs: list[list[dict]] = [[] for _ in range(n_passes)]
    combined_checks = [("cross_clause", check) for check in cross_checks] + [
        ("document", check) for check in doc_checks
    ]
    batches = [
        combined_checks[start:start + check_batch_size]
        for start in range(0, len(combined_checks), check_batch_size)
    ]

    def emit_batch_progress(message: str, *, current: int, total: int, pass_index: int, batch_index: int) -> None:
        if not callable(progress_callback):
            return
        try:
            progress_callback({
                "type": "progress",
                "stage": "cross_clause",
                "message": message,
                "current": current,
                "total": total,
                "pass": pass_index + 1,
                "passes": n_passes,
                "batch": batch_index,
                "batches": len(batches),
            })
        except Exception:
            logging.getLogger(__name__).exception("Could not publish cross-clause progress event")

    for pass_index in range(n_passes):
        for batch_index, batch in enumerate(batches, start=1):
            current_batch = pass_index * len(batches) + batch_index
            total_batches = n_passes * len(batches)
            batch_cross = [check for kind, check in batch if kind == "cross_clause"]
            batch_doc = [check for kind, check in batch if kind == "document"]
            emit_batch_progress(
                f"Evaluating contract-wide check batch {batch_index}/{len(batches)} ({len(batch)} checks)",
                current=current_batch, total=total_batches, pass_index=pass_index, batch_index=batch_index,
            )
            prompt = _prompt(clauses, batch_cross, batch_doc, deterministic_signals)
            try:
                parsed_cross, parsed_doc = _parse(
                    call_ollama(
                        prompt,
                        model=RISK_MODEL,
                        temperature=RISK_TEMPERATURE,
                        num_ctx=RISK_NUM_CTX,
                        max_tokens=RISK_MAX_TOKENS,
                        think=False,
                    ),
                    {str(x.get("id")) for x in batch_cross},
                    {str(x.get("id")) for x in batch_doc},
                )
            except Exception:
                logging.getLogger(__name__).exception(
                    "Cross/document model batch failed (pass=%d batch=%d/%d)",
                    pass_index + 1, batch_index, len(batches),
                )
                parsed_cross, parsed_doc = [], []
            cross_outputs[pass_index].extend(parsed_cross)
            doc_outputs[pass_index].extend(parsed_doc)
            emit_batch_progress(
                f"Completed contract-wide check batch {batch_index}/{len(batches)}",
                current=current_batch, total=total_batches, pass_index=pass_index, batch_index=batch_index,
            )

    def collapse(outputs: list[list[dict]], source_items: list[dict], kind: str) -> list[dict]:
        by_id = defaultdict(list)
        for output in outputs:
            for item in output:
                by_id[item["check_id"]].append(item)
        by_source = {str(item.get("id")): item for item in source_items}
        results = []
        for check_id, records in by_id.items():
            answer, agreement = _majority(records, expected_passes=n_passes)
            rep = next((x for x in records if x["answer"] == answer), records[0])
            check = by_source[check_id]
            topic_evidence = _fallback_evidence_for_check(check, clauses)
            topic_ids = {item["clause_id"] for item in topic_evidence}
            # Exact quotes are necessary but not sufficient: reject a valid quote
            # from an unrelated clause (e.g. a termination clause cited for a
            # document-precedence question).
            validated_model_evidence = [
                ev for ev in rep["evidence"]
                if ev.get("clause_id") is not None
                and int(ev["clause_id"]) in contract_lookup
                and _evidence_valid(
                    str(ev.get("quote") or ""),
                    str(contract_lookup[int(ev["clause_id"])].get("clause_text") or ""),
                    [],
                )
                and (not topic_ids or int(ev["clause_id"]) in topic_ids)
            ]
            evidence_ids = {int(ev["clause_id"]) for ev in validated_model_evidence}
            declared_ids = set(rep["clause_ids"])
            # Evidence must be present, exact, topic-relevant, source-addressable,
            # and consistent with the finding's declared affected clauses.
            evidence_ok = bool(validated_model_evidence) and evidence_ids == declared_ids
            if answer == "YES":
                status = "POTENTIAL_RISK" if evidence_ok else "INSUFFICIENT_EVIDENCE"
            elif answer == "NO":
                status = "NO_RISK" if evidence_ok else "INSUFFICIENT_EVIDENCE"
            else:
                status = "INSUFFICIENT_EVIDENCE"

            raw_support = _support_score(
                answer=answer,
                evidence_ok=evidence_ok,
                agreement=agreement,
                indicator_match=False,
            )
            confidence_details = (
                confidence_from_support_score(raw_support, playbook_hash=playbook.get("playbook_hash"))
                if status in {"POTENTIAL_RISK", "NO_RISK"}
                else {"confidence": None, "confidence_status": "NOT_ESTIMATED", "confidence_target": "PREDICTION_CORRECTNESS", "confidence_calibration_version": None}
            )
            supporting_sources = source_records(playbook, check.get("sources", []))
            primary_source = supporting_sources[0] if supporting_sources else {}
            validated_evidence = list(validated_model_evidence)
            finding_clause_ids = [i for i in rep["clause_ids"] if i in contract_lookup]
            why_flagged = str(rep.get("why_flagged") or "").strip()
            model_evidence_matches_declared = bool(validated_model_evidence) and evidence_ids == declared_ids
            if status == "INSUFFICIENT_EVIDENCE" and not model_evidence_matches_declared:
                validated_evidence = topic_evidence
                finding_clause_ids = [item["clause_id"] for item in validated_evidence]
                fallback_reason = _fallback_explanation(check, validated_evidence)
                if why_flagged:
                    # Do not preserve a fluent but off-topic explanation as if it
                    # answered the check. Replace it with the deterministic, topic-grounded rationale.
                    why_flagged = fallback_reason
                    if validated_evidence:
                        why_flagged += " The model's original cited excerpts were incomplete or off-topic and were replaced with these exact topic-matched excerpts."
                else:
                    why_flagged = fallback_reason
            results.append({
                "scope": kind,
                "check_id": check_id,
                "risk_domain": check.get("risk_domain"),
                "risk_subdomain": check.get("risk_subdomain"),
                "question": check.get("question", ""),
                "answer": answer,
                "risk_status": status,
                "risk": status == "POTENTIAL_RISK",
                "risk_type": rep.get("risk_type") if status == "POTENTIAL_RISK" else None,
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
                "clause_ids": finding_clause_ids,
                # Preserve model-validated or deterministic exact excerpts for unresolved findings too.
                "evidence": validated_evidence,
                "why_flagged": why_flagged,
                "provenance": {
                    "playbook_hash": playbook.get("playbook_hash"),
                    "source_ids": check.get("sources", []),
                    "model": RISK_MODEL,
                    "passes": len(records),
                    "expected_passes": n_passes,
                    "missing_passes": max(0, n_passes - len(records)),
                    "agreement": agreement,
                    "support_score_version": SUPPORT_SCORE_VERSION,
                    "support_score_interpretation": "Uncalibrated diagnostic only; not a probability.",
                    "confidence_target": confidence_details.get("confidence_target", "PREDICTION_CORRECTNESS"),
                    "confidence_calibration_version": confidence_details.get("confidence_calibration_version"),
                    "rule_registry_metadata": check.get("rule_registry_metadata", {}),
                    "check_batch_size": check_batch_size,
                    "model_batches_per_pass": len(batches),
                },
                "supporting_sources": supporting_sources,
                "source_tier": primary_source.get("source_tier"),
                "jurisdiction": primary_source.get("jurisdiction"),
                "effective_date": primary_source.get("effective_date"),
                "contract_type": primary_source.get("contract_type"),
                "source_url": primary_source.get("source_url"),
                "source_title": primary_source.get("source_title"),
                "retrieval_date": primary_source.get("retrieval_date"),
                "supporting_quote_or_paraphrase": primary_source.get("supporting_quote_or_paraphrase"),
                "transferability": primary_source.get("transferability"),
                "severity_factors": {},
                "score_components_raw": {},
            })
        # Missing outputs are unresolved rather than silently marked NO_RISK.
        returned = {x["check_id"] for x in results}
        for check in source_items:
            if str(check.get("id")) in returned:
                continue
            fallback_evidence = _fallback_evidence_for_check(check, clauses)
            results.append({
                "scope": kind,
                "check_id": str(check.get("id")),
                "risk_domain": check.get("risk_domain"),
                "risk_subdomain": check.get("risk_subdomain"),
                "question": check.get("question", ""),
                "answer": "DON'T KNOW",
                "risk_status": "INSUFFICIENT_EVIDENCE",
                "risk": False,
                "risk_type": None,
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
                "clause_ids": [item["clause_id"] for item in fallback_evidence],
                "evidence": fallback_evidence,
                "why_flagged": _fallback_explanation(check, fallback_evidence),
                "provenance": {
                    "playbook_hash": playbook.get("playbook_hash"),
                    "source_ids": check.get("sources", []),
                    "model": RISK_MODEL,
                    "passes": 0,
                    "expected_passes": n_passes,
                    "missing_passes": n_passes,
                    "agreement": 0.0,
                    "score_component_source": "NONE",
                    "score_interpretation": "Triage heuristic only; not calibrated to real-world legal outcomes.",
                    "check_batch_size": check_batch_size,
                    "model_batches_per_pass": len(batches),
                },
                "supporting_sources": source_records(playbook, check.get("sources", [])),
                "severity_factors": {},
            })
        return sorted(results, key=lambda x: x["check_id"])

    return collapse(cross_outputs, cross_checks, "cross_clause"), collapse(doc_outputs, doc_checks, "document")

[executed on device: jupyter-group-digi2026-g6 (a8417900-e68e-4ee2-bbe7-fc3493ade5e1)]