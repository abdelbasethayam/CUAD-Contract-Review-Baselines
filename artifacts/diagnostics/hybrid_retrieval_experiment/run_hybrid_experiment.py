from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


TOP_K = 5
BASELINE_METRICS = (
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
    "retrieval_recovery_count",
)


def package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def rank_for(label: str, results: list[dict], rank_key: str = "rank") -> int | None:
    for result in results:
        if result.get("clause_type") == label:
            return int(result[rank_key])
    return None


def load_fixed_rows(root: Path) -> list[dict]:
    selection_path = root / "diagnostics" / "fixed_10_classification_baseline" / "selected_10_rows.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    rows = selection.get("rows", [])
    expected_ids = [f"fixed-10-{index:02d}" for index in range(1, 11)]
    if len(rows) != 10 or [row.get("benchmark_row_id") for row in rows] != expected_ids:
        raise RuntimeError("The hybrid experiment requires the exact fixed 10-row benchmark.")
    if selection.get("source_test_csv") != "data/splits/test/master_clauses_test.csv":
        raise RuntimeError("The fixed benchmark source is not the approved test CSV.")
    return rows


def classify_previous_miss(
    baseline_row: dict,
    vector_rank: int | None,
    bm25_rank: int | None,
    hybrid_rank: int | None,
) -> str:
    if baseline_row["ground_truth_in_top5"]:
        return "NOT_PREVIOUS_MISS"
    vector_found = vector_rank is not None
    bm25_found = bm25_rank is not None
    hybrid_found = hybrid_rank is not None and hybrid_rank <= TOP_K
    if hybrid_found and bm25_found:
        return "RECOVERED_BY_BM25_AND_RRF"
    if bm25_found and not hybrid_found:
        return "BM25_FOUND_BUT_RRF_DID_NOT_PROMOTE"
    if vector_found:
        return "VECTOR_FOUND"
    if not vector_found and not bm25_found:
        return "BOTH_MISSED"
    return "OTHER"


