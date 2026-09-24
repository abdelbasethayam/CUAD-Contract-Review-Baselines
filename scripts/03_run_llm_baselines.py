"""
Step 3 (LLM Baselines): Run A (Zero-Shot), B (Randomized Few-Shot), C (Retrieval Few-Shot).

Maintains separate checkpoints per baseline:
- output/eval_1495/checkpoints/baseline_A_partial.jsonl
- output/eval_1495/checkpoints/baseline_B_partial.jsonl
- output/eval_1495/checkpoints/baseline_C_partial.jsonl
"""

import csv
import json
import os
import random
import sys
import time
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient, models

# Import backend modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import OLLAMA_MODEL, OLLAMA_URL, TRAIN_DATA_PATH, load_labels
from app.core.rag.generator import call_ollama, extract_legal_information, parse_prediction
from app.core.rag.prompt import build_prompt, load_label_definitions

COLLECTION_NAME = "cuad_train_mpnet"
TOP_K = 5
RANDOM_SEED = 42

EXCLUDED_METADATA_LABELS = {
    "Document Name",
    "Parties",
    "Agreement Date",
    "Effective Date",
    "Expiration Date",
}


def load_train_pool(train_csv: Path) -> list[dict]:
    pool = []
    with train_csv.open("r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            label = str(row.get("clause_type", "")).strip()
            text = str(row.get("clause_text", "")).strip()
            is_meta = str(row.get("is_metadata", "")).lower() == "true"
            if label and text and not is_meta and label not in EXCLUDED_METADATA_LABELS:
                pool.append({"clause_type": label, "clause_text": text, "score": 1.0})
    return pool


def sample_random_demos(pool: list[dict], k: int = TOP_K, seed: int = RANDOM_SEED) -> list[dict]:
    rng = random.Random(seed)
    return rng.sample(pool, min(k, len(pool)))


def load_existing_checkpoint(ckpt_file: Path) -> dict[str, dict]:
    results = {}
    if ckpt_file.exists():
        with ckpt_file.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    results[item["clause_id"]] = item
    return results


def run_llm_baseline(
    config_name: str,
    ckpt_file: Path,
    test_clauses: list[dict],
    test_embeddings: np.ndarray,
    train_pool: list[dict],
    labels: list[str],
    label_defs: dict[str, str],
    client: QdrantClient,
):
    print(f"\n--- Starting Baseline {config_name} ---")
    processed = load_existing_checkpoint(ckpt_file)
    print(f"Loaded {len(processed)} existing predictions from checkpoint {ckpt_file.name}")

    ckpt_file.parent.mkdir(parents=True, exist_ok=True)
    out_handle = ckpt_file.open("a", encoding="utf-8")

    start_time = time.time()
    count = len(processed)
    failures = 0

    for idx, (clause, vector) in enumerate(zip(test_clauses, test_embeddings), start=1):
        clause_id = clause["clause_id"]
        if clause_id in processed:
            continue

        gt_label = clause["clause_type"]
        clause_text = clause["clause_text"]

        # Determine prompt demonstrations
        demos = []
        retrieved_hits = []

        if config_name == "A":
            # Zero-shot: no demonstrations
            demos = []
        elif config_name == "B":
            # Randomized few-shot: seed fixed per clause index
            demos = sample_random_demos(train_pool, k=TOP_K, seed=RANDOM_SEED + idx)
        elif config_name == "C":
            # Retrieval few-shot: Top-5 from Qdrant
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
            demos = [
                {"clause_type": h["clause_type"], "clause_text": h["clause_text"], "score": h["score"]}
                for h in retrieved_hits
            ]

        # Candidate labels derived from retrieved top-k or full label set
        candidate_labels = (
            [h["clause_type"] for h in retrieved_hits] if config_name == "C" and retrieved_hits else labels
        )

        extracted_features = extract_legal_information(clause_text)
        prompt = build_prompt(
            clause_text=clause_text,
            examples=demos,
            labels=labels,
            label_definitions={lbl: label_defs[lbl] for lbl in candidate_labels if lbl in label_defs},
            extracted_features=extracted_features,
            candidate_labels=candidate_labels,
        )

        # Call local LLM (Ollama)
        raw_response = ""
        prediction = None
        status = "OK"

        try:
            raw_response = call_ollama(prompt)
            prediction = parse_prediction(raw_response, labels, candidate_labels=candidate_labels)
        except Exception as exc:
            status = f"ERROR: {type(exc).__name__}: {exc}"
            failures += 1

        record = {
            "clause_id": clause_id,
            "ground_truth": gt_label,
            "prediction": prediction,
            "correct": prediction == gt_label if prediction else False,
            "status": status,
            "raw_response": raw_response,
            "demos": [d.get("clause_type") for d in demos],
            "prompt_length": len(prompt),
        }

        processed[clause_id] = record
        out_handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        out_handle.flush()
        count += 1

        if count % 50 == 0 or count == len(test_clauses):
            elapsed = time.time() - start_time
            rate = count / max(elapsed, 1.0)
            rem = (len(test_clauses) - count) / rate if rate > 0 else 0
            print(
                f"[{config_name}] Processed {count}/{len(test_clauses)} clauses "
                f"({rate:.2f} cl/s, ETA: {rem/60:.1f} mins) | Failures: {failures}"
            )

    out_handle.close()
    acc = sum(r["correct"] for r in processed.values()) / len(processed) if processed else 0.0
    print(f"--- Baseline {config_name} Complete ---")
    print(f"Total: {len(processed)} clauses | Accuracy: {acc:.4f} ({acc*100:.2f}%) | Failures: {failures}")
    return processed, acc


def main():
    root = Path(__file__).resolve().parents[1]
    meta_path = root / "output" / "embeddings" / "test_1495_metadata.json"
    npy_path = root / "output" / "embeddings" / "test_1495_mpnet.npy"
    train_csv = root / "data" / "splits" / "train" / "master_clauses_train.csv"

    if not meta_path.exists() or not npy_path.exists():
        raise FileNotFoundError("Missing test embeddings. Run 01_reembed_local.py first.")

    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    test_clauses = metadata["clauses"]
    test_embeddings = np.load(npy_path)

    train_pool = load_train_pool(train_csv)
    labels = load_labels()
    label_defs = load_label_definitions(labels)

    qdrant_db_path = root / "data" / "qdrant_local"
    client = QdrantClient(path=str(qdrant_db_path))

    ckpt_dir = root / "output" / "eval_1495" / "checkpoints"
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    for cfg in ("A", "B", "C"):
        ckpt_file = ckpt_dir / f"baseline_{cfg}_partial.jsonl"
        run_llm_baseline(
            cfg,
            ckpt_file,
            test_clauses,
            test_embeddings,
            train_pool,
            labels,
            label_defs,
            client,
        )


if __name__ == "__main__":
    main()
