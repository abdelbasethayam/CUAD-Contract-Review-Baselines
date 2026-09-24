from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from hybrid_retriever import (
    BM25Index,
    HybridQueryClient,
    TrainingRecord,
    rrf_fuse,
    training_record_id,
    vector_search,
)


class FakePoint:
    def __init__(self, record_id: str, index: int):
        self.id = record_id
        self.score = 1.0 - index / 100.0
        self.payload = {
            "document_id": "doc",
            "clause_type": f"Label {index}",
            "clause_text": f"clause text {index}",
        }


class FakeQdrant:
    def __init__(self, count: int = 20):
        self.points = [FakePoint(str(index), index) for index in range(count)]
        self.last_kwargs = None

    def query_points(self, **kwargs):
        self.last_kwargs = kwargs
        return type("Response", (), {"points": self.points})()


class HybridRetrieverTests(unittest.TestCase):
    def test_bm25_uses_only_substantive_training_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "train.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["document_id", "clause_type", "clause_text", "is_metadata"],
                )
                writer.writeheader()
                writer.writerow({"document_id": "doc", "clause_type": "Document Name", "clause_text": "metadata", "is_metadata": "True"})
                writer.writerow({"document_id": "doc", "clause_type": "Insurance", "clause_text": "vehicle insurance coverage", "is_metadata": "False"})
            index = BM25Index.from_training_csv(path)
            self.assertEqual(len(index.records), 1)
            self.assertEqual(index.records[0].clause_type, "Insurance")

    def test_bm25_ranking_is_deterministic(self):
        records = [
            TrainingRecord(training_record_id("a", "A", 0), "a", "A", "alpha beta", 0),
            TrainingRecord(training_record_id("b", "B", 1), "b", "B", "alpha gamma", 1),
        ]
        index = BM25Index(records)
        self.assertEqual(index.search("alpha"), index.search("alpha"))

    def test_rrf_merges_duplicates_and_uses_one_based_ranks(self):
        vector = [
            {"record_id": "a", "document_id": "d", "clause_type": "A", "clause_text": "a", "score": 0.9, "rank": 1},
            {"record_id": "b", "document_id": "d", "clause_type": "B", "clause_text": "b", "score": 0.8, "rank": 2},
        ]
        bm25 = [
            {"record_id": "a", "document_id": "d", "clause_type": "A", "clause_text": "a", "score": 2.0, "rank": 1},
            {"record_id": "c", "document_id": "d", "clause_type": "C", "clause_text": "c", "score": 1.0, "rank": 2},
        ]
        result = rrf_fuse(vector, bm25, k=60, limit=5)
        by_id = {item["record_id"]: item for item in result}
        self.assertAlmostEqual(by_id["a"]["rrf_score"], 2 / 61)
        self.assertEqual(by_id["b"]["bm25_rank"], None)
        self.assertEqual(by_id["c"]["vector_rank"], None)
        self.assertEqual(result[0]["record_id"], "a")

    def test_rrf_is_sorted_and_limited_to_top_five(self):
        vector = [
            {"record_id": str(i), "document_id": "d", "clause_type": str(i), "clause_text": str(i), "score": 1.0, "rank": i}
            for i in range(1, 21)
        ]
        result = rrf_fuse(vector, [], k=60, limit=5)
        self.assertEqual(len(result), 5)
        self.assertEqual([item["hybrid_rank"] for item in result], [1, 2, 3, 4, 5])
        self.assertEqual(result[0]["record_id"], "1")

    def test_vector_search_uses_top_twenty_and_preserves_ranks(self):
        qdrant = FakeQdrant()
        result = vector_search(qdrant, [0.1, 0.2])
        self.assertEqual(len(result), 20)
        self.assertEqual(result[0]["rank"], 1)
        self.assertEqual(result[-1]["rank"], 20)
        self.assertEqual(qdrant.last_kwargs["collection_name"], "cuad_train")
        self.assertEqual(qdrant.last_kwargs["limit"], 20)

    def test_hybrid_adapter_returns_final_top_five_and_diagnostics(self):
        records = [
            TrainingRecord(
                training_record_id("doc", "Label 0", 0),
                "doc",
                "Label 0",
                "clause text 0",
                0,
            ),
        ]
        qdrant = FakeQdrant()
        client = HybridQueryClient(qdrant, BM25Index(records))
        client.set_query_text("clause text 0")
        response = client.query_points(query=[0.1, 0.2], limit=5)
        self.assertEqual(len(response.points), 5)
        self.assertEqual(len(client.last_diagnostics["vector_top20"]), 20)
        self.assertEqual(len(client.last_diagnostics["hybrid_top5"]), 5)


if __name__ == "__main__":
    unittest.main()
