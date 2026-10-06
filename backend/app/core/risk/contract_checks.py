"""Cross-clause and document-level Phase 2 checks with exact evidence validation."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from ..config import RISK_MAX_TOKENS, RISK_MODEL, RISK_NUM_CTX, RISK_SELF_CONSISTENCY_PASSES, RISK_TEMPERATURE
from ..rag.generator import call_ollama
from .calibration import calibrate_risk_probability, calibrate_severity, load_calibration
from .risk_engine import _evidence_valid, _majority, _severity_signal, _support_score
from .risk_playbook import load_playbook, source_records
from .risk_scoring import score_finding


def _candidate_clauses(clauses: list[dict], pair: list[str]) -> list[dict]:
    names = {str(x).strip().lower() for x in pair}
    selected = [
        item for item in clauses
        if str(item.get("predicted_label") or "").strip().lower() in names
    ]
    if selected:
        return selected
    # Fall back to risk-relevant text when the classifier label is not a close
    # CUAD category match.
    tokens = [re.findall(r"[a-z0-9]+", str(x).lower()) for x in pair]
    terms = {term for group in tokens for term in group if len(term) > 4}
    return [
        item for item in clauses
        if any(term in str(item.get("clause_text") or "").lower() for term in terms)
    ][:20]


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
      "why_flagged": "concise explanation",
      "score_components": {{"exposure_magnitude": 0, "likelihood_uncertainty": 0, "scope_duration": 0, "control_weakness": 0}}
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
      "why_flagged": "concise explanation",
      "score_components": {{"exposure_magnitude": 0, "likelihood_uncertainty": 0, "scope_duration": 0, "control_weakness": 0}}
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
        out = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            check_id = str(item.get("check_id") or "").strip()
            answer = str(item.get("answer") or "").strip().upper().replace("UNKNOWN", "DON'T KNOW")
            if check_id not in valid_ids or answer not in {"YES", "NO", "DON'T KNOW"}:
                continue
            status = str(item.get("status") or "").strip().upper()
            if status not in {"POTENTIAL_RISK", "NO_RISK", "INSUFFICIENT_EVIDENCE"}:
                status = "POTENTIAL_RISK" if answer == "YES" else ("NO_RISK" if answer == "NO" else "INSUFFICIENT_EVIDENCE")
            ids = [int(x) for x in (item.get("clause_ids") or []) if str(x).lstrip("-").isdigit()]
            evidence = []
            for ev in item.get("evidence") or []:
                if isinstance(ev, dict) and str(ev.get("quote") or "").strip():
                    evidence.append({"clause_id": ev.get("clause_id"), "quote": str(ev["quote"]).strip()})
            factors = item.get("score_components") if isinstance(item.get("score_components"), dict) else (item.get("severity_factors") if isinstance(item.get("severity_factors"), dict) else {})
            out.append({
                "check_id": check_id,
                "answer": answer,
                "status": status,
                "risk_type": str(item.get("risk_type") or "").strip() or None,
                "clause_ids": ids,
                "evidence": evidence,
                "why_flagged": str(item.get("why_flagged") or "").strip(),
                "score_components": {
                    key: (float(factors[key]) if str(factors.get(key)).replace(".", "", 1).isdigit() and 0 <= float(factors[key]) <= 5 else None)
                    for key in ("exposure_magnitude", "likelihood_uncertainty", "scope_duration", "control_weakness")
                },
            })
        return out

    return (
        parse_group(parsed.get("cross_clause_findings"), valid_cross),
        parse_group(parsed.get("document_findings"), valid_doc),
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

    calibration = load_calibration()
    contract_lookup = {int(x["clause_index"]): x for x in clauses if x.get("clause_index") is not None}
    prompts = _prompt(clauses, cross_checks, doc_checks, deterministic_signals)
    n_passes = max(1, int(passes or RISK_SELF_CONSISTENCY_PASSES))
    cross_outputs: list[list[dict]] = []
    doc_outputs: list[list[dict]] = []

    for _ in range(n_passes):
        try:
            parsed_cross, parsed_doc = _parse(
                call_ollama(
                    prompts,
                    model=RISK_MODEL,
                    temperature=RISK_TEMPERATURE,
                    num_ctx=RISK_NUM_CTX,
                    max_tokens=RISK_MAX_TOKENS,
                    think=False,
                ),
                {str(x.get("id")) for x in cross_checks},
                {str(x.get("id")) for x in doc_checks},
            )
        except Exception:
            parsed_cross, parsed_doc = [], []
        cross_outputs.append(parsed_cross)
        doc_outputs.append(parsed_doc)

    def collapse(outputs: list[list[dict]], source_items: list[dict], kind: str) -> list[dict]:
        by_id = defaultdict(list)
        for output in outputs:
            for item in output:
                by_id[item["check_id"]].append(item)
        by_source = {str(item.get("id")): item for item in source_items}
        results = []
        for check_id, records in by_id.items():
            answer, agreement = _majority(records)
            rep = next((x for x in records if x["answer"] == answer), records[0])
            evidence_ok = bool(rep["evidence"]) and all(
                int(ev.get("clause_id", -1)) in contract_lookup
                and _evidence_valid(
                    str(ev.get("quote") or ""),
                    str(contract_lookup[int(ev.get("clause_id"))].get("clause_text") or ""),
                    [],
                )
                for ev in rep["evidence"]
            )
            if answer == "YES":
                status = "POTENTIAL_RISK" if evidence_ok else "INSUFFICIENT_EVIDENCE"
            elif answer == "NO":
                status = "NO_RISK"
            else:
                status = "INSUFFICIENT_EVIDENCE"

            raw_support = _support_score(
                answer=answer,
                evidence_ok=evidence_ok,
                agreement=agreement,
                indicator_match=False,
            )
            confidence_values = [
                float(contract_lookup[int(cid)].get("classification_confidence"))
                for cid in rep.get("clause_ids", [])
                if int(cid) in contract_lookup and contract_lookup[int(cid)].get("classification_confidence") is not None
            ]
            extraction_confidence = min(confidence_values) if confidence_values else None
            score_details = score_finding({                "risk_status": status,
                "risk": status == "POTENTIAL_RISK",
                "risk_type": rep.get("risk_type"),
                "question": by_source[check_id].get("question", ""),
                "check_id": check_id,
                "scope": kind,
                "evidence": " ".join(str(x.get("quote") or "") for x in rep.get("evidence") or []),
                "why_flagged": rep.get("why_flagged"),
                "score_components": rep.get("score_components") or {},
                "deterministic_cross_check": bool(deterministic_signals and any(x.get("id") == check_id for x in deterministic_signals)),
            }, extraction_confidence=extraction_confidence) if status == "POTENTIAL_RISK" else None
            severity_score = float(score_details["final_score"]) if score_details and score_details.get("final_score") is not None else None
            severity_signal = round(severity_score / 20.0, 4) if severity_score is not None else None
            calibrated_confidence = (
                calibrate_risk_probability(raw_support, calibration)
                if status == "POTENTIAL_RISK" else None
            )
            calibrated_severity = calibrate_severity(severity_score, calibration)
            check = by_source[check_id]
            supporting_sources = source_records(playbook, check.get("sources", []))
            primary_source = supporting_sources[0] if supporting_sources else {}
            results.append({
                "scope": kind,
                "check_id": check_id,
                "question": check.get("question", ""),
                "answer": answer,
                "risk_status": status,
                "risk": status == "POTENTIAL_RISK",
                "risk_type": rep.get("risk_type") if status == "POTENTIAL_RISK" else None,
                "risk_level": (calibrated_severity["level"] if calibrated_severity and status == "POTENTIAL_RISK" else (score_details["severity"] if score_details and status == "POTENTIAL_RISK" else None)),
                "raw_support_score": raw_support,
                "severity_score": severity_score,
                "severity_signal": severity_signal,
                "score_components": score_details["score_components"] if score_details else {},
                "base_score": score_details["base_score"] if score_details else None,
                "score_modifiers": score_details["modifiers"] if score_details else [],
                "final_score": score_details["final_score"] if score_details else None,
                "score_override_reason": score_details["override_reason"] if score_details else None,
                "human_review_required": score_details["human_review_required"] if score_details else True,
                "review_escalation": score_details["escalation"] if score_details else "LEGAL_REVIEW",
                "confidence": calibrated_confidence,
                "confidence_status": "CALIBRATED" if calibrated_confidence is not None else "UNCALIBRATED",
                "severity_status": "CALIBRATED" if calibrated_severity else ("RULE_BASED_TRIAGE" if severity_score is not None else ("INCOMPLETE" if score_details else "UNCALIBRATED")),
                "severity_probabilities": calibrated_severity["probabilities"] if calibrated_severity else {},
                "ground_truth_status": "PLAYBOOK_DERIVED",
                "clause_ids": [i for i in rep["clause_ids"] if i in contract_lookup],
                "evidence": [
                    ev for ev in rep["evidence"]
                    if int(ev.get("clause_id", -1)) in contract_lookup
                    and str(ev.get("quote") or "") in str(contract_lookup[int(ev["clause_id"])]["clause_text"])
                ] if status == "POTENTIAL_RISK" else [],
                "why_flagged": rep.get("why_flagged", ""),
                "provenance": {
                    "playbook_hash": playbook.get("playbook_hash"),
                    "source_ids": check.get("sources", []),
                    "model": RISK_MODEL,
                    "passes": len(records),
                    "agreement": agreement,
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
                "severity_factors": rep.get("severity_factors") or rep.get("score_components") or {},
                "score_components_raw": rep.get("score_components") or {},
            })
        # Missing outputs are unresolved rather than silently marked NO_RISK.
        returned = {x["check_id"] for x in results}
        for check in source_items:
            if str(check.get("id")) in returned:
                continue
            results.append({
                "scope": kind,
                "check_id": str(check.get("id")),
                "question": check.get("question", ""),
                "answer": "DON'T KNOW",
                "risk_status": "INSUFFICIENT_EVIDENCE",
                "risk": False,
                "risk_type": None,
                "risk_level": None,
                "raw_support_score": 0.0,
                "severity_signal": None,
                "confidence": None,
                "confidence_status": "UNCALIBRATED",
                "severity_status": "UNCALIBRATED",
                "severity_probabilities": {},
                "ground_truth_status": "PLAYBOOK_DERIVED",
                "clause_ids": [],
                "evidence": [],
                "why_flagged": "No usable model answer was returned.",
                "provenance": {
                    "playbook_hash": playbook.get("playbook_hash"),
                    "source_ids": check.get("sources", []),
                    "model": RISK_MODEL,
                    "passes": n_passes,
                    "agreement": 0.0,
                },
                "supporting_sources": source_records(playbook, check.get("sources", [])),
                "severity_factors": {},
            })
        return sorted(results, key=lambda x: x["check_id"])

    return collapse(cross_outputs, cross_checks, "cross_clause"), collapse(doc_outputs, doc_checks, "document")
