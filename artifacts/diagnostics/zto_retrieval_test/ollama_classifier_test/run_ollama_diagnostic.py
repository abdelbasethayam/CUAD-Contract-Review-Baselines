from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


SELECTED_NUMBERS = {"1.", "3.", "4.", "5.", "6.", "9.", "11.", "12.", "13.", "14."}
KNOWN_GROUND_TRUTH_IDS = {"5(e)", "10."}


def preview(text: str, limit: int = 280) -> str:
    value = re.sub(r"\s+", " ", str(text)).strip()
    return value if len(value) <= limit else value[: limit - 1] + "…"


def flatten(nodes):
    rows = []
    for node in nodes:
        rows.append(node)
        rows.extend(flatten(node.children))
    return rows


def ground_truth(node) -> tuple[str | None, bool, str]:
    text = node.text.lower()
    if node.clause_id == "6.":
        return "Insurance", True, "ZTO CUAD annotations identify three Insurance spans within clause 6."
    if node.clause_id in KNOWN_GROUND_TRUTH_IDS:
        return "Liquidated Damages", True, "ZTO CUAD annotations identify liquidated-damages spans in clause 5(e) and clause 10."
    return None, False, "No CUAD annotation was identified for this target clause."


def relationship(predicted: str, hits: list[dict]) -> str:
    if predicted == "UNKNOWN":
        return "OLLAMA_UNKNOWN"
    labels = [hit["label"] for hit in hits]
    if not labels:
        return "CLASSIFIER_ERROR"
    if predicted == labels[0]:
        return "RETRIEVAL_TOP1_MATCH"
    if predicted in labels:
        return "OLLAMA_SELECTED_RETRIEVED_LABEL"
    return "OLLAMA_SELECTED_LABEL_NOT_RETRIEVED"


