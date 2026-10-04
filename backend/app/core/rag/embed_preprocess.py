"""Preprocess text before embedding so queries match indexed train style."""
from __future__ import annotations

from .advanced_preprocess import advanced_preprocess


def text_for_embedding(raw: str) -> str:
    """Normalize + lowercase for dense retrieval queries."""
    return advanced_preprocess(raw, for_llm=False).for_embedding


def texts_for_embedding(raw_texts: list[str]) -> list[str]:
    return [text_for_embedding(t) for t in raw_texts]
