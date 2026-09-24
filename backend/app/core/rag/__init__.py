"""
RAG building blocks. This package holds the domain logic only --
embedding, retrieval, generation, and text segmentation. Orchestrating
them into a full contract-classification pipeline lives one layer up, in
services/rag_service.py.
"""

from __future__ import annotations

from .embedder import make_cohere_client, embed_queries
from .retriever import make_qdrant_client, retrieve_similar
from .generator import classify_clause
from .prompt import build_prompt, load_label_definitions, DEFAULT_LABEL_DEFINITIONS
from .segmenter import extract_text, split_into_clauses
from .clause_segmenter import ClauseNode, segment_document

__all__ = [
    "make_cohere_client",
    "embed_queries",
    "make_qdrant_client",
    "retrieve_similar",
    "classify_clause",
    "build_prompt",
    "load_label_definitions",
    "DEFAULT_LABEL_DEFINITIONS",
    "extract_text",
    "split_into_clauses",
    "ClauseNode",
    "segment_document",
]
