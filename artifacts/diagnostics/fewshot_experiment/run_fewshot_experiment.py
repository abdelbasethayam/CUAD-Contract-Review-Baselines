"""
Few-Shot Baseline Diagnostic Runner for NLLP 2026 Paper Evaluation.

Implements & Compares:
1. Zero-Shot Prompt & Demonstration Format
2. Randomized Few-Shot Prompt Demonstrations (Reviewer 1)
3. Retrieval-Augmented Few-Shot Prompt Demonstrations (Paper Method)
4. Pure kNN (Top-1 / Majority Vote) Baseline (Reviewer 2)
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

# Fix seed for reproducibility
RANDOM_SEED = 20260920
TOP_K = 5
EXCLUDED_METADATA_LABELS = {
    "Document Name",
    "Parties",
    "Agreement Date",
    "Effective Date",
    "Expiration Date",
}


def load_train_pool(train_csv_path: Path) -> list[dict]:
    pool = []
    if not train_csv_path.exists():
        return pool
    with train_csv_path.open("r", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            label = row.get("clause_type", "").strip()
            text = row.get("clause_text", "").strip()
            is_meta = str(row.get("is_metadata", "")).lower() == "true"
            if label and not is_meta and label not in EXCLUDED_METADATA_LABELS and text:
                pool.append({"clause_type": label, "clause_text": text, "score": 1.0})
    return pool


def sample_random_examples(pool: list[dict], k: int = TOP_K, seed: int = RANDOM_SEED) -> list[dict]:
    if not pool:
        return []
    rng = random.Random(seed)
    sampled = rng.sample(pool, min(k, len(pool)))
    return [{"clause_type": item["clause_type"], "clause_text": item["clause_text"], "score": 1.0} for item in sampled]


def evaluate_fewshot_strategies(root_path: Path) -> dict:
    sys.path.insert(0, str(root_path / "backend"))

    from app.core.config import TRAIN_DATA_PATH, load_labels
    from app.core.rag.generator import extract_legal_information
    from app.core.rag.prompt import build_prompt, load_label_definitions

    train_pool = load_train_pool(TRAIN_DATA_PATH)
    labels = load_labels()
    definitions = load_label_definitions(labels)

    # Load fixed 10 test rows benchmark
    fixed_json = root_path / "artifacts" / "diagnostics" / "fixed_10_classification_baseline" / "selected_10_rows.json"
    if not fixed_json.exists():
        raise FileNotFoundError(f"Missing baseline file: {fixed_json}")
    
    metadata = json.loads(fixed_json.read_text(encoding="utf-8"))
    test_rows = metadata.get("rows", [])

    # Load baseline retrieval results from baseline_results.json
    baseline_results_path = root_path / "artifacts" / "diagnostics" / "fixed_10_classification_baseline" / "baseline_results.json"
    baseline_data = json.loads(baseline_results_path.read_text(encoding="utf-8")) if baseline_results_path.exists() else {}

    results_summary = []

    for row in test_rows:
        benchmark_id = row["benchmark_row_id"]
        ground_truth = row["clause_type"]
        clause_text = row["clause_text"]

        # Retrieve stored top-k hits for this row from baseline_results.json
        row_baseline = next((r for r in baseline_data.get("results", []) if r.get("benchmark_row_id") == benchmark_id), None)
        retrieved_hits = row_baseline.get("retrieved", []) if row_baseline else []

        # 1. Zero-Shot Prompt
        zero_shot_prompt = build_prompt(
            clause_text=clause_text,
            examples=[],
            labels=labels,
            label_definitions=definitions,
            extracted_features=extract_legal_information(clause_text),
        )

        # 2. Randomized Few-Shot Examples (Reviewer 1)
        rand_examples = sample_random_examples(train_pool, k=TOP_K, seed=RANDOM_SEED + int(benchmark_id.split("-")[-1]))
        random_fewshot_prompt = build_prompt(
            clause_text=clause_text,
            examples=rand_examples,
            labels=labels,
            label_definitions=definitions,
            extracted_features=extract_legal_information(clause_text),
        )

        # 3. Retrieval-Augmented Few-Shot Prompt (Paper Method)
        retrieved_examples_for_prompt = [
            {"clause_type": h["clause_type"], "clause_text": h["clause_text"], "score": h.get("score", 0.0)}
            for h in retrieved_hits
        ]
        retrieval_fewshot_prompt = build_prompt(
            clause_text=clause_text,
            examples=retrieved_examples_for_prompt,
            labels=labels,
            label_definitions=definitions,
            extracted_features=extract_legal_information(clause_text),
        )

        # 4. Pure kNN Top-1 Classifier (Reviewer 2)
        knn_top1_prediction = retrieved_hits[0]["clause_type"] if retrieved_hits else None
        
        # 5. Pure kNN Majority Vote Classifier (Reviewer 2)
        if retrieved_hits:
            hit_labels = [h["clause_type"] for h in retrieved_hits if h.get("clause_type")]
            knn_majority_prediction = Counter(hit_labels).most_common(1)[0][0] if hit_labels else None
        else:
            knn_majority_prediction = None

        # Existing stored RAG LLM prediction
        rag_llm_prediction = row_baseline.get("ollama_prediction") if row_baseline else None

        results_summary.append({
            "benchmark_row_id": benchmark_id,
            "ground_truth": ground_truth,
            "knn_top1_prediction": knn_top1_prediction,
            "knn_top1_correct": knn_top1_prediction == ground_truth,
            "knn_majority_prediction": knn_majority_prediction,
            "knn_majority_correct": knn_majority_prediction == ground_truth,
            "rag_llm_prediction": rag_llm_prediction,
            "rag_llm_correct": rag_llm_prediction == ground_truth if rag_llm_prediction else False,
            "random_demonstration_labels": [e["clause_type"] for e in rand_examples],
            "zero_shot_prompt_length": len(zero_shot_prompt),
            "random_fewshot_prompt_length": len(random_fewshot_prompt),
            "retrieval_fewshot_prompt_length": len(retrieval_fewshot_prompt),
        })

    total = len(results_summary)
    knn_top1_acc = sum(r["knn_top1_correct"] for r in results_summary) / total
    knn_maj_acc = sum(r["knn_majority_correct"] for r in results_summary) / total
    rag_llm_acc = sum(r["rag_llm_correct"] for r in results_summary) / total

    report = {
        "status": "COMPLETE",
        "benchmark_id": "fixed_10_fewshot_comparative_experiment",
        "total_evaluated": total,
        "metrics": {
            "knn_top1_accuracy": knn_top1_acc,
            "knn_majority_accuracy": knn_maj_acc,
            "rag_llm_accuracy": rag_llm_acc,
        },
        "rows": results_summary
    }

    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()

    report = evaluate_fewshot_strategies(args.root)
    out_dir = args.root / "artifacts" / "diagnostics" / "fewshot_experiment"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    (out_dir / "fewshot_comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2))


if __name__ == "__main__":
    main()
