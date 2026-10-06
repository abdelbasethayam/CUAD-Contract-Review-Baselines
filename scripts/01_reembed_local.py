"""
Step 1: Re-embed full Train and Test datasets with sentence-transformers/all-mpnet-base-v2 (768-dim).

- Re-indexes 7,004 non-metadata train clauses into Qdrant collection 'cuad_train_mpnet'.
- Embeds 1,679 non-metadata test clauses and saves to output/embeddings/test_1495_mpnet.npy.
- Creates test metadata index output/embeddings/test_1495_metadata.json.
"""

import csv
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
EMBEDDING_DIM = 768
BATCH_SIZE = 64
COLLECTION_NAME = "cuad_train_mpnet"

EXCLUDED_METADATA_LABELS = {
    "Document Name",
    "Parties",
    "Agreement Date",
    "Effective Date",
    "Expiration Date",
}


def load_clean_clauses(csv_path: Path) -> list[dict]:
    clauses = []
    with csv_path.open("r", encoding="utf-8-sig") as f:
        for idx, row in enumerate(csv.DictReader(f), start=2):
            label = str(row.get("clause_type", "")).strip()
            clean_text = str(row.get("clause_text_clean", "") or "").strip()
            text = clean_text or str(row.get("clause_text", "")).strip()
            is_meta = str(row.get("is_metadata", "")).lower() == "true"
            doc_id = str(row.get("document_id", "")).strip()
            answer = str(row.get("answer", "")).strip()

            if label and text and not is_meta and label not in EXCLUDED_METADATA_LABELS:
                clauses.append({
                    "original_row_index": idx,
                    "clause_id": f"clause-{idx}",
                    "document_id": doc_id,
                    "clause_type": label,
                    "clause_text": text,
                    "clause_text_source": "clause_text_clean" if clean_text else "clause_text",
                    "answer": answer,
                })
    return clauses


def main():
    root = Path(__file__).resolve().parents[1]
    train_csv = root / "data" / "splits" / "train" / "master_clauses_train.csv"
    test_csv = root / "data" / "splits" / "test" / "master_clauses_test.csv"
    out_dir = root / "output" / "embeddings"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Delete stale cache if present
    stale_cache = out_dir / "eval_sample_cache.json"
    if stale_cache.exists():
        stale_cache.unlink()
        print(f"Deleted stale cache: {stale_cache}")

    print(f"Loading embedding model: {MODEL_NAME}...")
    start_time = time.time()
    model = SentenceTransformer(MODEL_NAME)
    print(f"Model loaded in {time.time() - start_time:.2f} seconds.")

    # 2. Re-index Training Clauses into Qdrant 'cuad_train_mpnet'
    print(f"Loading train clauses from {train_csv}...")
    train_clauses = load_clean_clauses(train_csv)
    print(f"Loaded {len(train_clauses)} non-metadata training clauses.")

    qdrant_db_path = root / "data" / "qdrant_local"
    qdrant_db_path.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(qdrant_db_path))

    # Recreate collection
    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)
        print(f"Replaced existing Qdrant collection: '{COLLECTION_NAME}'")

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )

    print("Embedding training clauses and indexing in Qdrant...")
    train_texts = [item["clause_text"] for item in train_clauses]
    train_embeddings = model.encode(
        train_texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    points = [
        PointStruct(
            id=idx,
            vector=vector.tolist(),
            payload={
                "document_id": item["document_id"],
                "clause_type": item["clause_type"],
                "clause_text": item["clause_text"],
                "original_row_index": item["original_row_index"],
            },
        )
        for idx, (item, vector) in enumerate(zip(train_clauses, train_embeddings), start=1)
    ]

    # Batch upsert points
    for batch_start in range(0, len(points), 500):
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points[batch_start : batch_start + 500],
        )
    print(f"Successfully indexed {len(points)} points into '{COLLECTION_NAME}'.")

    # 3. Embed Test Clauses
    print(f"Loading test clauses from {test_csv}...")
    test_clauses = load_clean_clauses(test_csv)
    print(f"Loaded {len(test_clauses)} non-metadata test clauses.")

    test_texts = [item["clause_text"] for item in test_clauses]
    print("Embedding test clauses...")
    test_embeddings = model.encode(
        test_texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    npy_path = out_dir / "test_1495_mpnet.npy"
    meta_path = out_dir / "test_1495_metadata.json"

    np.save(npy_path, test_embeddings)
    meta_path.write_text(
        json.dumps(
            {
                "embedding_model": MODEL_NAME,
                "embedding_dimension": EMBEDDING_DIM,
                "qdrant_collection": COLLECTION_NAME,
                "test_count": len(test_clauses),
                "clauses": test_clauses,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"Saved test embeddings to {npy_path} (shape: {test_embeddings.shape})")
    print(f"Saved test metadata to {meta_path}")


if __name__ == "__main__":
    main()
