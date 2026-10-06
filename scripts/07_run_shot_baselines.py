#!/usr/bin/env python3
"""Held-out zero-/one-/five-shot Qwen baselines.

These are deliberately separate from the candidate-constrained hybrid pipeline:
- zero-shot = all 36 substantive labels, no examples
- random-1/random-5 = full label set + random demonstrations
- retrieval-1/retrieval-5 = dense top-k demonstrations + retrieved candidate labels

All runs use the untouched 100-contract / 1,679-clause test split.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, f1_score
from qdrant_client import QdrantClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core.config import (
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_URL,
    QDRANT_COLLECTION,
    QDRANT_PATH,
    load_labels,
)
from backend.app.core.rag.generator import call_ollama, extract_legal_information, parse_prediction
from backend.app.core.rag.prompt import build_prompt, load_label_definitions
from backend.app.core.rag.eval_data import EXCLUDED_METADATA, load_clauses

TEST_CSV = ROOT / "data" / "splits" / "test" / "master_clauses_test.csv"
EMBED_NPY = ROOT / "output" / "embeddings" / "test_1495_mpnet.npy"
EMBED_META = ROOT / "output" / "embeddings" / "test_1495_metadata.json"
OUT_DIR = ROOT / "output" / "eval" / "shot_baselines"
SEED = 42


def load_dense_test() -> tuple[list[dict], np.ndarray]:
    if not EMBED_NPY.exists() or not EMBED_META.exists():
        raise SystemExit(
            "Missing test embeddings. Run scripts/01_reembed_local.py first."
        )
    meta = json.loads(EMBED_META.read_text(encoding="utf-8"))
    vectors = np.load(EMBED_NPY)
    clauses = meta["clauses"]
    if len(clauses) != len(vectors):
        raise AssertionError("Test metadata/vector count mismatch.")
    return clauses, vectors


def load_train_pool() -> list[dict]:
    path = ROOT / "data" / "splits" / "train" / "master_clauses_train.csv"
    df = load_clauses(path)
    return df.to_dict("records")


def random_demos(pool: list[dict], k: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    return rng.sample(pool, min(k, len(pool)))


def dense_hits(client: QdrantClient, vector: np.ndarray, k: int) -> list[dict]:
    response = client.query_points(
        collection_name="cuad_train_mpnet",
        query=vector.tolist(),
        limit=k,
    )
    points = getattr(response, "points", response)
    return [
        {
            "clause_type": str(p.payload["clause_type"]),
            "clause_text": str(p.payload["clause_text"]),
            "score": float(p.score),
        }
        for p in points
        if p.payload.get("clause_type") not in EXCLUDED_METADATA
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--configs",
        default="zero-shot,random-1,random-5,retrieval-1,retrieval-5",
        help="Comma-separated configs to run.",
    )
    args = parser.parse_args()

    allowed = {
        "zero-shot",
        "random-1",
        "random-5",
        "retrieval-1",
        "retrieval-5",
    }
    configs = [x.strip() for x in args.configs.split(",") if x.strip()]
    unknown = set(configs) - allowed
    if unknown:
        raise SystemExit(f"Unknown configs: {sorted(unknown)}")

    test_rows, embeddings = load_dense_test()
    train_pool = load_train_pool()
    labels = [x for x in load_labels() if x not in EXCLUDED_METADATA]
    definitions = load_label_definitions(labels)

    client = QdrantClient(path=str(QDRANT_PATH))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for config in configs:
        checkpoint = OUT_DIR / f"{config}.jsonl"
        records = []
        start = time.time()

        with checkpoint.open("w", encoding="utf-8") as handle:
            for idx, (row, vector) in enumerate(zip(test_rows, embeddings), start=1):
                examples = []
                candidates = labels
                if config == "random-1":
                    examples = random_demos(train_pool, 1, SEED + idx)
                elif config == "random-5":
                    examples = random_demos(train_pool, 5, SEED + idx)
                elif config.startswith("retrieval-"):
                    k = int(config.rsplit("-", 1)[1])
                    hits = dense_hits(client, vector, 5)
                    examples = hits[:k]
                    candidates = []
                    for hit in hits:
                        if hit["clause_type"] not in candidates:
                            candidates.append(hit["clause_type"])
                    if not candidates:
                        candidates = labels

                prompt = build_prompt(
                    clause_text=str(row["clause_text"]),
                    examples=examples,
                    labels=labels,
                    label_definitions={
                        label: definitions[label]
                        for label in candidates
                        if label in definitions
                    },
                    extracted_features=extract_legal_information(str(row["clause_text"])),
                    candidate_labels=candidates,
                )
                raw = call_ollama(
                    prompt,
                    model=OLLAMA_MODEL,
                )
                prediction = parse_prediction(raw, labels, candidate_labels=candidates)
                rec = {
                    "config": config,
                    "clause_id": str(row.get("clause_id", f"test-{idx}")),
                    "document_id": str(row["document_id"]),
                    "ground_truth": str(row["clause_type"]),
                    "prediction": prediction,
                    "correct": prediction == str(row["clause_type"]),
                    "demo_labels": [x.get("clause_type") for x in examples],
                    "candidate_labels": candidates,
                }
                records.append(rec)
                handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
                handle.flush()

                if idx % 25 == 0 or idx == len(test_rows):
                    print(
                        f"[{config}] {idx}/{len(test_rows)} "
                        f"acc={np.mean([r['correct'] for r in records]):.4f} "
                        f"elapsed={(time.time()-start)/60:.1f}m"
                    )

        y_true = [r["ground_truth"] for r in records]
        y_pred = [r["prediction"] for r in records]
        summary = {
            "config": config,
            "count": len(records),
            "accuracy": float(accuracy_score(y_true, y_pred)) if records else 0.0,
            "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0))
            if records else 0.0,
            "model": OLLAMA_MODEL,
            "test_contracts": len({r["document_id"] for r in records}),
            "seed": SEED,
        }
        (OUT_DIR / f"{config}_summary.json").write_text(
            json.dumps(summary, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, indent=2))

    client.close()


if __name__ == "__main__":
    main()
