"""
Qdrant retrieval for the RAG pipeline: given a query embedding, fetch the
top-K most similar TRAIN clauses from the cuad_train collection, excluding
contract-metadata rows (Document Name, Parties, dates, etc.).
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

_LOCAL_CLIENT: QdrantClient | None = None
_CLIENT_LOCK = Lock()


def make_qdrant_client() -> QdrantClient:
    global _LOCAL_CLIENT

    if QDRANT_URL:
        if QDRANT_API_KEY:
            return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        return QdrantClient(url=QDRANT_URL)

    # Qdrant local mode places a lock on its storage directory. Reusing one
    # client prevents concurrent requests from opening the same directory
    # through separate local-storage instances.
    with _CLIENT_LOCK:
        if _LOCAL_CLIENT is None:
            _LOCAL_CLIENT = QdrantClient(path=QDRANT_PATH)
        return _LOCAL_CLIENT


def retrieve_similar(
    qdrant_client: QdrantClient,
    query_vector: list[float],
    top_k: int = TOP_K,
) -> list[dict]:
    """Top-K most similar TRAIN clauses. The is_metadata filter is kept
    here (not just at embedding time) in case the collection was ever
    rebuilt with INCLUDE_METADATA_CLAUSES=true.
    """
    response = qdrant_client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=query_vector,
        limit=top_k,
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
    return [
        {
            "source_id": str(hit.id),
            "score": hit.score,
            "clause_type": hit.payload["clause_type"],
            "clause_text": hit.payload["clause_text"],
        }
        for hit in hits
    ]
