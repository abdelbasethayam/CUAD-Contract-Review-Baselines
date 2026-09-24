"""
Cohere embedding client for the RAG pipeline.

Embeds query text (clauses extracted from an uploaded contract) with the
same Cohere model that built the Qdrant index in embed_train.py.
IMPORTANT: COHERE_MODEL in config must match whatever model actually built
train_embeddings.json, or retrieval similarity is meaningless (query and
stored vectors would live in different embedding spaces).
"""

from __future__ import annotations

import time

import cohere

from ..config import (
    COHERE_API_KEY,
    COHERE_MODEL,
    COHERE_EMBED_BATCH_SIZE,
    COHERE_MAX_RETRY_ATTEMPTS,
)


def make_cohere_client() -> cohere.ClientV2:
    if not COHERE_API_KEY:
        raise ValueError("COHERE_API_KEY is missing from .env")
    return cohere.ClientV2(api_key=COHERE_API_KEY)


def embed_texts(
    cohere_client: cohere.ClientV2,
    texts: list[str],
    input_type: str,
) -> list[list[float]]:
    """Batch-embed texts with the configured Cohere model and retry policy."""
    all_embeddings: list[list[float]] = []

    for start in range(0, len(texts), COHERE_EMBED_BATCH_SIZE):
        batch = texts[start : start + COHERE_EMBED_BATCH_SIZE]
        response = None
        delay = 5

        for attempt in range(1, COHERE_MAX_RETRY_ATTEMPTS + 1):
            try:
                response = cohere_client.embed(
                    model=COHERE_MODEL,
                    input_type=input_type,
                    texts=batch,
                    embedding_types=["float"],
                )
                break
            except Exception as exc:
                status_code = getattr(exc, "status_code", None)
                if status_code != 429 or attempt == COHERE_MAX_RETRY_ATTEMPTS:
                    raise
                print(
                    f"Rate limited by Cohere; retrying query batch in {delay}s "
                    f"(attempt {attempt}/{COHERE_MAX_RETRY_ATTEMPTS})."
                )
                time.sleep(delay)
                delay *= 2

        if response is None:
            raise RuntimeError("Cohere did not return an embedding response.")

        all_embeddings.extend(response.embeddings.float)

    return all_embeddings


def embed_queries(cohere_client: cohere.ClientV2, texts: list[str]) -> list[list[float]]:
    """Batch-embed query texts (clauses), with retry/backoff on Cohere 429s
    so a long contract with many clauses doesn't die on a rate limit.
    """
    return embed_texts(cohere_client, texts, input_type="search_query")


def embed_documents(cohere_client: cohere.ClientV2, texts: list[str]) -> list[list[float]]:
    """Batch-embed stored knowledge documents into the same embedding space."""
    return embed_texts(cohere_client, texts, input_type="search_document")
