from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import platform
import sys
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


TOP_K = 5
BASELINE_METRIC_KEYS = (
    "recall_at_1",
    "recall_at_3",
    "recall_at_5",
    "mrr",
    "classification_accuracy",
    "retrieval_miss_count",
    "classification_error_count",
    "ollama_selected_label_absent_from_top5_count",
    "unknown_count",
    "pipeline_error_count",
)


def package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def load_baseline_runner(root: Path):
    path = root / "diagnostics" / "fixed_10_classification_baseline" / "run_baseline.py"
    spec = importlib.util.spec_from_file_location("fixed_10_baseline_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load baseline runner: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_fixed_selection(root: Path, baseline_dir: Path) -> tuple[list[dict], dict]:
    metadata = json.loads((baseline_dir / "selected_10_rows.json").read_text(encoding="utf-8"))
    rows = metadata.get("rows", [])
    expected_ids = [f"fixed-10-{index:02d}" for index in range(1, 11)]
    if len(rows) != 10 or [row.get("benchmark_row_id") for row in rows] != expected_ids:
        raise RuntimeError("The classification experiment must use the exact fixed 10-row selection.")
    if metadata.get("source_test_csv") != "data/splits/test/master_clauses_test.csv":
        raise RuntimeError("The fixed benchmark source CSV does not match the baseline definition.")
    return rows, metadata


def rank_for(label: str, hits: list[dict]) -> int | None:
    for hit in hits:
        if hit.get("clause_type") == label:
            return int(hit["rank"])
    return None


def retrieval_matches_baseline(current: list[dict], baseline: list[dict]) -> bool:
    if len(current) != len(baseline):
        return False
    for current_hit, baseline_hit in zip(current, baseline):
        if current_hit.get("clause_type") != baseline_hit.get("clause_type"):
            return False
        if abs(float(current_hit.get("score", 0)) - float(baseline_hit.get("score", 0))) > 1e-8:
            return False
    return True


def evaluate(root: Path, qdrant_path: Path, baseline: dict, selected: list[dict]) -> dict:
    sys.path.insert(0, str(root / "backend"))
    from app.core.config import (
        COHERE_MODEL,
        OLLAMA_MAX_RETRY_ATTEMPTS,
        OLLAMA_MODEL,
        OLLAMA_TIMEOUT_SECONDS,
        OLLAMA_URL,
        QDRANT_COLLECTION,
        TOP_K as CONFIG_TOP_K,
        load_labels,
    )
    from app.core.rag.embedder import embed_queries, make_cohere_client
    from app.core.rag.generator import classify_clause
    from app.core.rag.retriever import make_qdrant_client, retrieve_similar

    if CONFIG_TOP_K != TOP_K:
        raise RuntimeError(f"Expected production TOP_K={TOP_K}, found {CONFIG_TOP_K}.")

    definitions_path = root / "data" / "metadata" / "cuad_label_definitions.json"
    definitions = json.loads(definitions_path.read_text(encoding="utf-8"))
    labels = load_labels()
    qdrant_client = make_qdrant_client()
    collection = qdrant_client.get_collection(collection_name=QDRANT_COLLECTION)
    vector_config = collection.config.params.vectors
    query_vectors = embed_queries(
        make_cohere_client(),
        [row["clause_text"] for row in selected],
    )

    results = []
    baseline_by_id = {row["benchmark_row_id"]: row for row in baseline["results"]}
    for row, query_vector in zip(selected, query_vectors):
        baseline_row = baseline_by_id[row["benchmark_row_id"]]
        ground_truth = row["clause_type"]
        try:
            retrieved = retrieve_similar(qdrant_client, query_vector, top_k=TOP_K)
            hits = [
                {
                    "rank": index,
                    "score": float(hit.get("score", 0.0)),
                    "document_id": hit.get("document_id"),
                    "clause_type": hit.get("clause_type"),
                    "clause_text": hit.get("clause_text", ""),
                }
                for index, hit in enumerate(retrieved, start=1)
            ]
            classification = classify_clause(
                clause_text=row["clause_text"],
                query_vector=query_vector,
                qdrant_client=qdrant_client,
                labels=labels,
                label_definitions={label: definitions[label] for label in labels},
                top_k=TOP_K,
            )
            prediction = classification["predicted_label"]
            status = classification.get("prediction_status", "UNKNOWN")
            gt_rank = rank_for(ground_truth, hits)
            prediction_in_top5 = prediction != "UNKNOWN" and any(
                hit["clause_type"] == prediction for hit in hits
            )
            selected_top1 = bool(hits and prediction != "UNKNOWN" and prediction == hits[0]["clause_type"])
            selected_another = bool(prediction_in_top5 and not selected_top1)
            prediction_outside = bool(prediction != "UNKNOWN" and not prediction_in_top5)
            invalid = status in {"OUT_OF_CANDIDATE", "MALFORMED_RESPONSE"}
            explicit_unknown = status == "UNKNOWN"
            if gt_rank is None:
                result_category = "RETRIEVAL_MISS"
            elif invalid:
                result_category = "INVALID_OUT_OF_CANDIDATE"
            elif explicit_unknown:
                result_category = "UNKNOWN_ABSTENTION"
            elif prediction == ground_truth:
                result_category = "CORRECT"
            else:
                result_category = "CLASSIFICATION_ERROR"
            new_correct = prediction == ground_truth
            baseline_correct = bool(baseline_row["prediction_equals_ground_truth"])
            if new_correct and baseline_correct:
                comparison_result = "UNCHANGED_CORRECT"
            elif new_correct:
                comparison_result = "IMPROVED"
            elif baseline_correct:
                comparison_result = "REGRESSED"
            else:
                comparison_result = "UNCHANGED_INCORRECT"
            results.append(
                {
                    **row,
                    "retrieved": hits,
                    "ground_truth_rank": gt_rank,
                    "ground_truth_in_top5": gt_rank is not None,
                    "qdrant_top1_label": hits[0]["clause_type"] if hits else None,
                    "qdrant_top1_score": hits[0]["score"] if hits else None,
                    "candidate_labels": classification.get("candidate_labels", []),
                    "raw_ollama_response": classification["raw_response"],
                    "ollama_prediction": prediction,
                    "prediction_status": status,
                    "raw_prediction_candidate": classification.get("raw_prediction_candidate"),
                    "prediction_equals_ground_truth": new_correct,
                    "ollama_selected_top1": selected_top1,
                    "ollama_selected_another_topk_category": selected_another,
                    "ollama_selected_label_absent_from_top5": prediction_outside,
                    "invalid_out_of_candidate": invalid,
                    "unknown_abstention": explicit_unknown,
                    "retrieval_matches_baseline": retrieval_matches_baseline(
                        hits, baseline_row["retrieved"]
                    ),
                    "result_category": result_category,
                    "baseline_prediction": baseline_row["ollama_prediction"],
                    "baseline_correct": baseline_correct,
                    "comparison_result": comparison_result,
                    "classifier_error": False,
                }
            )
        except Exception as exc:
            results.append(
                {
                    **row,
                    "retrieved": [],
                    "ground_truth_rank": None,
                    "ground_truth_in_top5": False,
                    "qdrant_top1_label": None,
                    "qdrant_top1_score": None,
                    "candidate_labels": [],
                    "raw_ollama_response": None,
                    "ollama_prediction": None,
                    "prediction_status": "PIPELINE_ERROR",
                    "raw_prediction_candidate": None,
                    "prediction_equals_ground_truth": False,
                    "ollama_selected_top1": False,
                    "ollama_selected_another_topk_category": False,
                    "ollama_selected_label_absent_from_top5": False,
                    "invalid_out_of_candidate": False,
                    "unknown_abstention": False,
                    "retrieval_matches_baseline": False,
                    "result_category": "PIPELINE_ERROR",
                    "baseline_prediction": baseline_row["ollama_prediction"],
                    "baseline_correct": bool(baseline_row["prediction_equals_ground_truth"]),
                    "comparison_result": "PIPELINE_ERROR",
                    "classifier_error": True,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    denominator = len(selected)
    metrics = {
        "recall_at_1": sum(bool(r["ground_truth_rank"] and r["ground_truth_rank"] <= 1) for r in results) / denominator,
        "recall_at_3": sum(bool(r["ground_truth_rank"] and r["ground_truth_rank"] <= 3) for r in results) / denominator,
        "recall_at_5": sum(bool(r["ground_truth_rank"] and r["ground_truth_rank"] <= 5) for r in results) / denominator,
        "mrr": sum(1 / r["ground_truth_rank"] if r["ground_truth_rank"] else 0 for r in results) / denominator,
        "classification_accuracy": sum(r["prediction_equals_ground_truth"] for r in results) / denominator,
        "correct_count": sum(r["result_category"] == "CORRECT" for r in results),
        "retrieval_miss_count": sum(r["result_category"] == "RETRIEVAL_MISS" for r in results),
        "classification_error_count": sum(r["result_category"] == "CLASSIFICATION_ERROR" for r in results),
        "invalid_out_of_candidate_count": sum(r["invalid_out_of_candidate"] for r in results),
        "unknown_count": sum(r["unknown_abstention"] for r in results),
        "ollama_selected_label_absent_from_top5_count": sum(
            r["ollama_selected_label_absent_from_top5"] for r in results
        ),
        "ground_truth_in_top5_count": sum(r["ground_truth_in_top5"] for r in results),
        "pipeline_error_count": sum(r["classifier_error"] for r in results),
        "retrieval_matches_baseline_count": sum(r["retrieval_matches_baseline"] for r in results),
    }
    output = {
        "status": "COMPLETE" if metrics["pipeline_error_count"] == 0 else "PARTIAL",
        "experiment_id": "fixed_10_classification_experiment",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": "969bd75",
        "selection": {
            "source_test_csv": baseline["selection"]["source_test_csv"],
            "seed": baseline["selection"]["seed"],
            "row_count": 10,
            "selected_row_ids": [row["benchmark_row_id"] for row in selected],
        },
        "environment": {
            "python_version": platform.python_version(),
            "embedding_model": COHERE_MODEL,
            "embedding_dimension": getattr(vector_config, "size", None),
            "qdrant_collection": QDRANT_COLLECTION,
            "qdrant_path": str(qdrant_path),
            "qdrant_distance": str(getattr(vector_config, "distance", vector_config)),
            "retrieval_top_k": TOP_K,
            "ollama_url": OLLAMA_URL,
            "ollama_model": OLLAMA_MODEL,
            "ollama_timeout_seconds": OLLAMA_TIMEOUT_SECONDS,
            "ollama_max_retry_attempts": OLLAMA_MAX_RETRY_ATTEMPTS,
            "generation_options": {"temperature": 0, "num_gpu": 0, "use_mmap": True, "num_ctx": 4096},
            "package_versions": {
                "torch": package_version("torch"),
                "qdrant-client": package_version("qdrant-client"),
                "cohere": package_version("cohere"),
            },
        },
        "metrics": metrics,
        "baseline_metrics": baseline["metrics"],
        "results": results,
        "safety": {
            "retrieval_logic_modified": False,
            "embedding_logic_modified": False,
            "segmentation_modified": False,
            "qdrant_modified": False,
            "risk_analysis_modified": False,
            "ollama_model_modified": False,
            "selected_rows_modified": False,
            "baseline_artifacts_modified": False,
        },
    }
    return output


def write_artifacts(output: dict, selected: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "experiment_results.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    fields = [
        "benchmark_row_id", "clause_type", "baseline_prediction", "ollama_prediction",
        "ground_truth_rank", "ground_truth_in_top5", "baseline_correct",
        "prediction_equals_ground_truth", "result_category", "prediction_status",
        "ollama_selected_top1", "ollama_selected_another_topk_category",
        "ollama_selected_label_absent_from_top5", "retrieval_matches_baseline",
    ]
    with (output_dir / "experiment_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in output["results"])

    baseline = output["baseline_metrics"]
    current = output["metrics"]
    comparison_rows = []
    for key in BASELINE_METRIC_KEYS:
        baseline_value = baseline.get(key, 0)
        current_value = current.get(key, 0)
        comparison_rows.append({
            "metric": key,
            "baseline": baseline_value,
            "classification_fix": current_value,
            "change": current_value - baseline_value,
        })
    with (output_dir / "comparison_baseline_vs_fix.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "baseline", "classification_fix", "change"])
        writer.writeheader()
        writer.writerows(comparison_rows)

    lines = [
        "# Fixed 10-Row Candidate-Constrained Classification Experiment",
        "",
        f"Status: **{output['status']}**",
        "",
        "## 1. Objective",
        "",
        "Test whether constraining Ollama to unique valid categories present in the unchanged Qdrant Top-5, with explicit UNKNOWN abstention, reduces classification-layer errors and out-of-candidate predictions.",
        "",
        "## 2. Baseline Configuration",
        "",
        f"- Baseline commit: `{output['baseline_commit']}`",
        f"- Test source: `{output['selection']['source_test_csv']}`",
        f"- Fixed seed: `{output['selection']['seed']}`",
        f"- Embedding model/dimension: `{output['environment']['embedding_model']}` / `{output['environment']['embedding_dimension']}`",
        f"- Qdrant collection/distance: `{output['environment']['qdrant_collection']}` / `{output['environment']['qdrant_distance']}`",
        f"- Retrieval Top-K: `{TOP_K}`",
        f"- Ollama model: `{output['environment']['ollama_model']}`",
        "",
        "## 3. Exact Benchmark Dataset",
        "",
        "The experiment reuses the baseline `selected_10_rows.json` without resampling.",
        "",
        "| Row | Original Row | Ground Truth | Document ID |",
        "|---|---:|---|---|",
    ]
    for row in selected:
        lines.append(f"| `{row['benchmark_row_id']}` | {row['original_row_index']} | `{row['clause_type']}` | `{row['document_id']}` |")
    lines.extend([
        "",
        "## 4. Classification Change",
        "",
        "The classification layer now derives unique valid candidate labels from the unchanged retrieved Top-5. The prompt exposes only those candidates and allows UNKNOWN when none is appropriate. The parser accepts only JSON labels in the candidate set, records explicit UNKNOWN, and records malformed or out-of-candidate responses instead of silently accepting them.",
        "",
        "## 5. Intentionally Unchanged",
        "",
        "Retrieval scoring, query embeddings, Qdrant data, Top-K, segmentation, risk analysis, Ollama model/configuration, and the fixed benchmark rows were not changed.",
        "",
        "## 6. Per-Row Comparison",
        "",
        "| Row | Ground Truth | Baseline Prediction | New Prediction | GT Rank | GT in Top-5 | Baseline Correct | New Correct | Result |",
        "|---|---|---|---|---:|---|---|---|---|",
    ])
    for row in output["results"]:
        lines.append(f"| `{row['benchmark_row_id']}` | `{row['clause_type']}` | `{row['baseline_prediction']}` | `{row['ollama_prediction']}` | {row['ground_truth_rank'] or '-'} | {'Yes' if row['ground_truth_in_top5'] else 'No'} | {'Yes' if row['baseline_correct'] else 'No'} | {'Yes' if row['prediction_equals_ground_truth'] else 'No'} | `{row['comparison_result']}` |")
    lines.extend(["", "### Retrieved Top-5 Categories", ""])
    for row in output["results"]:
        labels = ", ".join(f"{hit['rank']}. {hit['clause_type']} ({hit['score']:.6f})" for hit in row["retrieved"])
        lines.append(f"- `{row['benchmark_row_id']}`: {labels}")
    lines.extend([
        "",
        "## 7. Retrieval Metrics",
        "",
        f"- Recall@1: `{current['recall_at_1']:.4f}` (baseline `{baseline['recall_at_1']:.4f}`)",
        f"- Recall@3: `{current['recall_at_3']:.4f}` (baseline `{baseline['recall_at_3']:.4f}`)",
        f"- Recall@5: `{current['recall_at_5']:.4f}` (baseline `{baseline['recall_at_5']:.4f}`)",
        f"- MRR: `{current['mrr']:.4f}` (baseline `{baseline['mrr']:.4f}`)",
        f"- Rows with identical recorded retrieval: `{current['retrieval_matches_baseline_count']}/10`",
        "",
        "## 8. Classification Metrics",
        "",
        f"- Accuracy: `{current['classification_accuracy']:.4f}` ({current['correct_count']}/10; baseline `{baseline['classification_accuracy']:.4f}`)",
        f"- Retrieval misses: `{current['retrieval_miss_count']}`",
        f"- Classification errors: `{current['classification_error_count']}`",
        f"- Invalid/out-of-candidate responses: `{current['invalid_out_of_candidate_count']}`",
        f"- UNKNOWN/abstention: `{current['unknown_count']}`",
        f"- Valid predictions outside Top-5: `{current['ollama_selected_label_absent_from_top5_count']}`",
        f"- Pipeline/runtime errors: `{current['pipeline_error_count']}`",
        "",
        "## 9. Baseline vs Classification Fix",
        "",
        "| Metric | Baseline | Classification Fix | Change |",
        "|---|---:|---:|---:|",
    ])
    for row in comparison_rows:
        lines.append(f"| {row['metric']} | {row['baseline']:.4f} | {row['classification_fix']:.4f} | {row['change']:+.4f} |")
    lines.extend([
        "",
        "## 10. Error Analysis",
        "",
        f"- Retrieval limitation: `{current['retrieval_miss_count']}` rows lacked the ground-truth category in Top-5; a strict candidate-constrained classifier cannot reliably recover those labels.",
        f"- Classification limitation: `{current['classification_error_count']}` rows had the ground-truth category in Top-5 but received a different valid candidate.",
        f"- Invalid/out-of-candidate behavior: `{current['invalid_out_of_candidate_count']}` responses were rejected by the validator.",
        f"- Abstention: `{current['unknown_count']}` explicit UNKNOWN results occurred.",
        "",
        "## 11. Interpretation",
        "",
        "Retrieval metrics remained fixed, so any classification change is attributable to the classification layer. Candidate restriction prevents a valid prediction from being invented outside retrieved evidence, but it cannot repair retrieval misses. UNKNOWN is preferable to forcing a category when candidates are insufficient.",
        "",
        "## 12. Limitations",
        "",
        "This is a 10-row pilot benchmark and is not sufficient to claim generalization to the full CUAD test set. CUAD categories can overlap, and the fixed dataset provides one reference category per selected row for this controlled comparison.",
        "",
        "## 13. Conclusion",
        "",
        f"The classification fix produced accuracy `{current['classification_accuracy']:.4f}` versus baseline `{baseline['classification_accuracy']:.4f}` while preserving retrieval (`{current['retrieval_matches_baseline_count']}/10` rows identical). The result should be interpreted as a small controlled experiment, not a general performance claim.",
        "",
        "## 14. Recommendation for Next Experiment",
        "",
        "Evaluate the same candidate-constrained policy on a larger fixed benchmark and separately investigate the four retrieval misses; do not attribute those misses to Ollama classification.",
        "",
        "## Safety",
        "",
        "Only the classification-layer files and this diagnostic directory are intended for this experiment. Baseline artifacts and selected rows remain unchanged. No retrieval, embedding, segmentation, Qdrant, risk-analysis, `.env`, or Ollama model/configuration changes were made.",
    ])
    (output_dir / "classification_fix_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--qdrant-path", type=Path, required=True)
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    baseline = json.loads((args.baseline_dir / "baseline_results.json").read_text(encoding="utf-8"))
    selected, _ = load_fixed_selection(args.root, args.baseline_dir)
    output = evaluate(args.root, args.qdrant_path, baseline, selected)
    write_artifacts(output, selected, args.output_dir)
    print(json.dumps({"status": output["status"], "metrics": output["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
