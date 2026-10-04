"""
Generation stage of the RAG pipeline.

Flow:
  advanced_preprocess -> retrieve -> candidates -> high-precision rules
  -> Qwen3 Thinking (Ollama) -> parse (strip <think>) -> confidence gate

classify_clause() is the orchestrator. Prompt text lives in prompt.py.
"""

from __future__ import annotations

import json
import logging
import re
import time
from difflib import SequenceMatcher
from typing import Callable

import requests
from qdrant_client import QdrantClient

from ..config import (
    CLASSIFIER_TEMPERATURE,
    MIN_RETRIEVAL_CONFIDENCE,
    OLLAMA_MAX_RETRY_ATTEMPTS,
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_URL,
    OLLAMA_TIMEOUT_SECONDS,
    TOP_K,
)
from .retriever import retrieve_similar
from .prompt import build_prompt, load_label_definitions  # re-exported for callers
from .thinking_client import call_thinking_ollama, extract_json_object, strip_thinking
from .advanced_preprocess import advanced_preprocess
from .high_precision_rules import high_precision_rule_label
from .candidate_utils import fuse_confidence

__all__ = [
    "extract_legal_information",
    "call_ollama",
    "parse_prediction",
    "parse_prediction_result",
    "classify_clause",
    "load_label_definitions",
    "high_precision_rule_label",
]

ProgressCallback = Callable[[dict], None]
logger = logging.getLogger(__name__)


def _emit(callback: ProgressCallback | None, stage: str, message: str, **details) -> None:
    if callback:
        callback({"type": "progress", "stage": stage, "message": message, **details})


LEGAL_CONCEPT_PATTERNS: list[tuple[str, str]] = [
    ("change of control", r"\bchange of control\b"),
    ("governing law", r"\bgoverning law\b"),
    ("insurance", r"\binsur(?:e|ance|ed|ing)\b"),
    ("audit", r"\baudit(?:s|ed|ing| rights?)?\b"),
    ("license", r"\blicen[cs](?:e|es|ed|ing)?\b"),
    ("assignment", r"\bassign(?:ment|ed|ing)?\b"),
    ("transfer", r"\btransfer(?:red|ring|able)?\b"),
    ("termination", r"\bterminat(?:e|ed|ing|ion)\b"),
    ("renewal", r"\brenew(?:al|ed|ing)?\b"),
    ("notice", r"\bnotice\b"),
    ("liability", r"\bliabilit(?:y|ies)\b"),
    ("warranty", r"\bwarrant(?:y|ies)\b"),
    ("royalty", r"\broyalt(?:y|ies)\b"),
    ("revenue share", r"\brevenue(?:/profit)? sharing\b|\bprofit sharing\b"),
    ("price", r"\bprice(?:s|d|ing)?\b"),
    ("discount", r"\bdiscount(?:s|ed|ing)?\b"),
    ("non-compete", r"\bnon-compete\b"),
    ("non-solicit", r"\bnon-solicit\b"),
    ("exclusivity", r"\bexclusiv(?:e|ity)\b"),
    ("source code escrow", r"\bsource code escrow\b"),
    ("liquidated damages", r"\bliquidated damages\b"),
    ("minimum commitment", r"\bminimum commitment\b"),
    ("right of first refusal", r"\bright of first refusal\b"),
    ("right of first offer", r"\bright of first offer\b"),
    ("right of first negotiation", r"\bright of first negotiation\b"),
    ("first refusal", r"\bfirst refusal\b"),
    ("first offer", r"\bfirst offer\b"),
    ("first negotiation", r"\bfirst negotiation\b"),
    ("escrow", r"\bescrow\b"),
    ("perpetual", r"\bperpetual\b"),
    ("irrevocable", r"\birrevocable\b"),
    ("unlimited", r"\bunlimited\b"),
    ("uncapped", r"\buncapped\b"),
    ("volume", r"\bvolume\b"),
]

