"""Hybrid (dense + lexical) retrieval over the CUAD train pool.

Dense-only top-5 retrieval caps candidate-constrained Qwen: gold label is missing
from the shortlist ~1/6 of the time. Fusing dense similarity with TF-IDF via
reciprocal-rank fusion (RRF) raises kNN accuracy and shortlist label recall,
with no extra model or API call.

Index is in-memory (~7k clauses). Can be built from an existing Qdrant collection
that already holds dense vectors.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

RRF_K = 60


@dataclass(frozen=True)
class Hit:
    index: int
    label: str
    text: str
    document_id: str
    dense: float
    lexical: float
    rrf: float


class HybridIndex:
    def __init__(
        self,
        texts: list[str],
        labels: list[str],
        document_ids: list[str],
        dense: np.ndarray,
    ) -> None:
        if not (len(texts) == len(labels) == len(document_ids) == len(dense)):
            raise ValueError("texts, labels, document_ids and dense must align.")
        self.texts = texts
        self.labels = labels
        self.document_ids = np.asarray(document_ids)
        dense = np.asarray(dense, dtype=np.float32)
        norms = np.linalg.norm(dense, axis=1, keepdims=True)
        self.dense = dense / np.maximum(norms, 1e-9)
        self._tfidf = TfidfVectorizer(
            ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=200_000
        )
        self._lex = self._tfidf.fit_transform(texts)
        self.label_names = sorted(set(labels))
        counts = {name: 0 for name in self.label_names}
        for name in labels:
            counts[name] += 1
        total = float(len(labels))
        self.label_prior = {name: counts[name] / total for name in self.label_names}

    @classmethod
    def from_qdrant(
        cls,
        client,
        collection: str,
        cache_path: str | Path | None = None,
    ) -> "HybridIndex":
        """Build from an existing Qdrant collection (vectors + payload)."""
        if cache_path and Path(cache_path).exists():
            data = np.load(cache_path, allow_pickle=True)
            return cls(
                list(data["texts"]),
                list(data["labels"]),
                list(data["document_ids"]),
                data["dense"],
            )

        if client is None:
            raise ValueError("client is required when cache does not exist")

        texts: list[str] = []
        labels: list[str] = []
        document_ids: list[str] = []
        vectors: list[list[float]] = []

        offset = None
        while True:
            records, offset = client.scroll(
                collection_name=collection,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            for rec in records:
                payload = rec.payload or {}
                if payload.get("is_metadata"):
                    continue
                text = payload.get("clause_text") or payload.get("text") or ""
                label = payload.get("clause_type") or payload.get("label") or ""
                if not text or not label:
                    continue
                vec = rec.vector
                if isinstance(vec, dict):
                    vec = next(iter(vec.values()))
                texts.append(str(text))
                labels.append(str(label))
                document_ids.append(str(payload.get("document_id") or payload.get("doc_id") or ""))
                vectors.append(list(vec))
            if offset is None:
                break

        dense = np.asarray(vectors, dtype=np.float32)
        index = cls(texts, labels, document_ids, dense)
        if cache_path:
            path = Path(cache_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                path,
                texts=np.asarray(texts, dtype=object),
                labels=np.asarray(labels, dtype=object),
                document_ids=np.asarray(document_ids, dtype=object),
                dense=dense,
            )
        return index

    def search(
        self,
        query_text: str,
        query_vector,
        k: int = 30,
        exclude_document_id: str | None = None,
        exclude_document_ids: set[str] | None = None,
    ) -> list[Hit]:
        qv = np.asarray(query_vector, dtype=np.float32).reshape(-1)
        qv = qv / max(float(np.linalg.norm(qv)), 1e-9)
        dense_scores = self.dense @ qv

        q_lex = self._tfidf.transform([query_text])
        lex_scores = np.asarray(self._lex @ q_lex.T).reshape(-1)

        n = len(self.texts)
        dense_rank = np.argsort(-dense_scores)
        lex_rank = np.argsort(-lex_scores)
        dense_pos = np.empty(n, dtype=np.int32)
        lex_pos = np.empty(n, dtype=np.int32)
        dense_pos[dense_rank] = np.arange(n)
        lex_pos[lex_rank] = np.arange(n)
        rrf = 1.0 / (RRF_K + dense_pos) + 1.0 / (RRF_K + lex_pos)

        order = np.argsort(-rrf)
        hits: list[Hit] = []
        excluded = set(exclude_document_ids or ())
        if exclude_document_id:
            excluded.add(str(exclude_document_id))
        for idx in order:
            doc_id = str(self.document_ids[idx])
            if doc_id and doc_id in excluded:
                continue
            hits.append(
                Hit(
                    index=int(idx),
                    label=self.labels[idx],
                    text=self.texts[idx],
                    document_id=doc_id,
                    dense=float(dense_scores[idx]),
                    lexical=float(lex_scores[idx]),
                    rrf=float(rrf[idx]),
                )
            )
            if len(hits) >= k:
                break
        return hits

    @staticmethod
    def label_votes(hits: list[Hit]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for h in hits:
            scores[h.label] = scores.get(h.label, 0.0) + h.rrf
        total = sum(scores.values()) or 1.0
        return {k: v / total for k, v in scores.items()}

    def shortlist(self, hits: list[Hit], size: int = 8) -> list[str]:
        ordered: list[str] = []
        for h in hits:
            if h.label not in ordered:
                ordered.append(h.label)
            if len(ordered) >= size:
                break
        return ordered
