"""
Qdrant retrieval for the RAG pipeline: given a query embedding, fetch the
top-K most similar TRAIN clauses from the cuad_train collection, excluding
contract-metadata rows (Document Name, Parties, dates, etc.).

Also supports over-fetch + label diversification so the candidate set is not
dominated by a single clause_type.
"""

from __future__ import annotations

from threading import Lock

from qdrant_client import QdrantClient, models

from ..config import (
    QDRANT_URL,
    QDRANT_API_KEY,
    QDRANT_PATH,
    QDRANT_COLLECTION,
    TOP_K,
)
from .candidate_utils import diversify_by_label

_LOCAL_CLIENT: QdrantClient | None = None
_CLIENT_LOCK = Lock()


def make_qdrant_client() -> QdrantClient:
    global _LOCAL_CLIENT

    if QDRANT_URL:
        if QDRANT_API_KEY:
            return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        return QdrantClient(url=QDRANT_URL)

    with _CLIENT_LOCK:
        if _LOCAL_CLIENT is None:
            _LOCAL_CLIENT = QdrantClient(path=QDRANT_PATH)
        return _LOCAL_CLIENT


def retrieve_similar(
    qdrant_client: QdrantClient,
    query_vector: list[float],
    top_k: int = TOP_K,
    *,
    diversify: bool = True,
    fetch_multiplier: int = 3,
    max_per_label: int = 2,
) -> list[dict]:
    """Top-K similar TRAIN clauses with optional label diversification.

    Fetches up to top_k * fetch_multiplier hits, then keeps a diverse subset
    so prompts see multiple clause types when the neighborhood is mixed.
    """
    fetch_k = max(top_k, top_k * max(1, fetch_multiplier)) if diversify else top_k
    response = qdrant_client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=query_vector,
        limit=fetch_k,
        query_filter=models.Filter(
            must_not=[
                models.FieldCondition(
                    key="is_metadata",
                    match=models.MatchValue(value=True),
                )
            ]
        ),
    )
    hits = getattr(response, "points", response)
    results = [
        {
            "source_id": str(hit.id),
            "score": hit.score,
            "clause_type": hit.payload["clause_type"],
            "clause_text": hit.payload["clause_text"],
        }
        for hit in hits
    ]
    if diversify:
        return diversify_by_label(results, max_per_label=max_per_label, limit=top_k)
    return results[:top_k]
