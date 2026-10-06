"""Phase 2 clause-level risk engine with explicit provenance and calibration-safe confidence."""
from __future__ import annotations

import json
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
)
from ..rag.generator import call_ollama
from .calibration import calibrate_risk_probability, calibrate_severity, load_calibration
from .risk_playbook import applicable_checks, load_playbook, source_records
from .contract_context import retrieve_related_contract_context
from .risk_detector import detect_legal_indicators

ProgressCallback = Callable[[dict], None]

VALID_STATUS = {"POTENTIAL_RISK", "NO_RISK", "INSUFFICIENT_EVIDENCE", "ERROR"}
VALID_ANSWER = {"YES", "NO", "DON'T KNOW", "UNKNOWN"}


def _emit(callback: ProgressCallback | None, stage: str, message: str, **details) -> None:
    if callback:
        callback({"type": "progress", "stage": stage, "message": message, **details})


def _evidence_valid(evidence: str, clause_text: str, context: list[dict]) -> bool:
    evidence = str(evidence or "").strip()
    if not evidence:
        return False
    if evidence in str(clause_text or ""):
        return True
    return any(
        evidence in str(item.get("clause_text") or "")
        for item in context
    )


def _factor(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if 0.0 <= number <= 3.0 else None


def _severity_signal(factors: dict) -> float | None:
    values = [_factor(factors.get(key)) for key in ("impact", "scope", "asymmetry", "duration", "reversibility")]
    values = [v for v in values if v is not None]
    if len(values) < 3:
        return None
    return round(sum(values) / (3.0 * len(values)), 4)


def _support_score(*, answer: str, evidence_ok: bool, agreement: float, indicator_match: bool) -> float:
    if answer not in {"YES", "NO", "DON'T KNOW"}:
        return 0.0
    base = 1.0 if answer == "YES" else (0.55 if answer == "DON'T KNOW" else 0.25)
    evidence_component = 0.30 if evidence_ok else 0.0
    indicator_component = 0.10 if indicator_match else 0.0
    return round(min(1.0, 0.60 * base + evidence_component + 0.10 * agreement + indicator_component), 4)


def _prompt(
    *,
    clause_text: str,
    clause_type: str,
    checks: list[dict],
    indicators: dict,
    context: list[dict],
    playbook: dict,
) -> str:
    checklist = [
        {
            "id": item["id"],
            "question": item["question"],
            "flag_if": item["flag_if"],
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
8. Return JSON only. No hidden reasoning, no markdown, no extra text.

CURRENT CLAUSE
ID: {clause_type}
TEXT:
{clause_text}

DETERMINISTIC INDICATORS
{json.dumps(indicators, indent=2, ensure_ascii=False)}

RELATED SAME-CONTRACT CLAUSES
{json.dumps(context, indent=2, ensure_ascii=False)}

PLAYBOOK CHECKS
{json.dumps(checklist, indent=2, ensure_ascii=False)}

Return:
{{
  "checks": [
    {{
      "check_id": "one of the supplied ids",
      "answer": "YES | NO | DON'T KNOW",
      "status": "POTENTIAL_RISK | NO_RISK | INSUFFICIENT_EVIDENCE",
      "risk_type": "specific risk type or null",
      "evidence": "exact contiguous quote or empty string",
      "why_flagged": "concise explanation or empty string",
      "severity_factors": {{
        "impact": 0,
        "scope": 0,
        "asymmetry": 0,
        "duration": 0,
        "reversibility": 0
      }}
    }}
  ]
}}

Factor scale: 0=none/minor, 1=limited, 2=material, 3=extreme/one-sided.
Use the factors only as raw signals. Do not turn them into a calibrated probability.
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
    out = []
    for item in parsed["checks"]:
        if not isinstance(item, dict):
            continue
        check_id = str(item.get("check_id") or "").strip()
        answer = str(item.get("answer") or "").strip().upper()
        status = str(item.get("status") or "").strip().upper()
        if check_id not in valid_ids or answer not in VALID_ANSWER:
            continue
        if answer == "UNKNOWN":
            answer = "DON'T KNOW"
        if status not in VALID_STATUS:
            status = "POTENTIAL_RISK" if answer == "YES" else ("NO_RISK" if answer == "NO" else "INSUFFICIENT_EVIDENCE")
        factors = item.get("severity_factors") if isinstance(item.get("severity_factors"), dict) else {}
        out.append(
            {
                "check_id": check_id,
                "answer": answer,
                "status": status,
                "risk_type": str(item.get("risk_type") or "").strip() or None,
                "evidence": str(item.get("evidence") or "").strip(),
                "why_flagged": str(item.get("why_flagged") or "").strip(),
                "severity_factors": {
                    key: _factor(factors.get(key))
                    for key in ("impact", "scope", "asymmetry", "duration", "reversibility")
                },
            }
        )
    return out


def _majority(records: list[dict]) -> tuple[str, float]:
    if not records:
        return "DON'T KNOW", 0.0
    votes = Counter(record["answer"] for record in records)
    answer, count = votes.most_common(1)[0]
    return answer, round(count / len(records), 4)


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
) -> list[dict]:
    playbook = playbook or load_playbook()
    calibration = load_calibration()
    checks = applicable_checks(playbook, clause_type)
    if not checks:
        return []

    context = []
    if query_vector and contract_clauses:
        context = retrieve_related_contract_context(
            target_clause_index=clause_index,
            target_vector=query_vector,
            clauses=contract_clauses,
            top_k=RISK_CONTEXT_TOP_K,
        )

    indicators = detect_legal_indicators(clause_text, clause_type)
    prompt = _prompt(
        clause_text=clause_text,
        clause_type=clause_type,
        checks=checks,
        indicators=indicators,
        context=context,
        playbook=playbook,
    )

    n_passes = max(1, int(passes if passes is not None else RISK_SELF_CONSISTENCY_PASSES))
    outputs: list[list[dict]] = []
    valid_ids = {str(item["id"]) for item in checks}
    _emit(progress_callback, "risk_clause", f"Evaluating risk checks for clause {clause_index}", clause_index=clause_index)

    for pass_index in range(n_passes):
        try:
            raw = call_ollama(
                prompt,
                model=RISK_MODEL,
            )
            parsed = _parse(raw, valid_ids)
        except Exception:
            parsed = []
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
    findings: list[dict] = []
    for check_id, records in by_check.items():
        answer, agreement = _majority(records)
        representative = next((x for x in records if x["answer"] == answer), records[0])
        evidence = representative["evidence"]
        evidence_ok = _evidence_valid(evidence, clause_text, context)
        indicator_match = bool(indicators.get("matched_indicators"))
        status = representative["status"]
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
            indicator_match=indicator_match,
        )
        severity_signal = _severity_signal(representative.get("severity_factors") or {})
        calibrated_confidence = (
            calibrate_risk_probability(raw_support, calibration)
            if status == "POTENTIAL_RISK"
            else None
        )
        calibrated_severity = calibrate_severity(severity_signal, calibration)
        source_ids = checks_by_id[check_id].get("sources", [])
        findings.append(
            {
                "clause_index": clause_index,
                "clause_text": clause_text,
                "predicted_label": clause_type,
                "check_id": check_id,
                "question": checks_by_id[check_id]["question"],
                "answer": answer,
                "risk_status": status,
                "risk_type": representative.get("risk_type") if status == "POTENTIAL_RISK" else None,
                "risk": status == "POTENTIAL_RISK",
                "risk_level": calibrated_severity["level"] if calibrated_severity and status == "POTENTIAL_RISK" else None,
                "raw_support_score": raw_support,
                "severity_signal": severity_signal,
                "confidence": calibrated_confidence,
                "confidence_status": "CALIBRATED" if calibrated_confidence is not None else "UNCALIBRATED",
                "severity_status": "CALIBRATED" if calibrated_severity else "UNCALIBRATED",
                "severity_probabilities": (
                    calibrated_severity["probabilities"] if calibrated_severity else {}
                ),
                "ground_truth_status": "PLAYBOOK_DERIVED",
                "provenance": {
                    "playbook_hash": playbook.get("playbook_hash"),
                    "check_id": check_id,
                    "source_ids": source_ids,
                    "model": RISK_MODEL,
                    "passes": len(records),
                    "agreement": agreement,
                    "deterministic_indicators": indicators.get("matched_indicators", []),
                },
                "why_flagged": representative.get("why_flagged") if status == "POTENTIAL_RISK" else (
                    representative.get("why_flagged") or "No evidence-supported issue identified by the check."
                ),
                "evidence": evidence if evidence_ok and status == "POTENTIAL_RISK" else "",
                "supporting_sources": source_records(playbook, source_ids),
                "related_contract_context": context,
                "severity_factors": representative.get("severity_factors") or {},
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
                "question": check["question"],
                "answer": "DON'T KNOW",
                "risk_status": "INSUFFICIENT_EVIDENCE",
                "risk_type": None,
                "risk": False,
                "risk_level": None,
                "raw_support_score": 0.0,
                "severity_signal": None,
                "confidence": None,
                "confidence_status": "UNCALIBRATED",
                "ground_truth_status": "PLAYBOOK_DERIVED",
                "provenance": {
                    "playbook_hash": playbook.get("playbook_hash"),
                    "check_id": check["id"],
                    "source_ids": check.get("sources", []),
                    "model": RISK_MODEL,
                    "passes": n_passes,
                    "agreement": 0.0,
                    "deterministic_indicators": indicators.get("matched_indicators", []),
                },
                "why_flagged": "The model did not return a usable evidence-grounded answer for this check.",
                "evidence": "",
                "supporting_sources": source_records(playbook, check.get("sources", [])),
                "related_contract_context": context,
                "severity_factors": {},
            }
        )
    return sorted(findings, key=lambda item: (item["clause_index"], item["check_id"]))