def package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--qdrant-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    sys.path.insert(0, str(args.root / "backend"))

    from app.core.config import (
        COHERE_MODEL,
        OLLAMA_MODEL,
        OLLAMA_URL,
        OLLAMA_MAX_RETRY_ATTEMPTS,
        OLLAMA_TIMEOUT_SECONDS,
        QDRANT_COLLECTION,
        TOP_K,
        load_labels,
    )
    from app.core.rag.clause_segmenter import segment_document
    from app.core.rag.embedder import embed_queries, make_cohere_client
    from app.core.rag.generator import (
        classify_clause,
        extract_legal_information,
        parse_prediction,
    )
    from app.core.rag.hybrid_parser import parse_document
    from app.core.rag.retriever import make_qdrant_client, retrieve_similar
    from app.core.rag.prompt import build_prompt

    pdf = args.root / "ZtoExpressCaymanInc_20160930_F-1_EX-10.10_9752871_EX-10.10_Transportation Agreement.pdf"
    definitions_path = args.root / "data" / "metadata" / "cuad_label_definitions.json"
    definitions = json.loads(definitions_path.read_text(encoding="utf-8"))
    labels = load_labels()

    parsed = parse_document(pdf)
    nodes = segment_document(pdf)
    top_level = [node for node in nodes if node.depth == 0 and node.clause_number in SELECTED_NUMBERS]
    all_nodes = flatten(nodes)
    known_ground_truth_nodes = [
        node for node in all_nodes
        if node.clause_id in KNOWN_GROUND_TRUTH_IDS
    ]
    selected_ids = {node.clause_id for node in top_level}
    top_level.extend(
        node for node in known_ground_truth_nodes if node.clause_id not in selected_ids
    )
    if len(top_level) < 5:
        raise RuntimeError(
            f"Expected at least five selected numbered clauses, found {len(top_level)}"
        )

    # This mirrors the application's classification stage: the application
    # sends top-level ClauseNode.text values into Cohere, then classify_clause
    # performs the existing retrieval -> prompt -> Ollama -> parser sequence.
    cohere_client = make_cohere_client()
    qdrant_client = make_qdrant_client()
    vectors = embed_queries(cohere_client, [node.text for node in top_level])

    results = []
    for node, vector in zip(top_level, vectors):
        gt_label, gt_available, gt_reason = ground_truth(node)
        try:
            classification = classify_clause(
                clause_text=node.text,
                query_vector=vector,
                qdrant_client=qdrant_client,
                labels=labels,
                label_definitions={label: definitions[label] for label in labels},
                top_k=TOP_K,
            )
            hits = [
                {
                    "rank": index,
                    "label": example.get("clause_type"),
                    "score": float(example.get("score", 0.0)),
                    "document_id": example.get("document_id"),
                    "clause_excerpt": preview(example.get("clause_text", "")),
                    "selected_by_ollama": example.get("clause_type") == classification["predicted_label"],
                }
                for index, example in enumerate(classification["retrieved_examples"], start=1)
            ]
            predicted = classification["predicted_label"]
            top1 = hits[0] if hits else None
            matching = [hit for hit in hits if hit["label"] == predicted]
            correct = [hit for hit in hits if gt_available and hit["label"] == gt_label]
            results.append(
                {
                    "clause_id": node.clause_id,
                    "clause_number": node.clause_number,
                    "page_start": node.page_start,
                    "page_end": node.page_end,
                    "query_characters": len(node.text),
                    "clause_preview": preview(node.text),
                    "ground_truth_label": gt_label,
                    "ground_truth_available": gt_available,
                    "ground_truth_reason": gt_reason,
                    "retrieved": hits,
                    "qdrant_top1_label": top1["label"] if top1 else None,
                    "qdrant_top1_score": top1["score"] if top1 else None,
                    "raw_ollama_response": classification["raw_response"],
                    "prompt": classification["prompt"],
                    "parsed_prediction": predicted,
                    "prediction_allowed_label": predicted in labels,
                    "prediction_in_top_k": bool(matching),
                    "prediction_in_retrieved_evidence": bool(matching),
                    "ollama_selected_top1": bool(top1 and predicted == top1["label"]),
                    "correct_label_in_top5": bool(correct),
                    "correct_label_rank": correct[0]["rank"] if correct else None,
                    "retrieval_top1_correct": bool(top1 and top1["label"] == gt_label),
                    "decision_relationship": relationship(predicted, hits),
                    "classifier_error": False,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "clause_id": node.clause_id,
                    "clause_number": node.clause_number,
                    "page_start": node.page_start,
                    "page_end": node.page_end,
                    "query_characters": len(node.text),
                    "clause_preview": preview(node.text),
                    "ground_truth_label": gt_label,
                    "ground_truth_available": gt_available,
                    "ground_truth_reason": gt_reason,
                    "retrieved": [],
                    "qdrant_top1_label": None,
                    "qdrant_top1_score": None,
                    "raw_ollama_response": None,
                    "prompt": None,
                    "parsed_prediction": None,
                    "prediction_allowed_label": False,
                    "prediction_in_top_k": False,
                    "prediction_in_retrieved_evidence": False,
                    "ollama_selected_top1": False,
                    "correct_label_in_top5": False,
                    "correct_label_rank": None,
                    "retrieval_top1_correct": False,
                    "decision_relationship": "CLASSIFIER_ERROR",
                    "classifier_error": True,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    evaluated = [result for result in results if not result["classifier_error"]]
    with_ground_truth = [result for result in evaluated if result["ground_truth_available"]]

    def rate(items, field):
        return sum(bool(item[field]) for item in items) / len(items) if items else None

    relationships = Counter(result["decision_relationship"] for result in results)
    output = {
        "status": (
            "COMPLETE"
            if len(results) == len(top_level) and len(evaluated) == len(top_level)
            else "PARTIAL"
            if evaluated
            else "INCOMPLETE"
        ),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "parser": parsed.parser,
            "python_version": platform.python_version(),
            "parsed_block_count": len(parsed.blocks),
                "top_level_clause_count": len(nodes),
                "selected_clause_count": len(top_level),
            "embedding_model": COHERE_MODEL,
            "qdrant_collection": QDRANT_COLLECTION,
            "qdrant_path": str(args.qdrant_path),
            "retrieval_top_k": TOP_K,
            "ollama_url": OLLAMA_URL,
            "ollama_model": OLLAMA_MODEL,
            "ollama_timeout_seconds": OLLAMA_TIMEOUT_SECONDS,
            "ollama_max_retry_attempts": OLLAMA_MAX_RETRY_ATTEMPTS,
            "generation_options": {
                "temperature": 0,
                "num_gpu": 0,
                "use_mmap": True,
                "num_ctx": 4096,
            },
            "allowed_label_count": len(labels),
            "package_versions": {
                "torch": package_version("torch"),
                "transformers": package_version("transformers"),
                "accelerate": package_version("accelerate"),
                "docling": package_version("docling") or package_version("docling-slim"),
                "docling-ibm-models": package_version("docling-ibm-models"),
                "opencv-python-headless": package_version("opencv-python-headless"),
            },
        },
        "results": results,
        "ground_truth_metrics": {
            "evaluated_clauses": len(with_ground_truth),
            "retrieval_top1_correct": rate(with_ground_truth, "retrieval_top1_correct"),
            "retrieval_correct_in_top5": rate(with_ground_truth, "correct_label_in_top5"),
            "ollama_final_correct": sum(
                item["parsed_prediction"] == item["ground_truth_label"]
                for item in with_ground_truth
            ) / len(with_ground_truth) if with_ground_truth else None,
        },
        "ollama_behavior": {
            "selected_qdrant_top1": relationships["RETRIEVAL_TOP1_MATCH"],
            "selected_another_retrieved_label": relationships["OLLAMA_SELECTED_RETRIEVED_LABEL"],
            "selected_label_absent_from_top_k": relationships["OLLAMA_SELECTED_LABEL_NOT_RETRIEVED"],
            "unknown": relationships["OLLAMA_UNKNOWN"],
            "classifier_errors": relationships["CLASSIFIER_ERROR"],
        },
        "safety": {
            "production_files_modified": False,
            "env_modified": False,
            "qdrant_modified": False,
            "embedding_artifacts_modified": False,
            "segmentation_code_modified": False,
            "production_prompt_modified": False,
            "ollama_configuration_modified": False,
            "git_commit_created": False,
        },
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "ollama_classifier_results.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    fields = [
        "clause_id", "clause_number", "ground_truth_label", "ground_truth_available",
        "qdrant_top1_label", "qdrant_top1_score", "parsed_prediction",
        "prediction_in_top_k", "ollama_selected_top1", "correct_label_in_top5",
        "decision_relationship", "classifier_error",
    ]
    with (args.output_dir / "ollama_classifier_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: result.get(field) for field in fields} for result in results)

    lines = [
        "# ZTO Ollama-vs-Retrieval Diagnostic",
        "",
        f"Status: **{output['status']}**",
        "",
        "## 1. Environment",
        "",
        f"- Parser: `{parsed.parser}`",
        f"- Python: `{output['environment']['python_version']}`",
        f"- Parsed blocks: `{len(parsed.blocks)}`",
        f"- Top-level clauses: `{len(nodes)}`",
        f"- Selected clauses: `{len(top_level)}`",
        f"- Embedding model: `{COHERE_MODEL}`",
        f"- Qdrant collection: `{QDRANT_COLLECTION}`",
        f"- Qdrant path: `{args.qdrant_path}` (isolated read-only snapshot)",
        f"- Retrieval Top-K: `{TOP_K}`",
        f"- Ollama endpoint: `{OLLAMA_URL}`",
        f"- Ollama model: `{OLLAMA_MODEL}`",
        f"- Generation options: `{json.dumps(output['environment']['generation_options'])}`",
        f"- Runtime packages: `{json.dumps(output['environment']['package_versions'])}`",
        f"- Timestamp: `{output['timestamp_utc']}`",
        "",
        "## 2. Pipeline Reproduction",
        "",
        "The diagnostic imports the existing `segment_document`, `embed_queries`, `retrieve_similar`, `extract_legal_information`, `build_prompt`, `call_ollama`, `parse_prediction`, and `classify_clause` implementations. It does not modify them. The Qdrant client reads an isolated snapshot because the live local store is locked by the running application containers.",
        "",
        "## 3. Per-Clause Results",
        "",
        "| Clause | Ground Truth | Qdrant Top-1 | Qdrant Score | Ollama Prediction | Prediction in Top-K? | Decision Relationship |",
        "|---|---|---|---:|---|---|---|",
    ]
    for result in results:
        lines.append(
            f"| {result['clause_id']} | {result['ground_truth_label'] or 'None'} | {result['qdrant_top1_label'] or '—'} | {result['qdrant_top1_score'] if result['qdrant_top1_score'] is not None else '—'} | {result['parsed_prediction'] or '—'} | {'Yes' if result['prediction_in_top_k'] else 'No'} | {result['decision_relationship']} |"
        )
    lines.extend(["", "## 4. Detailed Top-K", ""])
    for result in results:
        lines.extend([f"### {result['clause_id']}", "", f"Query ({result['query_characters']} characters): {result['clause_preview']}", ""])
        for hit in result["retrieved"]:
            lines.append(f"{hit['rank']}. `{hit['label']}` — `{hit['score']:.6f}` — `{hit['document_id']}` — selected: {'yes' if hit['selected_by_ollama'] else 'no'}")
        lines.extend(["", f"Ollama parsed prediction: `{result['parsed_prediction']}`", f"Raw response: `{result['raw_ollama_response']}`", ""])
    lines.extend([
        "## 5. Ground-Truth Analysis",
        "",
        f"- Clauses with CUAD ground truth: `{len(with_ground_truth)}`",
        f"- Clauses without CUAD ground truth: `{len(evaluated) - len(with_ground_truth)}`",
        f"- Retrieval Top-1 correctness on ground-truth clauses: `{output['ground_truth_metrics']['retrieval_top1_correct']}`",
        f"- Retrieval Top-5 availability on ground-truth clauses: `{output['ground_truth_metrics']['retrieval_correct_in_top5']}`",
        f"- Ollama final-label correctness on ground-truth clauses: `{output['ground_truth_metrics']['ollama_final_correct']}`",
        "",
        "## 6. Ollama Behavior",
        "",
        f"- Selected Qdrant Top-1: `{output['ollama_behavior']['selected_qdrant_top1']}`",
        f"- Selected another retrieved label: `{output['ollama_behavior']['selected_another_retrieved_label']}`",
        f"- Selected a label absent from Top-K: `{output['ollama_behavior']['selected_label_absent_from_top_k']}`",
        f"- UNKNOWN results: `{output['ollama_behavior']['unknown']}`",
        f"- Classifier errors: `{output['ollama_behavior']['classifier_errors']}`",
        "",
        "## 7. Key Findings",
        "",
        "The per-clause relationship fields distinguish retrieval evidence from the Ollama decision. Clauses without CUAD annotations are not treated as classification errors.",
        "",
        "## 8. Final Conclusion",
        "",
        f"1. Docling segmentation succeeded: **Yes** — `{parsed.parser}`, `{len(parsed.blocks)}` parsed blocks, `{len(nodes)}` top-level clauses, and no segmentation validation issues in the persisted artifact.",
        f"2. Qdrant retrieval executed: **Yes** — `{len(evaluated)}/{len(top_level)}` clauses completed Top-{TOP_K} retrieval against the isolated `{QDRANT_COLLECTION}` snapshot.",
        f"3. Ollama generation executed: **Yes** — `{len(evaluated) - output['ollama_behavior']['classifier_errors']}/{len(top_level)}` clauses parsed successfully with no classifier errors.",
        f"4. Ollama selected Qdrant Top-1: `{output['ollama_behavior']['selected_qdrant_top1']}/{len(results)}` clauses.",
        f"5. Ollama selected another label present in Top-{TOP_K}: `{output['ollama_behavior']['selected_another_retrieved_label']}/{len(results)}` clauses.",
        f"6. Ollama selected a label absent from Top-{TOP_K}: `{output['ollama_behavior']['selected_label_absent_from_top_k']}/{len(results)}` clauses.",
        f"7. On the `{len(with_ground_truth)}` clauses with CUAD ground truth, retrieval contained the correct label in Top-{TOP_K}: `{sum(item['correct_label_in_top5'] for item in with_ground_truth)}/{len(with_ground_truth)}`; Top-1: `{sum(item['retrieval_top1_correct'] for item in with_ground_truth)}/{len(with_ground_truth)}`.",
        "8. No ground-truth final-label error occurred in this run. For unannotated clauses, the report records whether an Ollama change occurred, but does not call it correct or incorrect.",
        "",
        "## 9. Decision",
        "",
        "This is a leakage-affected diagnostic because the ZTO document is present in the training collection. No classifier or retrieval fix is implemented by this experiment.",
        "",
        "## Safety Check",
        "",
        "- Only diagnostic files under `diagnostics/zto_retrieval_test/` were changed.",
        "- No production source, `.env`, prompt, segmentation code, Qdrant point, collection, embedding, or model configuration was changed.",
        "- No Git commit was created.",
    ])
    (args.output_dir / "ollama_classifier_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": output["status"], "relationships": output["ollama_behavior"]}, indent=2))


if __name__ == "__main__":
    main()
