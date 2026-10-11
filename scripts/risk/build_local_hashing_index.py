#!/usr/bin/env python3
"""Build a strictly train-only local hashing-vector Qdrant collection."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from qdrant_client import QdrantClient, models
from app.core.config import LOCAL_HASHING_DIM, QDRANT_PATH, QDRANT_COLLECTION
from app.core.rag.embedder import LocalHashingEmbedder

TRAIN_CSV = ROOT / "data" / "splits" / "train" / "master_clauses_train.csv"
TEST_CSV = ROOT / "data" / "splits" / "test" / "master_clauses_test.csv"
MANIFEST = ROOT / "data" / "risk" / "results" / "local_hashing_cuad_index_manifest.json"
DEFAULT_COLLECTION = "cuad_train_hashing"
EXCLUDED = {
    "Document Name", "Parties", "Agreement Date", "Effective Date", "Expiration Date"
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_records(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def is_true(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def load_train_rows() -> list[dict]:
    rows = []
    for index, row in enumerate(read_records(TRAIN_CSV), start=2):
        label = str(row.get("clause_type") or "").strip()
        text = str(row.get("clause_text_clean") or "").strip() or str(row.get("clause_text") or "").strip()
        if not text or not label or is_true(row.get("is_metadata")) or label in EXCLUDED:
            continue
        rows.append({
            "document_id": str(row.get("document_id") or "").strip(),
            "clause_type": label,
            "clause_text": text,
            "source_row_index": index,
            "is_metadata": False,
        })
    return rows


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--batch-size", type=int, default=96)
    args = parser.parse_args()

    if not TRAIN_CSV.is_file() or not TEST_CSV.is_file():
        raise SystemExit("Expected prepared train/test CSV files were not found.")
    train_rows = load_train_rows()
    if not train_rows:
        raise SystemExit("No eligible training rows found.")
    train_docs = {x["document_id"] for x in train_rows if x["document_id"]}
    test_docs = {
        str(x.get("document_id") or "").strip()
        for x in read_records(TEST_CSV)
        if str(x.get("document_id") or "").strip()
    }
    overlap = train_docs & test_docs
    if overlap:
        raise SystemExit(f"Train/test contract overlap detected: {len(overlap)} contracts.")

    root_path = Path(QDRANT_PATH)
    if not root_path.is_absolute():
        root_path = ROOT / root_path
    client = QdrantClient(path=str(root_path))
    try:
        if client.collection_exists(args.collection):
            client.delete_collection(args.collection)
        client.create_collection(
            collection_name=args.collection,
            vectors_config=models.VectorParams(
                size=int(LOCAL_HASHING_DIM), distance=models.Distance.COSINE
            ),
        )
        embedder = LocalHashingEmbedder(int(LOCAL_HASHING_DIM))
        total = len(train_rows)
        inserted = 0
        batch_size = max(1, int(args.batch_size))
        for start in range(0, total, batch_size):
            batch = train_rows[start : start + batch_size]
            vectors = embedder.encode([item["clause_text"] for item in batch])
            points = []
            for offset, (item, vector) in enumerate(zip(batch, vectors), start=start):
                stable_key = f"{item['document_id']}::{item['source_row_index']}::{item['clause_type']}"
                point_id = str(uuid5(NAMESPACE_URL, stable_key))
                points.append(models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        **item,
                        "is_metadata": False,
                        "embedding_backend": "local_hashing",
                        "embedding_dimension": int(LOCAL_HASHING_DIM),
                        "split": "train",
                    },
                ))
            client.upsert(collection_name=args.collection, points=points, wait=True)
            inserted += len(points)
            print(f"indexed {inserted}/{total}", flush=True)

        info = client.get_collection(args.collection)
        points_count = int(info.points_count or 0)
        if points_count != len(train_rows):
            raise SystemExit(f"Collection count mismatch: expected {len(train_rows)}, got {points_count}")

        manifest = {
            "schema_version": 1,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "PASS",
            "collection": args.collection,
            "embedding": {
                "backend": "sklearn.HashingVectorizer",
                "dimension": int(LOCAL_HASHING_DIM),
                "ngram_range": [1, 2],
                "alternate_sign": False,
                "normalization": "l2",
                "note": "Deterministic local lexical-vector baseline; not a pretrained semantic embedding model.",
            },
            "source": {
                "train_csv": str(TRAIN_CSV.relative_to(ROOT)),
                "train_csv_sha256": sha256(TRAIN_CSV),
                "test_csv": str(TEST_CSV.relative_to(ROOT)),
                "test_csv_sha256": sha256(TEST_CSV),
            },
            "counts": {
                "eligible_train_rows": len(train_rows),
                "indexed_points": points_count,
                "train_contracts": len(train_docs),
                "test_contracts": len(test_docs),
                "train_test_contract_overlap": len(overlap),
            },
            "leakage_policy": "Only eligible rows from data/splits/train/master_clauses_train.csv are indexed. No test rows or test labels are inserted.",
        }
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
