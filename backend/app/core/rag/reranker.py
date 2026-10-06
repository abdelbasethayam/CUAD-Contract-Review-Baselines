"""Optional local cross-encoder reranking for CUAD retrieval."""
from __future__ import annotations

from functools import lru_cache

from .hybrid_retrieval import Hit


@lru_cache(maxsize=4)
def _load_model(model_name: str):
    from sentence_transformers import CrossEncoder
    return CrossEncoder(model_name)


def rerank_hits(
    query_text: str,
    hits: list[Hit],
    *,
    model_name: str = "BAAI/bge-reranker-v2-m3",
    top_k: int | None = None,
    batch_size: int = 16,
) -> list[Hit]:
    """Rerank retrieved hits with a local cross-encoder."""
    if not hits:
        return []
    model = _load_model(model_name)
    pairs = [(query_text, hit.text) for hit in hits]
    scores = model.predict(
        pairs,
        batch_size=batch_size,
        show_progress_bar=False,
    )
    ranked = sorted(
        ((float(score), hit) for score, hit in zip(scores, hits)),
        key=lambda item: item[0],
        reverse=True,
    )
    selected = [hit for _, hit in ranked]
    return selected[:top_k] if top_k else selected


__all__ = ["rerank_hits"]
