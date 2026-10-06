"""Bridge: hybrid retrieval + letter-logprob Qwen path.

Use alongside the existing classify_clause() pipeline:

  from backend.app.core.rag.hybrid_path import classify_with_hybrid_qwen
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import (
    HYBRID_COLLECTION,
    HYBRID_INDEX_CACHE,
    HYBRID_K,
    HYBRID_SHORTLIST,
    HYBRID_RERANK,
    HYBRID_RERANKER_MODEL,
    HYBRID_RERANK_TOP_K,
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_URL,
    QDRANT_COLLECTION,
    QDRANT_PATH,
)
from .hybrid_retrieval import HybridIndex
from .qwen_classifier import OllamaSettings, classify_clause_hybrid, load_fusion_params

_INDEX: HybridIndex | None = None


def get_hybrid_index(
    client=None,
    *,
    collection: str | None = None,
    cache_path: str | Path | None = None,
    force_reload: bool = False,
) -> HybridIndex:
    global _INDEX
    if _INDEX is not None and not force_reload:
        return _INDEX
    coll = collection or HYBRID_COLLECTION or QDRANT_COLLECTION
    cache = cache_path or HYBRID_INDEX_CACHE
    if client is None:
        from qdrant_client import QdrantClient

        client = QdrantClient(path=str(QDRANT_PATH))
    _INDEX = HybridIndex.from_qdrant(client, coll, cache_path=cache)
    return _INDEX


def classify_with_hybrid_qwen(
    clause_text: str,
    query_vector,
    *,
    definitions: dict[str, str],
    index: HybridIndex | None = None,
    alpha: float | None = None,
    beta: float | None = None,
    fusion_params_path: str | Path | None = None,
    permutations: int = 1,
) -> dict[str, Any]:
    """Hybrid shortlist + Qwen letter probs + score fusion."""
    idx = index or get_hybrid_index()
    if alpha is None or beta is None:
        a, b = load_fusion_params(
            fusion_params_path or "output/eval/qwen_improved/hybrid-rerank-1_fusion_params.json"
        )
        alpha = alpha if alpha is not None else a
        beta = beta if beta is not None else b
    cfg = OllamaSettings(
        url=OLLAMA_URL,
        model=OLLAMA_MODEL,
        num_ctx=OLLAMA_NUM_CTX,
    )
    return classify_clause_hybrid(
        clause_text,
        query_vector,
        idx,
        definitions,
        cfg=cfg,
        alpha=float(alpha),
        beta=float(beta),
        k=HYBRID_K,
        shortlist_size=HYBRID_SHORTLIST,
        permutations=permutations,
        examples_per_candidate=1,
        rerank=HYBRID_RERANK,
        reranker_model=HYBRID_RERANKER_MODEL,
        rerank_top_k=HYBRID_RERANK_TOP_K,
    )
