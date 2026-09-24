"""Deterministic compression for retrieval evidence passed downstream."""

from __future__ import annotations

import re
from difflib import SequenceMatcher


def _normalized_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _score(item: dict, key: str = "score") -> float:
    try:
        return float(item.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _source_id(item: dict) -> str | None:
    for key in ("source_id", "document_id", "id", "point_id"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def compress_cuad_evidence(
    *,
    clause_id: int | None,
    final_label: str | None,
    contract_text: str,
    retrieved_examples: list[dict] | None,
    max_items: int = 2,
) -> list[dict]:
    """Keep at most two exact, unique CUAD examples without changing retrieval."""
    del clause_id, contract_text
    max_items = min(max(0, max_items), 2)
    target = str(final_label or "").casefold()
    examples = sorted(
        list(retrieved_examples or []),
        key=lambda item: (
            1 if target and str(item.get("clause_type") or item.get("label") or "").casefold() == target else 0,
            _score(item),
        ),
        reverse=True,
    )
    selected: list[dict] = []
    seen_sources: set[str] = set()
    seen_text: set[str] = set()
    for item in examples:
        quote = item.get("clause_text") or item.get("quote")
        normalized = _normalized_text(quote)
        if not normalized or normalized in seen_text:
            continue
        source_id = _source_id(item)
        if source_id and source_id in seen_sources:
            continue
        if any(
            SequenceMatcher(None, normalized, _normalized_text(old["quote"])).ratio() >= 0.92
            for old in selected
        ):
            continue
        label = item.get("clause_type") or item.get("label")
        compressed = {
            "label": label,
            "score": _score(item),
            "quote": quote,
        }
        if source_id:
            compressed["source_id"] = source_id
        selected.append(compressed)
        seen_text.add(normalized)
        if source_id:
            seen_sources.add(source_id)
        if len(selected) >= max_items:
            break
    return selected


def compress_legal_guidance(guidance: list[dict], max_items: int = 6) -> list[dict]:
    """Remove repeated guidance while preserving original metadata and text."""
    ordered = sorted(guidance or [], key=lambda item: _score(item, "relevance_score"), reverse=True)
    selected: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()
    for item in ordered:
        normalized = _normalized_text(item.get("retrieved_text"))
        key = (_normalized_text(item.get("source_url")), _normalized_text(item.get("title")))
        if not normalized or key in seen_keys:
            continue
        if any(
            SequenceMatcher(None, normalized, _normalized_text(old.get("retrieved_text"))).ratio() >= 0.92
            for old in selected
        ):
            continue
        selected.append(item)
        seen_keys.add(key)
        if len(selected) >= max_items:
            break
    return selected