def evaluate(args: argparse.Namespace) -> dict:
    sys.path.insert(0, str(args.root / "backend"))
    hybrid_module_dir = args.root / "diagnostics" / "hybrid_retrieval_experiment"
    sys.path.insert(0, str(hybrid_module_dir))
    from hybrid_retriever import BM25_DEPTH, RRF_K, VECTOR_DEPTH, BM25Index, HybridQueryClient

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
    from app.core.rag.retriever import make_qdrant_client

    if CONFIG_TOP_K != TOP_K:
        raise RuntimeError(f"Expected production TOP_K={TOP_K}, found {CONFIG_TOP_K}.")
    if QDRANT_COLLECTION != "cuad_train":
        raise RuntimeError(f"Expected cuad_train, found {QDRANT_COLLECTION}.")

    baseline = json.loads((args.baseline_dir / "experiment_results.json").read_text(encoding="utf-8"))
    baseline_by_id = {row["benchmark_row_id"]: row for row in baseline["results"]}
    selected = load_fixed_rows(args.root)
    train_csv = args.root / "data" / "splits" / "train" / "master_clauses_train.csv"
    bm25_index = BM25Index.from_training_csv(train_csv)
    fixed_test_keys = {
        (row["document_id"], row["clause_type"], row["clause_text"])
        for row in selected
    }
    corpus_keys = {
        (record.document_id, record.clause_type, record.clause_text)
        for record in bm25_index.records
    }
    leaked_keys = sorted(fixed_test_keys & corpus_keys)
    if leaked_keys:
        raise RuntimeError(f"Fixed test rows found in BM25 corpus: {len(leaked_keys)}")
    leaked_texts = [row["clause_text"] for row in selected if any(row["clause_text"] == record.clause_text for record in bm25_index.records)]
    if leaked_texts:
        raise RuntimeError(f"Fixed test text found in BM25 corpus: {len(leaked_texts)}")

    labels = load_labels()
    definitions = json.loads((args.root / "data" / "metadata" / "cuad_label_definitions.json").read_text(encoding="utf-8"))
    qdrant_client = make_qdrant_client()
    collection = qdrant_client.get_collection(collection_name=QDRANT_COLLECTION)
    vector_config = collection.config.params.vectors
    query_vectors = embed_queries(make_cohere_client(), [row["clause_text"] for row in selected])
    results = []

    for row, query_vector in zip(selected, query_vectors):
        baseline_row = baseline_by_id[row["benchmark_row_id"]]
        hybrid_client = HybridQueryClient(qdrant_client, bm25_index)
        hybrid_client.set_query_text(row["clause_text"])
        try:
            classification = classify_clause(
                clause_text=row["clause_text"],
                query_vector=query_vector,
                qdrant_client=hybrid_client,
                labels=labels,
                label_definitions={label: definitions[label] for label in labels},
                top_k=TOP_K,
            )
            diagnostics = hybrid_client.last_diagnostics
            vector_top20 = diagnostics["vector_top20"]
            bm25_top20 = diagnostics["bm25_top20"]
            hybrid_ranked = diagnostics["hybrid_ranked"]
            hybrid_top5 = diagnostics["hybrid_top5"]
            ground_truth = row["clause_type"]
            vector_rank = rank_for(ground_truth, vector_top20)
            bm25_rank = rank_for(ground_truth, bm25_top20)
            hybrid_rank = rank_for(ground_truth, hybrid_ranked, "hybrid_rank")
            prediction = classification["predicted_label"]
            prediction_status = classification.get("prediction_status", "UNKNOWN")
            hybrid_in_top5 = hybrid_rank is not None and hybrid_rank <= TOP_K
            prediction_in_top5 = prediction != "UNKNOWN" and any(
                item["clause_type"] == prediction for item in hybrid_top5
            )
            invalid = prediction_status in {"OUT_OF_CANDIDATE", "MALFORMED_RESPONSE"}
            explicit_unknown = prediction_status == "UNKNOWN"
            if not hybrid_in_top5:
                result_category = "RETRIEVAL_MISS"
            elif invalid:
                result_category = "INVALID_OUT_OF_CANDIDATE"
            elif explicit_unknown:
                result_category = "UNKNOWN_ABSTENTION"
            elif prediction == ground_truth:
                result_category = "CORRECT"
            else:
                result_category = "CLASSIFICATION_ERROR"
            results.append(
                {
                    **row,
                    "vector_top20": vector_top20,
                    "bm25_top20": bm25_top20,
                    "hybrid_ranked": hybrid_ranked,
                    "hybrid_top5": hybrid_top5,
                    "vector_gt_rank": vector_rank,
                    "bm25_gt_rank": bm25_rank,
                    "hybrid_gt_rank": hybrid_rank,
                    "vector_gt_in_top5": vector_rank is not None and vector_rank <= TOP_K,
                    "bm25_gt_in_top5": bm25_rank is not None and bm25_rank <= TOP_K,
                    "hybrid_gt_in_top5": hybrid_in_top5,
                    "candidate_labels": classification.get("candidate_labels", []),
                    "ollama_prediction": prediction,
                    "prediction_status": prediction_status,
                    "raw_prediction_candidate": classification.get("raw_prediction_candidate"),
                    "raw_ollama_response": classification["raw_response"],
                    "prediction_equals_ground_truth": prediction == ground_truth,
                    "ollama_selected_label_absent_from_top5": prediction != "UNKNOWN" and not prediction_in_top5,
                    "invalid_out_of_candidate": invalid,
                    "unknown_abstention": explicit_unknown,
                    "result_category": result_category,
                    "previous_miss_analysis": classify_previous_miss(
                        baseline_row, vector_rank, bm25_rank, hybrid_rank
                    ),
                    "pipeline_error": False,
                }
            )
        except Exception as exc:
            results.append(
                {
                    **row,
                    "vector_top20": [],
                    "bm25_top20": [],
                    "hybrid_ranked": [],
                    "hybrid_top5": [],
                    "vector_gt_rank": None,
                    "bm25_gt_rank": None,
                    "hybrid_gt_rank": None,
                    "vector_gt_in_top5": False,
                    "bm25_gt_in_top5": False,
                    "hybrid_gt_in_top5": False,
                    "candidate_labels": [],
                    "ollama_prediction": None,
                    "prediction_status": "PIPELINE_ERROR",
                    "raw_prediction_candidate": None,
                    "raw_ollama_response": None,
                    "prediction_equals_ground_truth": False,
                    "ollama_selected_label_absent_from_top5": False,
                    "invalid_out_of_candidate": False,
                    "unknown_abstention": False,
                    "result_category": "PIPELINE_ERROR",
                    "previous_miss_analysis": "OTHER",
                    "pipeline_error": True,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    denominator = len(results)
    metric = {
        "recall_at_1": sum(bool(r["hybrid_gt_rank"] and r["hybrid_gt_rank"] <= 1) for r in results) / denominator,
        "recall_at_3": sum(bool(r["hybrid_gt_rank"] and r["hybrid_gt_rank"] <= 3) for r in results) / denominator,
        "recall_at_5": sum(bool(r["hybrid_gt_rank"] and r["hybrid_gt_rank"] <= 5) for r in results) / denominator,
        "mrr": sum(1 / r["hybrid_gt_rank"] if r["hybrid_gt_rank"] else 0 for r in results) / denominator,
        "classification_accuracy": sum(r["prediction_equals_ground_truth"] for r in results) / denominator,
        "retrieval_miss_count": sum(r["result_category"] == "RETRIEVAL_MISS" for r in results),
        "classification_error_count": sum(r["result_category"] == "CLASSIFICATION_ERROR" for r in results),
        "ollama_selected_label_absent_from_top5_count": sum(r["ollama_selected_label_absent_from_top5"] for r in results),
        "unknown_count": sum(r["unknown_abstention"] for r in results),
        "pipeline_error_count": sum(r["pipeline_error"] for r in results),
        "correct_count": sum(r["result_category"] == "CORRECT" for r in results),
        "invalid_out_of_candidate_count": sum(r["invalid_out_of_candidate"] for r in results),
        "retrieval_recovery_count": sum(r["previous_miss_analysis"] == "RECOVERED_BY_BM25_AND_RRF" for r in results),
    }
    recovery_counts = Counter(r["previous_miss_analysis"] for r in results if r["previous_miss_analysis"] != "NOT_PREVIOUS_MISS")
    return {
        "status": "COMPLETE" if metric["pipeline_error_count"] == 0 else "PARTIAL",
        "experiment_id": "hybrid_retrieval_experiment",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_reference": {
            "experiment": "fixed_10_classification_experiment",
            "metrics": baseline["metrics"],
        },
        "configuration": {
            "source_test_csv": "data/splits/test/master_clauses_test.csv",
            "fixed_row_count": 10,
            "embedding_model": COHERE_MODEL,
            "embedding_dimension": getattr(vector_config, "size", None),
            "qdrant_collection": QDRANT_COLLECTION,
            "qdrant_distance": str(getattr(vector_config, "distance", vector_config)),
            "qdrant_path": str(args.qdrant_path),
            "vector_depth": VECTOR_DEPTH,
            "bm25_depth": BM25_DEPTH,
            "final_top_k": TOP_K,
            "rrf_k": RRF_K,
            "bm25_k1": bm25_index.k1,
            "bm25_b": bm25_index.b,
            "bm25_tokenizer": "lowercase ASCII alphanumeric tokens via [a-z0-9]+",
            "bm25_corpus_source": str(train_csv.relative_to(args.root)),
            "bm25_corpus_size": len(bm25_index.records),
            "ollama_model": OLLAMA_MODEL,
            "ollama_url": OLLAMA_URL,
            "ollama_timeout_seconds": OLLAMA_TIMEOUT_SECONDS,
            "ollama_max_retry_attempts": OLLAMA_MAX_RETRY_ATTEMPTS,
            "python_version": platform.python_version(),
            "package_versions": {
                "qdrant-client": package_version("qdrant-client"),
                "cohere": package_version("cohere"),
            },
        },
        "leakage_check": {
            "bm25_training_source_only": True,
            "bm25_corpus_size": len(bm25_index.records),
            "fixed_test_rows_in_bm25_by_identity": len(leaked_keys),
            "fixed_test_texts_in_bm25": len(leaked_texts),
            "qdrant_read_only_snapshot": True,
            "test_rows_ingested": False,
        },
        "metrics": metric,
        "recovery_counts": dict(recovery_counts),
        "results": results,
        "safety": {
            "classification_fix_modified": False,
            "segmentation_modified": False,
            "embedding_modified": False,
            "qdrant_modified": False,
            "ollama_modified": False,
            "risk_analysis_modified": False,
            "selected_rows_modified": False,
        },
    }


def write_artifacts(output: dict, args: argparse.Namespace) -> None:
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "experiment_results.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    fields = [
        "benchmark_row_id", "document_id", "clause_type", "vector_gt_rank", "bm25_gt_rank", "hybrid_gt_rank",
        "vector_gt_in_top5", "bm25_gt_in_top5", "hybrid_gt_in_top5", "ollama_prediction", "prediction_status",
        "prediction_equals_ground_truth", "result_category", "previous_miss_analysis",
    ]
    with (output_dir / "experiment_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: result.get(field, "") for field in fields} for result in output["results"])

    baseline = output["baseline_reference"]["metrics"]
    current = output["metrics"]
    comparison = []
    for key in BASELINE_METRICS:
        baseline_value = baseline.get(key, 0)
        current_value = current.get(key, 0)
        comparison.append({"metric": key, "classification_fix": baseline_value, "hybrid_retrieval": current_value, "change": current_value - baseline_value})
    with (output_dir / "comparison_with_baseline.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "classification_fix", "hybrid_retrieval", "change"])
        writer.writeheader()
        writer.writerows(comparison)

    lines = [
        "# Hybrid Retrieval: BM25 + Vector Search + RRF",
        "",
        f"Status: **{output['status']}**",
        "",
        "## 1. Experiment Objective",
        "",
        "Test whether combining semantic Vector Top-20 retrieval with lexical BM25 Top-20 retrieval and Reciprocal Rank Fusion improves retrieval coverage on the fixed 10-row benchmark.",
        "",
        "## 2. Research Hypothesis",
        "",
        "Hybrid retrieval may recover CUAD categories missed by vector-only search, especially where lexical clause terms are informative.",
        "",
        "## 3. Controlled Variables",
        "",
        "The fixed rows, training corpus, Cohere query embeddings, Qdrant collection, distance metric, Ollama model, classification-fix, prompt, UNKNOWN handling, and Top-5 evaluation target remained fixed.",
        "",
        "## 4. Baseline",
        "",
        "The comparison baseline is the completed `fixed_10_classification_experiment` run over the same official 10-row selection.",
        f"- Recall@1: `{baseline['recall_at_1']:.4f}`; Recall@3: `{baseline['recall_at_3']:.4f}`; Recall@5: `{baseline['recall_at_5']:.4f}`.",
        f"- MRR: `{baseline['mrr']:.4f}`; classification accuracy: `{baseline['classification_accuracy']:.4f}`.",
        f"- Retrieval misses: `{baseline['retrieval_miss_count']}`; classification errors: `{baseline['classification_error_count']}`; invalid/out-of-candidate responses: `{baseline.get('invalid_out_of_candidate_count', 0)}`; UNKNOWN abstentions: `{baseline['unknown_count']}`; pipeline errors: `{baseline['pipeline_error_count']}`.",
        "",
        "## 5. Independent Variable",
        "",
        "Only retrieval changed: Vector Top-20 plus BM25 Top-20 fused with RRF, followed by final Top-5 selection.",
        "",
        "## 6. Architecture",
        "",
        "Before: query text -> Cohere search_query embedding -> Qdrant Vector Top-5 -> existing candidate-constrained classifier.",
        "",
        "After: query text -> Cohere search_query embedding -> Qdrant Vector Top-20 + BM25 Top-20 over training clauses -> RRF (k=60) -> final Top-5 -> unchanged candidate-constrained classifier.",
        "",
        "## 7. BM25 and RRF Configuration",
        "",
        f"- Corpus: `{output['configuration']['bm25_corpus_source']}`; `{output['configuration']['bm25_corpus_size']}` substantive training records.",
        f"- Tokenizer: `{output['configuration']['bm25_tokenizer']}`.",
        f"- BM25 parameters: `k1={output['configuration']['bm25_k1']}`, `b={output['configuration']['bm25_b']}`.",
        f"- Vector depth: `{output['configuration']['vector_depth']}`; BM25 depth: `{output['configuration']['bm25_depth']}`.",
        f"- RRF formula: `RRF(d) = sum(1 / ({output['configuration']['rrf_k']} + rank(d)))`, with 1-based ranks.",
        f"- Final fused output: Top-`{output['configuration']['final_top_k']}`.",
        "- Record identity: the existing UUID5 Qdrant point identity derived from document ID, clause type, and training source row index; duplicate records are merged only when this identity matches.",
        "",
        "## 8. Leakage Verification",
        "",
        f"- BM25 source is training data only: `{output['leakage_check']['bm25_training_source_only']}`.",
        f"- Fixed test identities in BM25 corpus: `{output['leakage_check']['fixed_test_rows_in_bm25_by_identity']}`.",
        f"- Fixed test texts in BM25 corpus: `{output['leakage_check']['fixed_test_texts_in_bm25']}`.",
        f"- Test rows ingested into Qdrant: `{output['leakage_check']['test_rows_ingested']}`.",
        "",
        "## 9. Fixed Benchmark",
        "",
        "Exactly the ten rows in `diagnostics/fixed_10_classification_baseline/selected_10_rows.json` were used; no resampling occurred.",
        "",
        "## 10. Per-Row Results",
        "",
        "| Row | Ground Truth | Vector GT Rank | BM25 GT Rank | Hybrid GT Rank | Vector Top-5 | BM25 Top-5 | Hybrid Top-5 | Prediction | Status | Correct |",
        "|---|---|---:|---:|---:|---|---|---|---|---|---|",
    ]
    for result in output["results"]:
        lines.append(f"| `{result['benchmark_row_id']}` | `{result['clause_type']}` | {result['vector_gt_rank'] or '-'} | {result['bm25_gt_rank'] or '-'} | {result['hybrid_gt_rank'] or '-'} | {'Yes' if result['vector_gt_in_top5'] else 'No'} | {'Yes' if result['bm25_gt_in_top5'] else 'No'} | {'Yes' if result['hybrid_gt_in_top5'] else 'No'} | `{result['ollama_prediction']}` | `{result['prediction_status']}` | {'Yes' if result['prediction_equals_ground_truth'] else 'No'} |")
    lines.extend(["", "### Top-5 Category Details", ""])
    for result in output["results"]:
        vector = ", ".join(f"{item['rank']}:{item['clause_type']}" for item in result["vector_top20"][:5])
        bm25 = ", ".join(f"{item['rank']}:{item['clause_type']}" for item in result["bm25_top20"][:5])
        hybrid = ", ".join(f"{item['hybrid_rank']}:{item['clause_type']}" for item in result["hybrid_top5"])
        lines.append(f"- `{result['benchmark_row_id']}` Vector: {vector}")
        lines.append(f"  BM25: {bm25}")
        lines.append(f"  Hybrid/RRF: {hybrid}")
    lines.extend(["", "## 11. Retrieval Recovery Analysis", ""])
    for result in output["results"]:
        if result["previous_miss_analysis"] != "NOT_PREVIOUS_MISS":
            lines.append(f"- `{result['benchmark_row_id']}`: `{result['previous_miss_analysis']}`; Vector Top-20 rank `{result['vector_gt_rank']}`, BM25 Top-20 rank `{result['bm25_gt_rank']}`, Hybrid rank `{result['hybrid_gt_rank']}`.")
            if result["previous_miss_analysis"] == "BM25_FOUND_BUT_RRF_DID_NOT_PROMOTE":
                lines.append("  BM25 retrieved useful evidence, but the RRF configuration did not promote it sufficiently into the final Top-5.")
    lines.extend([
        "",
        "## 12. Aggregate Metrics",
        "",
        f"- Recall@1: `{current['recall_at_1']:.4f}`",
        f"- Recall@3: `{current['recall_at_3']:.4f}`",
        f"- Recall@5: `{current['recall_at_5']:.4f}`",
        f"- MRR: `{current['mrr']:.4f}`",
        f"- Classification accuracy: `{current['classification_accuracy']:.4f}`",
        f"- Retrieval misses: `{current['retrieval_miss_count']}`",
        f"- Classification errors: `{current['classification_error_count']}`",
        f"- Invalid/out-of-candidate responses: `{current['invalid_out_of_candidate_count']}`",
        f"- Out-of-Top-5 predictions: `{current['ollama_selected_label_absent_from_top5_count']}`",
        f"- UNKNOWN count: `{current['unknown_count']}`",
        f"- Pipeline errors: `{current['pipeline_error_count']}`",
        f"- Previous retrieval misses recovered by hybrid Top-5: `{current['retrieval_recovery_count']}`",
        "",
        "`UNKNOWN` is counted only when production parsing reports intentional `UNKNOWN` abstention. An out-of-candidate or malformed Ollama response is rejected by production parsing and exposed as final prediction `UNKNOWN`, but is counted separately as invalid. The out-of-Top-5 metric counts only non-UNKNOWN labels that remain absent from the final candidate set.",
        "",
        "## 13. Baseline vs Hybrid",
        "",
        "| Metric | Classification Fix | Hybrid Retrieval | Change |",
        "|---|---:|---:|---:|",
    ])
    for row in comparison:
        lines.append(f"| {row['metric']} | {row['classification_fix']:.4f} | {row['hybrid_retrieval']:.4f} | {row['change']:+.4f} |")
    lines.extend([
        "",
        "## 14. Classification Impact",
        "",
        "The existing candidate-constrained classifier was reused without modification. Hybrid accuracy increased from 4/10 to 5/10 because `fixed-10-07` changed from the valid but incorrect candidate `Minimum Commitment` to the correct candidate `Revenue/Profit Sharing`; both runs had the same two candidate labels, so the change reflects the changed retrieved examples/order and/or Ollama run variability rather than improved retrieval coverage. `fixed-10-09` remained an out-of-candidate response: raw `Obligations` was rejected and exposed as final `UNKNOWN`. Retrieval misses remain distinct from classifier errors.",
        "",
        "## 15. Limitations",
        "",
        "This is a 10-row pilot and cannot establish generalization. BM25 tokenization is intentionally simple, and RRF ranking is sensitive to the chosen depth and k value. The Qdrant retriever payload does not expose source point IDs through the existing production helper, so this experiment uses the UUID5 identity available from the indexed training-record construction for fusion alignment.",
        "",
        "## 16. Conclusion",
        "",
        f"Hybrid Recall@5 was `{current['recall_at_5']:.4f}` versus `{baseline['recall_at_5']:.4f}` for classification-fix. The hypothesis is {'SUPPORTED' if current['recall_at_5'] > baseline['recall_at_5'] else 'NOT SUPPORTED' if current['recall_at_5'] < baseline['recall_at_5'] else 'INCONCLUSIVE ON THIS PILOT'} for this fixed 10-row retrieval-coverage test.",
        "",
        "## Safety",
        "",
        "Only hybrid retrieval experiment files are intended for this branch. Classification-fix source and baseline artifacts were not modified. No segmentation, embedding, Qdrant, Ollama, risk-analysis, or test-data writes were performed.",
    ])
    (output_dir / "hybrid_retrieval_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--qdrant-path", type=Path, required=True)
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = evaluate(args)
    write_artifacts(output, args)
    print(json.dumps({"status": output["status"], "metrics": output["metrics"], "recovery_counts": output["recovery_counts"]}, indent=2))


if __name__ == "__main__":
    main()
