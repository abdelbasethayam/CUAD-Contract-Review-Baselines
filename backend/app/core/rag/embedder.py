"""Shared query/document embedding adapter.

Supported backends:
- cohere: Cohere Embed v3 (must match a Cohere-built Qdrant index).
- local_hashing: scikit-learn HashingVectorizer + cosine similarity. This is a
  deterministic local lexical-vector fallback, NOT a semantic pretrained model.
  Its Qdrant collections must be built with the same dimension/configuration.
"""
from __future__ import annotations

import time
from typing import Any

import cohere
from sklearn.feature_extraction.text import HashingVectorizer

from ..config import (
    COHERE_API_KEY,
    COHERE_MODEL,
    COHERE_EMBED_BATCH_SIZE,
    COHERE_MAX_RETRY_ATTEMPTS,
    COHERE_TIMEOUT_SECONDS,
    EMBEDDING_BACKEND,
    LOCAL_HASHING_DIM,
)


class LocalHashingEmbedder:
    """Deterministic stateless local vectorizer; vectors are L2 normalized."""

    def __init__(self, n_features: int = LOCAL_HASHING_DIM):
        if int(n_features) < 128:
            raise ValueError("LOCAL_HASHING_DIM must be >= 128.")
        self.n_features = int(n_features)
        self.vectorizer = HashingVectorizer(
            n_features=self.n_features,
            alternate_sign=False,
            norm="l2",
            ngram_range=(1, 2),
            lowercase=True,
            strip_accents="unicode",
            token_pattern=r"(?u)\b\w+\b",
        )

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        matrix = self.vectorizer.transform([str(text or "") for text in texts])
        return matrix.astype("float32").toarray().tolist()

    def close(self) -> None:
        return None


def make_cohere_client() -> Any:
    """Create the configured embedding client (legacy function name retained)."""
    backend = str(EMBEDDING_BACKEND or "cohere").strip().lower()
    if backend in {"local_hashing", "hashing", "offline"}:
        return LocalHashingEmbedder(LOCAL_HASHING_DIM)
    if backend != "cohere":
        raise ValueError(
            f"Unsupported EMBEDDING_BACKEND={backend!r}; use 'cohere' or 'local_hashing'."
        )
    if not COHERE_API_KEY:
        raise ValueError("COHERE_API_KEY is missing from .env")
    # Disable SDK retries; explicit bounded 429 handling below owns retry policy.
    return cohere.ClientV2(
        api_key=COHERE_API_KEY,
        timeout=COHERE_TIMEOUT_SECONDS,
        max_retries=0,
    )


def embed_texts(
    cohere_client: Any,
    texts: list[str],
    input_type: str,
) -> list[list[float]]:
    """Embed a batch in the active backend's configured vector space."""
    if isinstance(cohere_client, LocalHashingEmbedder):
        # Hashing is stateless and uses one transform for queries/documents.
        return cohere_client.encode(texts)

    all_embeddings: list[list[float]] = []
    for start in range(0, len(texts), COHERE_EMBED_BATCH_SIZE):
        batch = texts[start : start + COHERE_EMBED_BATCH_SIZE]
        response = None
        delay = 1
        max_attempts = max(1, min(COHERE_MAX_RETRY_ATTEMPTS, 5))

        for attempt in range(1, max_attempts + 1):
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
                if status_code != 429 or attempt == max_attempts:
                    raise
                print(
                    f"Rate limited by Cohere; retrying embedding batch in {delay}s "
                    f"(attempt {attempt}/{max_attempts})."
                )
                time.sleep(delay)
                delay = min(delay * 2, 8)

        if response is None:
            raise RuntimeError("Cohere did not return an embedding response.")
        all_embeddings.extend(response.embeddings.float)

    return all_embeddings


def embed_queries(cohere_client: Any, texts: list[str]) -> list[list[float]]:
    """Embed query text in the vector space configured for the active index."""
    return embed_texts(cohere_client, texts, input_type="search_query")


def embed_documents(cohere_client: Any, texts: list[str]) -> list[list[float]]:
    """Embed indexed documents in the vector space configured for the active index."""
    return embed_texts(cohere_client, texts, input_type="search_document")
