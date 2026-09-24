"""
Step 2 (Fast Baselines): Run D (Pure kNN Top-1), E (Pure kNN Majority Vote), F (Weighted kNN).

Saves separate checkpoints per baseline:
- output/eval_1495/checkpoints/baseline_D_partial.jsonl
- output/eval_1495/checkpoints/baseline_E_partial.jsonl
- output/eval_1495/checkpoints/baseline_F_partial.jsonl
- output/eval_1495/predictions_fast_baselines.json
"""

import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient, models

COLLECTION_NAME = "cuad_train_mpnet"
TOP_K = 5


def load_test_data(root: Path):
    meta_path = root / "output" / "embeddings" / "test_1495_metadata.json"
    npy_path = root / "output" / "embeddings" / "test_1495_mpnet.npy"

    if not meta_path.exists() or not npy_path.exists():
        raise FileNotFoundError(
            "Missing test embeddings. Run 01_reembed_local.py first."
        )

    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    embeddings = np.load(npy_path)
    return metadata["clauses"], embeddings


def run_fast_baselines():
    root = Path(__file__).resolve().parents[1]
    test_clauses, test_embeddings = load_test_data(root)

    ckpt_dir = root / "output" / "eval_1495" / "checkpoints"
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    qdrant_db_path = root / "data" / "qdrant_local"
    client = QdrantClient(path=str(qdrant_db_path))

    print(f"Running Fast Baselines (D, E, F) on {len(test_clauses)} test clauses...")
    start_time = time.time()

    results_D = []
    results_E = []
    results_F = []

    file_D = ckpt_dir / "baseline_D_partial.jsonl"
    file_E = ckpt_dir / "baseline_E_partial.jsonl"
    file_F = ckpt_dir / "baseline_F_partial.jsonl"

    f_D = file_D.open("w", encoding="utf-8")
    f_E = file_E.open("w", encoding="utf-8")
    f_F = file_F.open("w", encoding="utf-8")

    for idx, (clause, vector) in enumerate(zip(test_clauses, test_embeddings), start=1):
        gt_label = clause["clause_type"]

        # Search top-k in Qdrant
        response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector.tolist(),
            limit=TOP_K,
        )
        search_res = getattr(response, "points", response)

        retrieved_hits = [
            {
                "rank": rank,
                "score": float(hit.score),
                "clause_type": str(hit.payload["clause_type"]),
                "clause_text": str(hit.payload["clause_text"]),
                "document_id": str(hit.payload["document_id"]),
            }
            for rank, hit in enumerate(search_res, start=1)
        ]

        hit_labels = [h["clause_type"] for h in retrieved_hits if h.get("clause_type")]
        hit_scores = [h["score"] for h in retrieved_hits if h.get("clause_type")]

        # Baseline D: Pure kNN Top-1
        pred_D = hit_labels[0] if hit_labels else None
        rec_D = {
            "clause_id": clause["clause_id"],
            "ground_truth": gt_label,
            "prediction": pred_D,
            "correct": pred_D == gt_label,
            "retrieved_hits": retrieved_hits,
        }
        results_D.append(rec_D)
        f_D.write(json.dumps(rec_D, ensure_ascii=False) + "\n")

        # Baseline E: Pure kNN Majority Vote
        pred_E = Counter(hit_labels).most_common(1)[0][0] if hit_labels else None
        rec_E = {
            "clause_id": clause["clause_id"],
            "ground_truth": gt_label,
            "prediction": pred_E,
            "correct": pred_E == gt_label,
            "retrieved_hits": retrieved_hits,
        }
        results_E.append(rec_E)
        f_E.write(json.dumps(rec_E, ensure_ascii=False) + "\n")

        # Baseline F: Weighted kNN
        weighted_scores = defaultdict(float)
        for lbl, sc in zip(hit_labels, hit_scores):
            weighted_scores[lbl] += max(sc, 0.0)
        pred_F = max(weighted_scores.items(), key=lambda item: item[1])[0] if weighted_scores else None
        rec_F = {
            "clause_id": clause["clause_id"],
            "ground_truth": gt_label,
            "prediction": pred_F,
            "correct": pred_F == gt_label,
            "retrieved_hits": retrieved_hits,
        }
        results_F.append(rec_F)
        f_F.write(json.dumps(rec_F, ensure_ascii=False) + "\n")

    f_D.close()
    f_E.close()
    f_F.close()

    total = len(test_clauses)
    acc_D = sum(r["correct"] for r in results_D) / total
    acc_E = sum(r["correct"] for r in results_E) / total
    acc_F = sum(r["correct"] for r in results_F) / total

    duration = time.time() - start_time
    summary = {
        "duration_seconds": duration,
        "total_test_clauses": total,
        "metrics": {
            "baseline_D_knn_top1_accuracy": acc_D,
            "baseline_E_knn_majority_accuracy": acc_E,
            "baseline_F_weighted_knn_accuracy": acc_F,
        },
    }

    out_file = root / "output" / "eval_1495" / "predictions_fast_baselines.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n--- FAST BASELINES RESULTS ---")
    print(f"Evaluated {total} clauses in {duration:.2f} seconds.")
    print(f"Baseline D (Pure kNN Top-1) Accuracy:        {acc_D:.4f} ({acc_D * 100:.2f}%)")
    print(f"Baseline E (Pure kNN Majority Vote) Accuracy: {acc_E:.4f} ({acc_E * 100:.2f}%)")
    print(f"Baseline F (Weighted kNN) Accuracy:          {acc_F:.4f} ({acc_F * 100:.2f}%)")


if __name__ == "__main__":
    run_fast_baselines()
