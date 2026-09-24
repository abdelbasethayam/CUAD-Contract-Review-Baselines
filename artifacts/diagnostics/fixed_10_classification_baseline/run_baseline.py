from __future__ import annotations

import argparse
import csv
import json
import platform
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


SELECTION_SEED = 20260910
TOP_K = 5
EXCLUDED_METADATA_LABELS = {
    "Document Name",
    "Parties",
    "Agreement Date",
    "Effective Date",
    "Expiration Date",
}
SOURCE_RELATIVE_PATH = Path("data/splits/test/master_clauses_test.csv")


def package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def read_source_rows(source_path: Path) -> list[dict]:
    rows = []
    with source_path.open("r", newline="", encoding="utf-8-sig") as handle:
        for original_row_index, row in enumerate(csv.DictReader(handle), start=2):
            row["original_row_index"] = original_row_index
            rows.append(row)
    return rows


def eligible_rows(rows: list[dict]) -> list[dict]:
    return [
        row
        for row in rows
        if row.get("clause_type")
        and row.get("clause_type") not in EXCLUDED_METADATA_LABELS
        and row.get("clause_text", "").strip()
    ]


def select_fixed_rows(rows: list[dict]) -> list[dict]:
    """Select one deterministic row from each of ten shuffled categories."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in eligible_rows(rows):
        grouped[row["clause_type"]].append(row)

    rng = random.Random(SELECTION_SEED)
    categories = sorted(grouped)
    rng.shuffle(categories)
    selected = []
    for category in categories[:10]:
        candidates = list(grouped[category])
        candidates.sort(key=lambda item: int(item["original_row_index"]))
        selected.append(rng.choice(candidates).copy())

    if len(selected) != 10 or len({row["clause_type"] for row in selected}) != 10:
        raise RuntimeError("Fixed selection did not produce ten diverse rows.")
    return selected


def row_payload(row: dict, selection_rank: int) -> dict:
    return {
        "benchmark_row_id": f"fixed-10-{selection_rank:02d}",
        "selection_rank": selection_rank,
        "original_row_index": int(row["original_row_index"]),
        "document_id": row.get("document_id", ""),
        "clause_type": row.get("clause_type", ""),
        "clause_text": row.get("clause_text", ""),
        "answer": row.get("answer", ""),
        "is_metadata": row.get("is_metadata", ""),
    }


def load_or_create_selection(source_path: Path, output_dir: Path) -> tuple[list[dict], dict]:
    selection_path = output_dir / "selected_10_rows.json"
    source_rows = read_source_rows(source_path)

    if selection_path.exists():
        metadata = json.loads(selection_path.read_text(encoding="utf-8"))
        selected = metadata.get("rows", [])
        if len(selected) != 10:
            raise RuntimeError("Existing selected_10_rows.json does not contain exactly 10 rows.")
        return selected, metadata

    selected = [row_payload(row, rank) for rank, row in enumerate(select_fixed_rows(source_rows), start=1)]
    metadata = {
        "benchmark_id": "fixed_10_classification_baseline",
        "selection_seed": SELECTION_SEED,
        "selection_strategy": "One reproducibly sampled row from each of ten shuffled non-metadata CUAD categories.",
        "source_test_csv": str(SOURCE_RELATIVE_PATH),
        "source_absolute_path_at_creation": str(source_path),
        "source_row_count": len(source_rows),
        "eligible_row_count": len(eligible_rows(source_rows)),
        "excluded_metadata_labels": sorted(EXCLUDED_METADATA_LABELS),
        "row_count": 10,
        "rows": selected,
    }
    return selected, metadata


def write_selection_artifacts(output_dir: Path, metadata: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "selected_10_rows.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    fields = [
        "benchmark_row_id",
        "selection_rank",
        "original_row_index",
        "document_id",
        "clause_type",
        "clause_text",
        "answer",
        "is_metadata",
    ]
    with (output_dir / "selected_10_rows.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in metadata["rows"])


def preview(text: str, limit: int = 240) -> str:
    value = " ".join(str(text).split())
    return value if len(value) <= limit else value[: limit - 1] + "..."


def select_rank(label: str | None, hits: list[dict]) -> int | None:
    for hit in hits:
        if hit.get("clause_type") == label:
            return int(hit["rank"])
    return None


def evaluate(selected: list[dict], args: argparse.Namespace) -> dict:
    sys.path.insert(0, str(args.root / "backend"))

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

    definitions_path = args.root / "data" / "metadata" / "cuad_label_definitions.json"
    definitions = json.loads(definitions_path.read_text(encoding="utf-8"))
    labels = load_labels()
    cohere_client = make_cohere_client()
    qdrant_client = make_qdrant_client()
    collection = qdrant_client.get_collection(collection_name=QDRANT_COLLECTION)
    vector_config = collection.config.params.vectors
    vector_size = getattr(vector_config, "size", None)
    distance = str(getattr(vector_config, "distance", vector_config))
    query_vectors = embed_queries(cohere_client, [row["clause_text"] for row in selected])

    results = []
    for row, query_vector in zip(selected, query_vectors):
        ground_truth = row["clause_type"]
        try:
            # Record the production retriever output before invoking the exact
            # production classifier, which performs the same retrieval again.
            retrieved = retrieve_similar(qdrant_client, query_vector, top_k=TOP_K)
            hits = [
                {
                    "rank": rank,
                    "score": float(hit.get("score", 0.0)),
                    "document_id": hit.get("document_id"),
                    "clause_type": hit.get("clause_type"),
                    "clause_text": hit.get("clause_text", ""),
                }
                for rank, hit in enumerate(retrieved, start=1)
            ]
            classification = classify_clause(
                clause_text=row["clause_text"],
                query_vector=query_vector,
                qdrant_client=qdrant_client,
                labels=labels,
                label_definitions={label: definitions[label] for label in labels},
                top_k=TOP_K,
            )
            predicted = classification["predicted_label"]
            gt_rank = select_rank(ground_truth, hits)
            in_top5 = gt_rank is not None
            prediction_in_top5 = any(hit["clause_type"] == predicted for hit in hits)
            selected_top1 = bool(hits and predicted == hits[0]["clause_type"])
            selected_another = bool(prediction_in_top5 and not selected_top1)
            selected_absent = not prediction_in_top5
            if not in_top5:
                error_category = "RETRIEVAL_MISS"
            elif predicted != ground_truth:
                error_category = "CLASSIFICATION_ERROR"
            else:
                error_category = "CORRECT"
            results.append(
                {
                    **row,
                    "query_embedding_dimension": len(query_vector),
                    "retrieved": hits,
                    "ground_truth_rank": gt_rank,
                    "ground_truth_in_top5": in_top5,
                    "qdrant_top1_label": hits[0]["clause_type"] if hits else None,
                    "qdrant_top1_score": hits[0]["score"] if hits else None,
                    "raw_ollama_response": classification["raw_response"],
                    "ollama_prediction": predicted,
                    "prediction_equals_ground_truth": predicted == ground_truth,
                    "ollama_selected_top1": selected_top1,
                    "ollama_selected_another_topk_category": selected_another,
                    "ollama_selected_label_absent_from_top5": selected_absent,
                    "unsupported_or_ambiguous_behavior": selected_absent,
                    "error_category": error_category,
                    "classifier_error": False,
                }
            )
        except Exception as exc:
            results.append(
                {
                    **row,
                    "query_embedding_dimension": len(query_vector),
                    "retrieved": [],
                    "ground_truth_rank": None,
                    "ground_truth_in_top5": False,
                    "qdrant_top1_label": None,
                    "qdrant_top1_score": None,
                    "raw_ollama_response": None,
                    "ollama_prediction": None,
                    "prediction_equals_ground_truth": False,
                    "ollama_selected_top1": False,
                    "ollama_selected_another_topk_category": False,
                    "ollama_selected_label_absent_from_top5": False,
                    "unsupported_or_ambiguous_behavior": False,
                    "error_category": "PIPELINE_ERROR",
                    "classifier_error": True,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    denominator = len(selected)
    recall = {
        f"recall_at_{k}": sum(
            bool(result["ground_truth_rank"] and result["ground_truth_rank"] <= k)
            for result in results
        ) / denominator
        for k in (1, 3, 5)
    }
    mrr = sum(
        1 / result["ground_truth_rank"] if result["ground_truth_rank"] else 0
        for result in results
    ) / denominator
    counts = Counter(result["error_category"] for result in results)
    metrics = {
        **recall,
        "mrr": mrr,
        "classification_accuracy": sum(
            result["prediction_equals_ground_truth"] for result in results
        ) / denominator,
        "ground_truth_in_top5_count": sum(result["ground_truth_in_top5"] for result in results),
        "ground_truth_in_top5_ollama_selected_another_count": sum(
            result["ground_truth_in_top5"] and not result["prediction_equals_ground_truth"]
            for result in results
        ),
        "ollama_selected_label_absent_from_top5_count": sum(
            result["ollama_selected_label_absent_from_top5"] for result in results
        ),
        "retrieval_miss_count": counts["RETRIEVAL_MISS"],
        "classification_error_count": counts["CLASSIFICATION_ERROR"],
        "pipeline_error_count": counts["PIPELINE_ERROR"],
        "correct_count": counts["CORRECT"],
    }
    output = {
        "status": "COMPLETE" if not counts["PIPELINE_ERROR"] else "PARTIAL",
        "benchmark_id": "fixed_10_classification_baseline",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "selection": {
            "seed": SELECTION_SEED,
            "source_test_csv": str(SOURCE_RELATIVE_PATH),
            "row_count": len(selected),
        },
        "environment": {
            "python_version": platform.python_version(),
            "embedding_model": COHERE_MODEL,
            "embedding_dimension": vector_size or (len(query_vectors[0]) if query_vectors else None),
            "qdrant_collection": QDRANT_COLLECTION,
            "qdrant_path": str(args.qdrant_path),
            "qdrant_distance": distance,
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
        "results": results,
        "safety": {
            "production_files_modified": False,
            "segmentation_modified": False,
            "embedding_artifacts_modified": False,
            "qdrant_modified": False,
            "env_modified": False,
            "ollama_modified": False,
            "risk_analysis_modified": False,
            "git_commit_created": False,
        },
    }
    return output


def write_results(output: dict, output_dir: Path, selection_metadata: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "baseline_results.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    fields = [
        "benchmark_row_id", "selection_rank", "document_id", "clause_type",
        "ground_truth_rank", "ground_truth_in_top5", "qdrant_top1_label",
        "qdrant_top1_score", "ollama_prediction", "prediction_equals_ground_truth",
        "ollama_selected_top1", "ollama_selected_another_topk_category",
        "ollama_selected_label_absent_from_top5", "error_category", "classifier_error",
    ]
    with (output_dir / "baseline_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: result.get(field, "") for field in fields} for result in output["results"])

    metrics = output["metrics"]
    environment = output["environment"]
    lines = [
        "# Fixed 10-Row CUAD Classification/Retrieval Baseline",
        "",
        f"Status: **{output['status']}**",
        "",
        "This is a read-only baseline of the current pipeline. It does not modify production code, segmentation, embeddings, Qdrant, Ollama, prompts, or risk analysis.",
        "",
        "## Selection",
        "",
        f"- Fixed seed: `{SELECTION_SEED}`",
        f"- Source: `{SOURCE_RELATIVE_PATH}`",
        f"- Source rows: `{selection_metadata['source_row_count']}`; eligible rows: `{selection_metadata['eligible_row_count']}`",
        "- Metadata categories excluded: `Document Name`, `Parties`, `Agreement Date`, `Effective Date`, `Expiration Date`",
        "- Future runs must reuse `selected_10_rows.json`; this runner does not resample when that file exists.",
        "",
        "### Exact Selected Rows",
        "",
        "| Rank | Stable ID | Original Row | Document ID | Ground Truth | Clause Text |",
        "|---:|---|---:|---|---|---|",
    ]
    for row in selection_metadata["rows"]:
        lines.append(
            f"| {row['selection_rank']} | `{row['benchmark_row_id']}` | {row['original_row_index']} | `{row['document_id']}` | `{row['clause_type']}` | {row['clause_text'].replace('|', '\\|')} |"
        )
    lines.extend([
        "",
        "## Environment",
        "",
        f"- Python: `{environment['python_version']}`",
        f"- Cohere query embedding model: `{environment['embedding_model']}`",
        f"- Embedding dimension: `{environment['embedding_dimension']}`",
        f"- Qdrant collection: `{environment['qdrant_collection']}`",
        f"- Qdrant distance: `{environment['qdrant_distance']}`",
        f"- Qdrant path: `{environment['qdrant_path']}` (isolated read-only snapshot)",
        f"- Retrieval Top-K: `{environment['retrieval_top_k']}`",
        f"- Ollama endpoint: `{environment['ollama_url']}`",
        f"- Ollama model: `{environment['ollama_model']}`",
        f"- Runtime packages: `{json.dumps(environment['package_versions'])}`",
        "",
        "## Aggregate Metrics",
        "",
        f"- Recall@1: **{metrics['recall_at_1']:.4f}**",
        f"- Recall@3: **{metrics['recall_at_3']:.4f}**",
        f"- Recall@5: **{metrics['recall_at_5']:.4f}**",
        f"- MRR: **{metrics['mrr']:.4f}**",
        f"- Final classification accuracy: **{metrics['classification_accuracy']:.4f}** ({metrics['correct_count']}/10)",
        f"- Ground truth in Top-5 but Ollama selected another category: **{metrics['ground_truth_in_top5_ollama_selected_another_count']}**",
        f"- Ollama selected a category absent from Top-5: **{metrics['ollama_selected_label_absent_from_top5_count']}**",
        "",
        "## Error Breakdown",
        "",
        f"- Retrieval miss (ground truth absent from Top-5): **{metrics['retrieval_miss_count']}**",
        f"- Classification error (ground truth in Top-5, Ollama prediction differs): **{metrics['classification_error_count']}**",
        f"- Other/unsupported behavior (prediction absent from Top-5): **{metrics['ollama_selected_label_absent_from_top5_count']}**",
        f"- Pipeline errors: **{metrics['pipeline_error_count']}**",
        "",
        "## Per-Row Results",
        "",
        "| Row | Ground Truth | Qdrant Top-1 | Ollama Prediction | GT Rank | GT in Top-5 | Relationship |",
        "|---|---|---|---|---:|---|---|",
    ])
    for result in output["results"]:
        lines.append(
            f"| `{result['benchmark_row_id']}` | `{result['clause_type']}` | `{result['qdrant_top1_label']}` | `{result['ollama_prediction']}` | {result['ground_truth_rank'] or '-'} | {'Yes' if result['ground_truth_in_top5'] else 'No'} | `{result['error_category']}` |"
        )
    for result in output["results"]:
        lines.extend([
            "",
            f"### {result['benchmark_row_id']} — {result['clause_type']}",
            "",
            f"Clause: {result['clause_text']}",
            "",
            "Top-5 retrieved results:",
            "",
            "| Rank | Score | Document ID | Category | Clause Text |",
            "|---:|---:|---|---|---|",
        ])
        for hit in result["retrieved"]:
            lines.append(
                f"| {hit['rank']} | {hit['score']:.6f} | `{hit['document_id']}` | `{hit['clause_type']}` | {preview(hit['clause_text']).replace('|', '\\|')} |"
            )
        lines.extend([
            "",
            f"Ollama raw response: `{result['raw_ollama_response']}`",
            f"Ollama selected Top-1: **{result['ollama_selected_top1']}**",
            f"Ollama selected another Top-K category: **{result['ollama_selected_another_topk_category']}**",
            f"Ollama selected category absent from Top-K: **{result['ollama_selected_label_absent_from_top5']}**",
        ])
    lines.extend([
        "",
        "## Decision",
        "",
        "This artifact is the fixed reference baseline for future retrieval/classification experiments. The benchmark exposes retrieval misses separately from Ollama classification changes. No system change is recommended from this baseline alone.",
        "",
        "## Safety Check",
        "",
        "- Only files under `diagnostics/fixed_10_classification_baseline/` were created or modified by this benchmark.",
        "- The source test CSV was read but not modified.",
        "- The Qdrant train collection was queried through an isolated read-only snapshot; no points or collections were written.",
        "- No production source, segmentation code, embedding artifact, `.env`, Ollama model/configuration, prompt, or risk-analysis logic was changed.",
        "- No Git commit was created.",
    ])
    (output_dir / "baseline_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--qdrant-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    source_path = args.root / SOURCE_RELATIVE_PATH
    selected, selection_metadata = load_or_create_selection(source_path, args.output_dir)
    write_selection_artifacts(args.output_dir, selection_metadata)
    output = evaluate(selected, args)
    write_results(output, args.output_dir, selection_metadata)
    print(json.dumps({"status": output["status"], "metrics": output["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