LEGAL_ACTION_PATTERNS: list[tuple[str, str]] = [
    ("grant", r"\bgrant(?:s|ed|ing)?\b"),
    ("license", r"\blicen[cs](?:e|es|ed|ing)?\b"),
    ("assign", r"\bassign(?:s|ed|ing|ment)?\b"),
    ("delegate", r"\bdelegat(?:e|es|ed|ing|ion)\b"),
    ("transfer", r"\btransfer(?:s|red|ring|able)?\b"),
    ("terminate", r"\bterminat(?:e|es|ed|ing|ion)?\b"),
    ("renew", r"\brenew(?:s|ed|ing|al)?\b"),
    ("notify", r"\bnotif(?:y|ies|ied|ication)\b"),
    ("pay", r"\bpay(?:s|ment|ing|able)?\b"),
    ("provide", r"\bprovid(?:e|es|ed|ing)\b"),
    ("audit", r"\baudit(?:s|ed|ing)?\b"),
    ("inspect", r"\binspect(?:s|ed|ing)?\b"),
    ("restrict", r"\brestrict(?:s|ed|ing|ion)?\b"),
    ("compete", r"\bcompet(?:e|es|ed|ing|ition)\b"),
    ("solicit", r"\bsolicit(?:s|ed|ing|ation)?\b"),
    ("purchase", r"\bpurchas(?:e|es|ed|ing|ed)\b"),
    ("sell", r"\bsell(?:s|ing|er|ers)?\b"),
    ("use", r"\buse(?:s|d|ing)?\b"),
    ("sublicense", r"\bsublicen[cs](?:e|es|ed|ing)?\b"),
    ("insure", r"\binsur(?:e|es|ed|ing|ance)\b"),
    ("disclose", r"\bdisclos(?:e|es|ed|ing|ure)\b"),
    ("hold harmless", r"\bhold harmless\b"),
]

RIGHT_PATTERNS: list[tuple[str, str]] = [
    ("right to", r"\bright to\b"),
    ("may", r"\bmay\b"),
    ("entitled to", r"\bentitled to\b"),
    ("authorized to", r"\bauthorized to\b"),
    ("permitted to", r"\bpermitted to\b"),
    ("shall have the right to", r"\bshall have the right to\b"),
]

OBLIGATION_PATTERNS: list[tuple[str, str]] = [
    ("shall", r"\bshall\b"),
    ("must", r"\bmust\b"),
    ("agree to", r"\bagree to\b"),
    ("agrees to", r"\bagrees to\b"),
    ("required to", r"\brequired to\b"),
    ("is required to", r"\bis required to\b"),
    ("undertakes to", r"\bundertakes to\b"),
]

RESTRICTION_PATTERNS: list[tuple[str, str]] = [
    ("shall not", r"\bshall not\b"),
    ("may not", r"\bmay not\b"),
    ("no ", r"\bno\b"),
    ("not", r"\bnot\b"),
    ("except", r"\bexcept\b"),
    ("only", r"\bonly\b"),
    ("solely", r"\bsolely\b"),
    ("without", r"\bwithout\b"),
    ("prohibited", r"\bprohibit(?:ed|s|ing)?\b"),
]

CONDITION_PATTERNS: list[tuple[str, str]] = [
    ("provided that", r"\bprovided that\b"),
    ("subject to", r"\bsubject to\b"),
    ("if", r"\bif\b"),
    ("unless", r"\bunless\b"),
    ("in the event", r"\bin the event\b"),
    ("upon", r"\bupon\b"),
    ("as long as", r"\bas long as\b"),
    ("only if", r"\bonly if\b"),
]

DATE_PATTERN = re.compile(
    r"\b(?:\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{1,2}[/\-]\d{1,2}|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},\s+\d{4}|"
    r"\d{1,2}\s+days?|\d{1,2}\s+months?|\d{1,2}\s+years?)\b",
    re.IGNORECASE,
)
MONEY_PATTERN = re.compile(
    r"(?:[$€£]\s?\d[\d,]*(?:\.\d+)?|\b(?:usd|eur|gbp)\s?\d[\d,]*(?:\.\d+)?\b|"
    r"\b\d[\d,]*(?:\.\d+)?\s?(?:usd|eur|gbp)\b)",
    re.IGNORECASE,
)
PERCENT_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s?(?:%|percent|per cent)\b", re.IGNORECASE)
NUMERIC_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?(?:\s*(?:days?|months?|years?|weeks?|hours?))?\b",
    re.IGNORECASE,
)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized.lower() in seen:
            continue
        seen.add(normalized.lower())
        ordered.append(normalized)
    return ordered


