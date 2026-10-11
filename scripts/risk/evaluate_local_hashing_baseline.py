#!/usr/bin/env python3
"""Evaluate deterministic local-hashing nearest-neighbor retrieval on held-out CUAD.

This is a clause-category retrieval baseline only. It is not a risk-predicate or
legal-correctness evaluation. Documents are contract-disjoint from the index.
"""
from __future__ import annotations

import csv
import hashlib
import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.metrics import f1_score

ROOT = Path(__file__).resolve().parents[2]
TRAIN_CSV = ROOT / "data/splits/train/master_clauses_train.csv"
TEST_CSV = ROOT / "data/splits/test/master_clauses_test.csv"
OUT = ROOT / "data/risk/results/local_hashing_cuad_retrieval_baseline.json"
N_FEATURES = 768
TOP_K = 5
BOOTSTRAP_REPLICATES = 1000
SEED = 42
EXCLUDED = {
    "Document Name", "Parties", "Agreement Date", "Effective Date", "Expiration Date"
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_eligible(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    output = []
    for row in rows:
        label = str(row.get("clause_type") or "").strip()
        text = str(row.get("clause_text") or "").strip()
        metadata = str(row.get("is_metadata") or "").strip().lower() in {"true", "1", "yes"}
        if metadata or label in EXCLUDED or not text or not label:
            continue
        output.append({
            "document_id": str(row.get("document_id") or "").strip(),
            "clause_type": label,
            "clause_text": text,
        })
    return output


def percentile_interval(values: list[float]) -> dict:
    return {
        "lower_95": round(float(np.percentile(values, 2.5)), 4),
        "upper_95": round(float(np.percentile(values, 97.5)), 4),
    }


def main() -> int:
    start = time.monotonic()
    train = read_eligible(TRAIN_CSV)
    test = read_eligible(TEST_CSV)
    train_docs = {x["document_id"] for x in train}
    test_docs = {x["document_id"] for x in test}
    overlap = train_docs & test_docs
    if overlap:
        raise SystemExit(f"Train/test contract overlap detected: {len(overlap)}")

    labels_train = [x["clause_type"] for x in train]
    labels_test = [x["clause_type"] for x in test]
    label_set = sorted(set(labels_test))
    texts_train = [x["clause_text"] for x in train]
    texts_test = [x["clause_text"] for x in test]

    # Keep this vectorizer exactly aligned with LocalHashingEmbedder in embedder.py.
    vectorizer = HashingVectorizer(
        n_features=N_FEATURES,
        alternate_sign=False,
        norm="l2",
        ngram_range=(1, 2),
        lowercase=True,
        strip_accents="unicode",
        token_pattern=r"(?u)\b\w+\b",
    )
    x_train = vectorizer.transform(texts_train)
    x_test = vectorizer.transform(texts_test)
    similarities = x_test @ x_train.T

    y_pred: list[str] = []
    recall_at_1: list[int] = []
    recall_at_5: list[int] = []
    reciprocal_rank_at_5: list[float] = []
    row_scores: list[list[float]] = []

    for i in range(similarities.shape[0]):
        row = similarities.getrow(i).toarray().ravel()
        # Stable tie-breaking by corpus row index makes this deterministic.
        order = np.argsort(-row, kind="stable")[:TOP_K]
        row_scores.append([float(row[j]) for j in order])
        candidate_labels = [labels_train[j] for j in order]
        gold = labels_test[i]
        y_pred.append(candidate_labels[0])
        recall_at_1.append(int(gold == candidate_labels[0]))
        hit_positions = [rank for rank, label in enumerate(candidate_labels, start=1) if label == gold]
        recall_at_5.append(int(bool(hit_positions)))
        reciprocal_rank_at_5.append(1.0 / hit_positions[0] if hit_positions else 0.0)

    accuracy = float(np.mean(np.asarray(y_pred) == np.asarray(labels_test)))
    macro_f1 = float(f1_score(labels_test, y_pred, labels=label_set, average="macro", zero_division=0))
    recall1 = float(np.mean(recall_at_1))
    recall5 = float(np.mean(recall_at_5))
    mrr5 = float(np.mean(reciprocal_rank_at_5))

    # Contract-cluster bootstrap: sample test contracts with replacement, carrying
    # all eligible clause queries for each sampled contract.
    rows_by_doc: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(test):
        rows_by_doc[row["document_id"]].append(index)
    unique_docs = sorted(rows_by_doc)
    rng = np.random.default_rng(SEED)
    boot_acc: list[float] = []
    boot_f1: list[float] = []
    y_true_arr = np.asarray(labels_test)
    y_pred_arr = np.asarray(y_pred)
    for _ in range(BOOTSTRAP_REPLICATES):
        sampled_docs = rng.choice(unique_docs, size=len(unique_docs), replace=True)
        sampled_indices = [index for doc in sampled_docs for index in rows_by_doc[str(doc)]]
        yt = y_true_arr[sampled_indices]
        yp = y_pred_arr[sampled_indices]
        boot_acc.append(float(np.mean(yt == yp)))
        boot_f1.append(float(f1_score(yt, yp, labels=label_set, average="macro", zero_division=0)))

    class_counts = Counter(labels_test)
    rows_out = []
    for label in sorted(class_counts):
        support_indices = [i for i, gold in enumerate(labels_test) if gold == label]
        correct = sum(y_pred[i] == label for i in support_indices)
        hit5 = sum(recall_at_5[i] for i in support_indices)
        rows_out.append({
            "label": label,
            "support": len(support_indices),
            "nearest_neighbor_correct": correct,
            "nearest_neighbor_accuracy": round(correct / len(support_indices), 4) if support_indices else None,
            "recall_at_5_hits": hit5,
            "recall_at_5": round(hit5 / len(support_indices), 4) if support_indices else None,
        })

    result = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "experiment_name": "local_hashing_cuad_nearest_neighbor_retrieval",
        "scope": "Held-out CUAD clause-category retrieval/classification baseline; not custom-risk accuracy, legal correctness or severity evaluation.",
        "configuration": {
            "embedding": "sklearn HashingVectorizer",
            "dimension": N_FEATURES,
            "ngram_range": [1, 2],
            "alternate_sign": False,
            "normalization": "l2",
            "similarity": "sparse dot product of L2-normalized vectors (cosine similarity)",
            "top_k": TOP_K,
            "tie_breaking": "stable corpus-row order",
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "bootstrap_unit": "test contract (cluster bootstrap)",
            "bootstrap_seed": SEED,
        },
        "inputs": {
            "train_csv": str(TRAIN_CSV.relative_to(ROOT)),
            "train_csv_sha256": sha256(TRAIN_CSV),
            "test_csv": str(TEST_CSV.relative_to(ROOT)),
            "test_csv_sha256": sha256(TEST_CSV),
        },
        "isolation": {
            "train_contract_count": len(train_docs),
            "test_contract_count": len(test_docs),
            "train_eligible_rows": len(train),
            "test_eligible_rows": len(test),
            "train_test_contract_overlap": len(overlap),
            "passed": not overlap,
        },
        "metrics": {
            "nearest_neighbor_accuracy": round(accuracy, 4),
            "nearest_neighbor_macro_f1": round(macro_f1, 4),
            "recall_at_1": round(recall1, 4),
            "recall_at_5": round(recall5, 4),
            "mrr_at_5": round(mrr5, 4),
            "nearest_neighbor_accuracy_contract_bootstrap_95_ci": percentile_interval(boot_acc),
            "nearest_neighbor_macro_f1_contract_bootstrap_95_ci": percentile_interval(boot_f1),
        },
        "label_metrics": rows_out,
        "runtime_seconds": round(time.monotonic() - start, 3),
        "interpretation": (
            "Nearest-neighbor labels and top-5 hit metrics measure the local lexical-vector baseline only. "
            "They are not numerically equivalent to the prior Cohere/retrieval-conditioned SLM configuration. "
            "The held-out true category labels are used only for evaluation and were not inserted into the index."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "output": str(OUT.relative_to(ROOT)),
        "isolation": result["isolation"],
        "metrics": result["metrics"],
        "runtime_seconds": result["runtime_seconds"],
        "labels_with_test_support": len(label_set),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
