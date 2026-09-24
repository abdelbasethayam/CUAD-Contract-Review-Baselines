from __future__ import annotations

import csv
import math
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from qdrant_client import models


VECTOR_DEPTH = 20
BM25_DEPTH = 20
RRF_K = 60
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
METADATA_LABELS = {
    "Document Name",
    "Parties",
    "Agreement Date",
    "Effective Date",
    "Expiration Date",
}


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(str(text or "").lower())


def is_metadata(value: str) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes"}


def training_record_id(document_id: str, clause_type: str, source_index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}::{clause_type}::{source_index}"))


@dataclass(frozen=True)
class TrainingRecord:
    record_id: str
    document_id: str
    clause_type: str
    clause_text: str
    source_index: int


class BM25Index:
    """Deterministic BM25 index over substantive training clauses only."""

    def __init__(self, records: list[TrainingRecord], k1: float = 1.5, b: float = 0.75):
        self.records = list(records)
        self.k1 = k1
        self.b = b
        self.tokens = [tokenize(record.clause_text) for record in self.records]
        self.lengths = [len(tokens) for tokens in self.tokens]
        self.average_length = sum(self.lengths) / len(self.lengths) if self.lengths else 0.0
        self.postings: dict[str, dict[int, int]] = {}
        for index, tokens in enumerate(self.tokens):
            counts: dict[str, int] = {}
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1
            for token, count in counts.items():
                self.postings.setdefault(token, {})[index] = count

    @classmethod
    def from_training_csv(cls, path: Path, k1: float = 1.5, b: float = 0.75) -> "BM25Index":
        records: list[TrainingRecord] = []
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            for csv_row, row in enumerate(csv.DictReader(handle), start=2):
                if is_metadata(row.get("is_metadata")):
                    continue
                clause_type = str(row.get("clause_type", "")).strip()
                clause_text = str(row.get("clause_text", "")).strip()
                document_id = str(row.get("document_id", "")).strip()
                if not clause_type or not clause_text or clause_type in METADATA_LABELS:
                    continue
                source_index = csv_row - 2
                records.append(
                    TrainingRecord(
                        record_id=training_record_id(document_id, clause_type, source_index),
                        document_id=document_id,
                        clause_type=clause_type,
                        clause_text=clause_text,
                        source_index=source_index,
                    )
                )
        return cls(records, k1=k1, b=b)

    def search(self, query: str, limit: int = BM25_DEPTH) -> list[dict]:
        query_terms = set(tokenize(query))
        document_count = len(self.records)
        scores: dict[int, float] = {}
        for term in query_terms:
            posting = self.postings.get(term)
            if not posting:
                continue
            document_frequency = len(posting)
            idf = math.log(1.0 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5))
            for index, term_frequency in posting.items():
                length_factor = 1.0 - self.b + self.b * self.lengths[index] / self.average_length
                denominator = term_frequency + self.k1 * length_factor
                scores[index] = scores.get(index, 0.0) + idf * (
                    term_frequency * (self.k1 + 1.0) / denominator
                )

        ranked = sorted(
            scores.items(),
            key=lambda item: (-item[1], self.records[item[0]].record_id),
        )[:limit]
        return [
            {
                "record_id": self.records[index].record_id,
                "document_id": self.records[index].document_id,
                "clause_type": self.records[index].clause_type,
                "clause_text": self.records[index].clause_text,
                "score": score,
                "rank": rank,
                "source_index": self.records[index].source_index,
            }
            for rank, (index, score) in enumerate(ranked, start=1)
        ]


def vector_search(qdrant_client, query_vector: list[float], limit: int = VECTOR_DEPTH) -> list[dict]:
    response = qdrant_client.query_points(
        collection_name="cuad_train",
        query=query_vector,
        limit=limit,
        query_filter=models.Filter(
            must_not=[
                models.FieldCondition(
                    key="is_metadata",
                    match=models.MatchValue(value=True),
                )
            ]
        ),
    )
    points = getattr(response, "points", response)
    results = []
    for rank, point in enumerate(points, start=1):
        payload = point.payload
        results.append(
            {
                "record_id": str(point.id),
                "document_id": payload.get("document_id"),
                "clause_type": payload["clause_type"],
                "clause_text": payload["clause_text"],
                "score": float(point.score),
                "rank": rank,
            }
        )
    return results


def rrf_fuse(vector_results: list[dict], bm25_results: list[dict], k: int = RRF_K, limit: int = 5) -> list[dict]:
    merged: dict[str, dict] = {}

    def add(results: list[dict], source: str) -> None:
        for result in results:
            record_id = str(result["record_id"])
            item = merged.setdefault(
                record_id,
                {
                    "record_id": record_id,
                    "document_id": result.get("document_id"),
                    "clause_type": result["clause_type"],
                    "clause_text": result["clause_text"],
                    "vector_rank": None,
                    "bm25_rank": None,
                    "vector_score": None,
                    "bm25_score": None,
                    "rrf_score": 0.0,
                },
            )
            rank = int(result["rank"])
            item[f"{source}_rank"] = rank
            item[f"{source}_score"] = float(result["score"])
            item["rrf_score"] += 1.0 / (k + rank)

    add(vector_results, "vector")
    add(bm25_results, "bm25")
    ranked = sorted(
        merged.values(),
        key=lambda item: (
            -item["rrf_score"],
            min(
                rank for rank in (item["vector_rank"], item["bm25_rank"]) if rank is not None
            ),
            item["record_id"],
        ),
    )
    for rank, item in enumerate(ranked, start=1):
        item["hybrid_rank"] = rank
    return ranked[:limit]


class HybridQueryClient:
    """Adapter consumed by the unchanged production retrieve_similar()."""

    def __init__(self, qdrant_client, bm25_index: BM25Index):
        self.qdrant_client = qdrant_client
        self.bm25_index = bm25_index
        self.query_text = ""
        self.last_diagnostics: dict = {}

    def set_query_text(self, query_text: str) -> None:
        self.query_text = query_text

    def query_points(self, **kwargs):
        vector_results = vector_search(self.qdrant_client, kwargs["query"], limit=VECTOR_DEPTH)
        bm25_results = self.bm25_index.search(self.query_text, limit=BM25_DEPTH)
        hybrid_results = rrf_fuse(vector_results, bm25_results, k=RRF_K, limit=kwargs.get("limit", 5))
        self.last_diagnostics = {
            "vector_top20": vector_results,
            "bm25_top20": bm25_results,
            "hybrid_ranked": rrf_fuse(vector_results, bm25_results, k=RRF_K, limit=len(vector_results) + len(bm25_results)),
            "hybrid_top5": hybrid_results,
        }
        points = [
            SimpleNamespace(
                id=result["record_id"],
                score=result["rrf_score"],
                payload={
                    "document_id": result.get("document_id"),
                    "clause_type": result["clause_type"],
                    "clause_text": result["clause_text"],
                },
            )
            for result in hybrid_results
        ]
        return SimpleNamespace(points=points)


def rank_for(label: str, results: list[dict], rank_key: str = "rank") -> int | None:
    for result in results:
        if result.get("clause_type") == label:
            return int(result[rank_key])
    return None
