"""Candidate selection and confidence helpers for CUAD classification."""
from __future__ import annotations

from collections import defaultdict


def diversify_by_label(
    hits: list[dict],
    *,
    max_per_label: int = 2,
    limit: int | None = None,
) -> list[dict]:
    """Keep top scores while ensuring label diversity in the candidate pool.

    Retrieval often returns many near-duplicates of the same clause_type.
    Diversifying improves the prompt candidate set and Recall@K for rare labels.
    """
    counts: dict[str, int] = defaultdict(int)
    selected: list[dict] = []
    overflow: list[dict] = []

    for hit in sorted(hits, key=lambda h: float(h.get("score") or 0.0), reverse=True):
        label = str(hit.get("clause_type") or "").strip().lower()
        if not label:
            continue
        if counts[label] < max_per_label:
            selected.append(hit)
            counts[label] += 1
        else:
            overflow.append(hit)

    # Fill remaining slots with next-best scores if we undershot limit
    if limit is not None and len(selected) < limit:
        for hit in overflow:
            selected.append(hit)
            if len(selected) >= limit:
                break

    if limit is not None:
        return selected[:limit]
    return selected


def unique_labels_in_order(hits: list[dict], valid: dict[str, str]) -> list[str]:
    """Ordered unique canonical labels from retrieval hits."""
    out: list[str] = []
    for hit in hits:
        raw = str(hit.get("clause_type") or "").strip()
        canon = valid.get(raw.lower())
        if canon and canon not in out:
            out.append(canon)
    return out


def fuse_confidence(
    *,
    retrieval_score: float | None,
    rule_agrees: bool,
    model_valid: bool,
    min_retrieval: float,
) -> float:
    """Simple calibrated-ish confidence in [0, 1] for logging / UI."""
    base = 0.0
    if retrieval_score is not None:
        # Use the actual retrieval score as the conservative base; do not add
        # an artificial confidence floor to a weak match when the model abstains.
        base = max(0.0, min(1.0, float(retrieval_score)))
    if model_valid:
        base = max(base, 0.45)
    if rule_agrees and model_valid:
        base = min(1.0, base + 0.20)
    elif rule_agrees:
        base = max(base, 0.70)
    return round(float(base), 4)