def _collect_matches(text: str, patterns: list[tuple[str, str]]) -> list[str]:
    matches: list[str] = []
    lowered = text.lower()
    for label, pattern in patterns:
        if re.search(pattern, lowered, re.IGNORECASE):
            matches.append(label)
    return _dedupe_preserve_order(matches)


def _collect_span_matches(text: str, pattern: re.Pattern[str]) -> list[str]:
    return _dedupe_preserve_order([m.group(0).strip() for m in pattern.finditer(text)])


def _collect_legal_keywords(text: str) -> list[str]:
    vocabulary = [
        "termination", "terminate", "renewal", "renew", "notice", "written notice",
        "license", "licence", "assignment", "assign", "transfer", "liability",
        "warranty", "insurance", "audit", "exclusivity", "exclusive", "royalty",
        "revenue", "profit", "price", "discount", "non-compete", "non-solicit",
        "source code escrow", "liquidated damages", "minimum commitment",
        "first refusal", "first offer", "first negotiation", "governing law",
        "change of control", "perpetual", "irrevocable", "unlimited", "uncapped", "volume",
    ]
    lowered = text.lower()
    return _dedupe_preserve_order([p for p in vocabulary if p in lowered])


def extract_legal_information(clause_text: str) -> dict[str, list[str]]:
    text = str(clause_text or "").strip()
    legal_concepts = _collect_matches(text, LEGAL_CONCEPT_PATTERNS)
    legal_actions = _collect_matches(text, LEGAL_ACTION_PATTERNS)
    rights = _collect_matches(text, RIGHT_PATTERNS)
    obligations = _collect_matches(text, OBLIGATION_PATTERNS)
    restrictions = _collect_matches(text, RESTRICTION_PATTERNS)
    conditions = _collect_matches(text, CONDITION_PATTERNS)
    dates = _collect_span_matches(text, DATE_PATTERN)
    money = _collect_span_matches(text, MONEY_PATTERN)
    percentages = _collect_span_matches(text, PERCENT_PATTERN)
    numeric_candidates = _collect_span_matches(text, NUMERIC_PATTERN)
    numeric_values = _dedupe_preserve_order([v for v in numeric_candidates if v not in dates])
    keywords = _dedupe_preserve_order(
        _collect_legal_keywords(text) + legal_concepts + legal_actions + rights
        + obligations + restrictions + conditions
    )
    return {
        "keywords": keywords,
        "legal_concepts": legal_concepts,
        "legal_actions": legal_actions,
        "rights": rights,
        "obligations": obligations,
        "restrictions": restrictions,
        "conditions": conditions,
        "dates": dates,
        "durations": _dedupe_preserve_order([
            v for v in numeric_candidates
            if re.search(r"\b(?:days?|months?|years?|weeks?|hours?)\b", v, re.I)
        ]),
        "monetary_values": money,
        "percentages": percentages,
        "numeric_values": numeric_values,
    }


def call_ollama(prompt: str, *, model: str | None = None) -> str:
    return call_thinking_ollama(
        prompt,
        model=model or OLLAMA_MODEL,
        temperature=CLASSIFIER_TEMPERATURE,
        num_ctx=OLLAMA_NUM_CTX,
    )


def _canonical_labels(labels: list[str]) -> dict[str, str]:
    return {label.strip().lower(): label for label in labels if str(label).strip()}


FORBIDDEN_CLASSIFICATION_OUTPUTS = {
    "UNKNOWN", "OTHER", "NONE", "UNCLASSIFIED", "NO_MATCH", "NO_LABEL",
}
NO_APPLICABLE_LABEL = "NO_APPLICABLE_LABEL"


