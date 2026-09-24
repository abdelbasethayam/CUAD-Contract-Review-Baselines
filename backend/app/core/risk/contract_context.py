"""Retrieve semantically related clauses from the currently uploaded contract."""

from __future__ import annotations

import math


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def retrieve_related_contract_context(
    *,
    target_clause_index: int,
    target_vector: list[float],
    clauses: list[dict],
    top_k: int = 5,
) -> list[dict]:
    """Return top-K related clauses from the same uploaded contract.

    ``target_vector`` is the Cohere embedding of the actual target clause.
    The current clause is excluded by stable clause index, so no separate
    corpus or Qdrant collection is required for contract-context retrieval.
    """
    ranked: list[dict] = []
    for item in clauses:
        clause_index = int(item.get("clause_index", -1))
        if clause_index == target_clause_index:
            continue
        text = str(item.get("clause_text") or "").strip()
        vector = item.get("vector") or []
        if not text or not vector:
            continue
        ranked.append(
            {
                "chunk_id": f"contract-clause-{clause_index}",
                "clause_index": clause_index,
                "clause_text": text,
                "similarity_score": round(
                    _cosine_similarity(target_vector, vector), 4
                ),
            }
        )

    ranked.sort(key=lambda item: item["similarity_score"], reverse=True)
    return ranked[: max(0, int(top_k))]