def _invalid_prediction(status: str, raw_candidate: str | None = None) -> dict[str, str | None]:
    return {"prediction": None, "status": status, "raw_candidate": raw_candidate}


def parse_prediction_result(
    raw_response: str,
    labels: list[str],
    candidate_labels: list[str] | None = None,
) -> dict[str, str | None]:
    all_labels = _canonical_labels(labels)
    candidates = candidate_labels or labels
    candidate_map = _canonical_labels(candidates)
    raw_text = str(raw_response or "").strip()
    parsed = extract_json_object(raw_text)
    if parsed is None:
        residual = strip_thinking(raw_text)
        try:
            parsed = json.loads(residual)
        except json.JSONDecodeError:
            match = re.search(r"\{.*?\}", residual, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except json.JSONDecodeError:
                    parsed = None

    if not isinstance(parsed, dict) or not isinstance(parsed.get("clause_type"), str):
        return _invalid_prediction("MALFORMED_RESPONSE")

    raw_candidate = parsed["clause_type"].strip()
    normalized = raw_candidate.upper()
    if normalized == NO_APPLICABLE_LABEL:
        return {
            "prediction": NO_APPLICABLE_LABEL,
            "status": "NO_APPLICABLE_LABEL",
            "raw_candidate": raw_candidate,
        }
    if not raw_candidate or normalized in FORBIDDEN_CLASSIFICATION_OUTPUTS:
        return _invalid_prediction("FORBIDDEN_ABSTENTION", raw_candidate)

    normalized_label = raw_candidate.lower()
    if normalized_label not in all_labels or normalized_label not in candidate_map:
        return _invalid_prediction("OUT_OF_CANDIDATE", raw_candidate)

    return {
        "prediction": candidate_map[normalized_label],
        "status": "VALID_CANDIDATE",
        "raw_candidate": raw_candidate,
    }


def parse_prediction(
    raw_response: str,
    labels: list[str],
    candidate_labels: list[str] | None = None,
) -> str | None:
    prediction = parse_prediction_result(
        raw_response, labels, candidate_labels=candidate_labels
    )["prediction"]
    return str(prediction) if prediction else None


def _highest_scoring_retrieved_label(
    retrieved_examples: list[dict],
    valid_labels: dict[str, str],
) -> tuple[str | None, float | None]:
    ranked: list[tuple[float, str]] = []
    for example in retrieved_examples:
        label = valid_labels.get(str(example.get("clause_type") or "").strip().lower())
        if not label:
            continue
        try:
            score = float(example.get("score"))
        except (TypeError, ValueError):
            score = float("-inf")
        ranked.append((score, label))
    if not ranked:
        return None, None
    score, label = max(ranked, key=lambda item: (item[0], item[1]))
    return label, score if score != float("-inf") else None


def _semantic_fallback_label(
    clause_text: str,
    labels: list[str],
    label_definitions: dict[str, str],
    extracted_features: dict[str, list[str]],
) -> str:
    clause = str(clause_text or "").lower()
    feature_text = " ".join(v for vs in extracted_features.values() for v in vs).lower()
    source_text = f"{clause} {feature_text}"
    source_tokens = set(re.findall(r"[a-z0-9]+", source_text))
    scored: list[tuple[float, str]] = []
    for label in labels:
        definition = str(label_definitions.get(label) or "")
        comparison = f"{label} {definition}".lower()
        definition_tokens = set(re.findall(r"[a-z0-9]+", comparison))
        overlap = len(source_tokens & definition_tokens)
        similarity = SequenceMatcher(None, clause, comparison).ratio()
        scored.append((overlap * 2.0 + similarity, label))
    return max(scored, key=lambda item: (item[0], item[1]))[1]


def _retrieve_with_retry(
    qdrant_client: QdrantClient,
    query_vector: list[float],
    top_k: int,
    progress_callback: ProgressCallback | None,
) -> tuple[list[dict], str, str | None]:
    first_error: Exception | None = None
    try:
        retrieved = retrieve_similar(qdrant_client, query_vector, top_k=top_k)
    except Exception as exc:
        retrieved = []
        first_error = exc
    if retrieved:
        return retrieved, "ok", None
    _emit(progress_callback, "search", "No usable retrieval candidates; retrying CUAD retrieval")
    retry_top_k = max(top_k + 1, top_k * 2)
    try:
        retried = retrieve_similar(qdrant_client, query_vector, top_k=retry_top_k)
    except Exception as exc:
        error = str(exc)
        if first_error:
            error = f"initial retrieval: {first_error}; retry: {exc}"
        return [], "error_after_retry", error
    if retried:
        return retried, "retried_success", None
    return [], "empty_after_retry", str(first_error) if first_error else None


def classify_clause(
    clause_text: str,
    query_vector: list[float],
    qdrant_client: QdrantClient,
    labels: list[str],
    label_definitions: dict[str, str],
    top_k: int = TOP_K,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    pre = advanced_preprocess(clause_text, for_llm=True)
    clause_text = pre.text
    _emit(progress_callback, "preprocess", "Advanced preprocessing complete", notes=pre.notes)

    _emit(progress_callback, "search", "Searching similar CUAD examples in Qdrant")
    valid_labels = _canonical_labels(labels)
    if not valid_labels:
        raise RuntimeError("The canonical CUAD label set is empty.")

    retrieved_examples, retrieval_status, retrieval_error = _retrieve_with_retry(
        qdrant_client, query_vector, top_k, progress_callback,
    )
    _emit(
        progress_callback, "search",
        f"Qdrant search complete ({len(retrieved_examples)} matches)",
        matches=len(retrieved_examples),
    )

    candidate_labels: list[str] = []
    for example in retrieved_examples:
        label = str(example.get("clause_type", "")).strip()
        canonical = valid_labels.get(label.lower())
        if canonical and canonical not in candidate_labels:
            candidate_labels.append(canonical)

    rule_hit = high_precision_rule_label(clause_text, allowed=None)
    if rule_hit:
        canonical_rule = valid_labels.get(rule_hit.lower())
        if canonical_rule and canonical_rule not in candidate_labels:
            candidate_labels.insert(0, canonical_rule)

    allowed_labels = candidate_labels or list(valid_labels.values())
    extracted_features = extract_legal_information(clause_text)
    prompt = build_prompt(
        clause_text=clause_text,
        examples=retrieved_examples,
        labels=labels,
        label_definitions={
            label: label_definitions[label]
            for label in allowed_labels
            if label in label_definitions
        },
        extracted_features=extracted_features,
        candidate_labels=allowed_labels,
    )
    _emit(
        progress_callback, "classification",
        f"Classification candidates: {', '.join(allowed_labels)}",
        candidates=allowed_labels,
    )
    _emit(progress_callback, "classification", f"Running classifier model={OLLAMA_MODEL}")

    raw_response = ""
    prediction_result: dict[str, str | None] = _invalid_prediction("MODEL_ERROR")
    for attempt in range(2):
        try:
            raw_response = call_ollama(prompt)
            prediction_result = parse_prediction_result(
                raw_response, labels, candidate_labels=allowed_labels,
            )
        except Exception as exc:
            prediction_result = _invalid_prediction("MODEL_ERROR", str(exc))
        if prediction_result["status"] == "VALID_CANDIDATE":
            break
        if attempt == 0:
            _emit(progress_callback, "classification", "Invalid label; retrying once")

    predicted_label = prediction_result.get("prediction")
    fallback_used = False
    fallback_reason = None
    classifier_source = "ollama_thinking"
    _, top_score = _highest_scoring_retrieved_label(retrieved_examples, valid_labels)
    rule_for_allowed = high_precision_rule_label(clause_text, allowed=allowed_labels)

    if rule_for_allowed and prediction_result.get("status") != "VALID_CANDIDATE":
        predicted_label = valid_labels.get(rule_for_allowed.lower(), rule_for_allowed)
        classifier_source = "high_precision_rule"
        fallback_used = True
        fallback_reason = "rule_override_on_model_fail"
        prediction_status = "VALID_CANDIDATE"
    elif predicted_label == NO_APPLICABLE_LABEL and rule_for_allowed:
        predicted_label = valid_labels.get(rule_for_allowed.lower(), rule_for_allowed)
        classifier_source = "high_precision_rule"
        fallback_used = True
        fallback_reason = "rule_override_on_abstention"
        prediction_status = "VALID_CANDIDATE"
    elif predicted_label not in valid_labels.values() and predicted_label != NO_APPLICABLE_LABEL:
        if rule_for_allowed:
            predicted_label = valid_labels.get(rule_for_allowed.lower(), rule_for_allowed)
            classifier_source = "high_precision_rule"
            fallback_used = True
            fallback_reason = "rule_override_invalid_model_label"
            prediction_status = "VALID_CANDIDATE"
        else:
            predicted_label = NO_APPLICABLE_LABEL
            classifier_source = "abstention"
            fallback_reason = str(prediction_result.get("status") or "invalid_model_response")
            prediction_status = "NO_APPLICABLE_LABEL"
    elif predicted_label == NO_APPLICABLE_LABEL or (
        predicted_label not in valid_labels.values()
    ):
        predicted_label = NO_APPLICABLE_LABEL
        classifier_source = "abstention"
        fallback_reason = str(prediction_result.get("status") or "invalid_model_response")
        prediction_status = "NO_APPLICABLE_LABEL"
    elif top_score is None or (
        top_score < MIN_RETRIEVAL_CONFIDENCE and classifier_source != "high_precision_rule"
    ):
        if rule_for_allowed:
            predicted_label = valid_labels.get(rule_for_allowed.lower(), rule_for_allowed)
            classifier_source = "high_precision_rule"
            fallback_used = True
            fallback_reason = "rule_override_low_retrieval"
            prediction_status = "VALID_CANDIDATE"
        else:
            predicted_label = NO_APPLICABLE_LABEL
            classifier_source = "low_retrieval_confidence"
            fallback_reason = f"top_retrieval_score_below_{MIN_RETRIEVAL_CONFIDENCE}"
            prediction_status = "NO_APPLICABLE_LABEL"
    else:
        prediction_status = "VALID_CANDIDATE"
        if rule_for_allowed and valid_labels.get(rule_for_allowed.lower()) == predicted_label:
            classifier_source = "model_plus_rule_agree"

    rule_agrees = bool(
        rule_for_allowed
        and predicted_label
        and valid_labels.get(str(rule_for_allowed).lower()) == predicted_label
    )
    classification_confidence = fuse_confidence(
        retrieval_score=top_score,
        rule_agrees=rule_agrees or classifier_source == "high_precision_rule",
        model_valid=prediction_status == "VALID_CANDIDATE",
        min_retrieval=MIN_RETRIEVAL_CONFIDENCE,
    )

    _emit(
        progress_callback, "classification",
        f"Classification selected: {predicted_label} ({classifier_source})",
        label=predicted_label, fallback_used=fallback_used,
    )

    return {
        "predicted_label": str(predicted_label),
        "raw_response": raw_response,
        "retrieved_examples": retrieved_examples,
        "retrieved_labels": [str(ex.get("clause_type") or "") for ex in retrieved_examples],
        "retrieved_scores": [round(float(ex.get("score", 0.0)), 4) for ex in retrieved_examples],
        "candidate_labels": allowed_labels,
        "prediction_status": prediction_status,
        "raw_prediction_candidate": prediction_result.get("raw_candidate"),
        "classification_source": classifier_source,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "classification_confidence": classification_confidence,
        "retrieval_status": retrieval_status,
        "retrieval_error": retrieval_error,
        "extracted_features": extracted_features,
        "preprocess_notes": pre.notes,
        "rule_hit": rule_hit,
        "prompt": prompt,
    }
