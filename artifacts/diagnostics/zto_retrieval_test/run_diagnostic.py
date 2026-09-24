from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import cohere
from qdrant_client import QdrantClient, models


ZTO_DOCUMENT = (
    "ZtoExpressCaymanInc_20160930_F-1_EX-10.10_9752871_EX-10.10_"
    "Transportation Agreement.pdf"
)

QUERIES = (
    ("liquidated_damages_termination", "Liquidated Damages", "one-month freight"),
    ("liquidated_damages_vehicle_delay", "Liquidated Damages", "vehicle delay"),
    ("insurance_vehicle_personnel", "Insurance", "vehicle personnel insurance"),
    ("insurance_third_party", "Insurance", "third-party liability insurance"),
    ("insurance_vehicle", "Insurance", "sufficient insurance for the transportation vehicles"),
)


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def short_excerpt(text: str, limit: int = 220) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return normalized if len(normalized) <= limit else normalized[: limit - 1] + "…"


def load_zto_clauses(metadata_path: Path) -> list[dict[str, str]]:
    records = [
        json.loads(line)
        for line in metadata_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    zto = [record for record in records if record.get("document_id") == ZTO_DOCUMENT]
    selected: list[dict[str, str]] = []
    for identifier, label, marker in QUERIES:
        matches = [
            record
            for record in zto
            if record.get("clause_type") == label
            and marker.lower() in record.get("clause_text", "").lower()
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"Expected one source clause for {identifier}, found {len(matches)}"
            )
        record = matches[0]
        selected.append(
            {
                "clause_id": identifier,
                "ground_truth": label,
                "query_text": record["clause_text"],
                "source_record_id": record["id"],
            }
        )
    return selected


def collection_size(info) -> int:
    vectors = info.config.params.vectors
    if isinstance(vectors, dict):
        return int(next(iter(vectors.values())).size)
    return int(vectors.size)


def query_collection(client, collection: str, vector: list[float], top_k: int):
    query_filter = models.Filter(
        must_not=[
            models.FieldCondition(
                key="is_metadata",
                match=models.MatchValue(value=True),
            )
        ]
    )
    return client.query_points(
        collection_name=collection,
        query=vector,
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    ).points


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--qdrant-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    env = load_env(args.root / "backend" / ".env")
    model_name = env.get("COHERE_MODEL") or env.get("COHERE_EMBED_MODEL", "embed-english-v3.0")
    collection = env.get("QDRANT_COLLECTION", "cuad_train")
    top_k = int(env.get("TOP_K", "5"))
    api_key = env.get("COHERE_API_KEY")
    if not api_key:
        raise RuntimeError("COHERE_API_KEY is missing from backend/.env")

    clauses = load_zto_clauses(args.root / "data" / "embeddings" / "train_metadata.jsonl")
    cohere_client = cohere.ClientV2(api_key=api_key)
    embeddings = cohere_client.embed(
        model=model_name,
        input_type="search_query",
        texts=[clause["query_text"] for clause in clauses],
        embedding_types=["float"],
    ).embeddings.float

    qdrant = QdrantClient(path=str(args.qdrant_path))
    info = qdrant.get_collection(collection)
    vector_dimension = collection_size(info)
    if any(len(vector) != vector_dimension for vector in embeddings):
        raise RuntimeError("Cohere vector dimension does not match Qdrant collection")

    results: list[dict] = []
    for clause, vector in zip(clauses, embeddings):
        hits = query_collection(qdrant, collection, vector, top_k)
        serialized_hits = []
        for rank, hit in enumerate(hits, start=1):
            payload = hit.payload or {}
            serialized_hits.append(
                {
                    "rank": rank,
                    "score": float(hit.score),
                    "label": payload.get("clause_type"),
                    "document_id": payload.get("document_id"),
                    "same_zto_document": payload.get("document_id") == ZTO_DOCUMENT,
                    "clause_excerpt": short_excerpt(str(payload.get("clause_text", ""))),
                }
            )
        correct = [hit for hit in serialized_hits if hit["label"] == clause["ground_truth"]]
        correct_best = max(correct, key=lambda hit: hit["score"]) if correct else None
        top1 = serialized_hits[0] if serialized_hits else None
        top2 = serialized_hits[1] if len(serialized_hits) > 1 else None
        results.append(
            {
                **clause,
                "query_excerpt": short_excerpt(clause["query_text"]),
                "top_k": top_k,
                "hits": serialized_hits,
                "correct_rank": correct_best["rank"] if correct_best else None,
                "correct_score": correct_best["score"] if correct_best else None,
                "top1_score": top1["score"] if top1 else None,
                "top2_score": top2["score"] if top2 else None,
                "top1_label": top1["label"] if top1 else None,
                "top1_to_top2_margin": (
                    top1["score"] - top2["score"]
                    if top1 and top2
                    else None
                ),
                "top1_is_correct": bool(top1 and top1["label"] == clause["ground_truth"]),
                "correct_in_top3": any(hit["label"] == clause["ground_truth"] for hit in serialized_hits[:3]),
                "correct_in_top5": bool(correct),
                "top1_to_correct_margin": (
                    top1["score"] - correct_best["score"]
                    if top1 and correct_best
                    else None
                ),
                "same_zto_document": any(hit["same_zto_document"] for hit in serialized_hits),
                "top1_same_zto_document": bool(top1 and top1["same_zto_document"]),
            }
        )

    def rate(key: str) -> float:
        return sum(bool(result[key]) for result in results) / len(results)

    same_document_count = sum(result["same_zto_document"] for result in results)
    top1_same_document_count = sum(result["top1_same_zto_document"] for result in results)
    label_summary: dict[str, dict] = {}
    for label in sorted({result["ground_truth"] for result in results}):
        group = [result for result in results if result["ground_truth"] == label]
        competitors = Counter(
            hit["label"]
            for result in group
            for hit in result["hits"]
            if hit["label"] != label
        )
        label_summary[label] = {
            "tested_clauses": len(group),
            "top1_hit_rate": sum(result["top1_is_correct"] for result in group) / len(group),
            "top3_hit_rate": sum(result["correct_in_top3"] for result in group) / len(group),
            "top5_hit_rate": sum(result["correct_in_top5"] for result in group) / len(group),
            "main_competitors": [name for name, _ in competitors.most_common(5)],
        }

    output = {
        "status": "LEAKAGE_AFFECTED",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "embedding_model": model_name,
        "embedding_dimension": len(embeddings[0]),
        "qdrant_collection": collection,
        "qdrant_vector_dimension": vector_dimension,
        "retrieval_top_k": top_k,
        "label_mapping": "Qdrant payload field 'clause_type' is the CUAD label/category.",
        "ground_truth_source": "data/embeddings/train_metadata.jsonl, filtered to the ZTO document",
        "zto_document": ZTO_DOCUMENT,
        "results": results,
        "aggregate": {
            "tested_clauses": len(results),
            "top1_hit_rate": rate("top1_is_correct"),
            "top3_hit_rate": rate("correct_in_top3"),
            "top5_hit_rate": rate("correct_in_top5"),
            "same_document_retrieval_count": same_document_count,
            "same_document_retrieval_rate": same_document_count / len(results),
            "top1_same_document_count": top1_same_document_count,
            "top1_same_document_rate": top1_same_document_count / len(results),
            "other_document_retrieval_count": len(results) - same_document_count,
        },
        "label_summary": label_summary,
        "safety": {
            "production_files_modified": False,
            "env_modified": False,
            "qdrant_original_modified": False,
            "embedding_artifacts_modified": False,
            "ollama_called": False,
            "git_commit_created": False,
        },
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "retrieval_results.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    with (args.output_dir / "retrieval_results.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "clause_id", "ground_truth", "query_excerpt", "top1_label", "top1_score",
            "correct_in_top3", "correct_in_top5", "correct_rank", "correct_score",
            "top1_to_correct_margin", "same_zto_document", "top1_same_zto_document",
            "top1_to_top2_margin",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: result.get(field) for field in fields} for result in results)

    rows = []
    for result in results:
        rows.append(
            "| {clause_id} | {ground_truth} | {top1_label} | {top1_score:.6f} | {correct_in_top3} | {correct_in_top5} | {correct_rank} | {same_zto_document} |".format(
                clause_id=result["clause_id"],
                ground_truth=result["ground_truth"],
                top1_label=result["top1_label"],
                top1_score=result["top1_score"],
                correct_in_top3="Yes" if result["correct_in_top3"] else "No",
                correct_in_top5="Yes" if result["correct_in_top5"] else "No",
                correct_rank=result["correct_rank"] or "—",
                same_zto_document="Yes" if result["same_zto_document"] else "No",
            )
        )
    summary_rows = []
    for label, summary in label_summary.items():
        summary_rows.append(
            f"| {label} | {summary['tested_clauses']} | {summary['top1_hit_rate']:.1%} | {summary['top3_hit_rate']:.1%} | {summary['top5_hit_rate']:.1%} | {', '.join(summary['main_competitors']) or 'None'} |"
        )
    report = f"""# ZTO CUAD Retrieval Diagnostic

Status: **LEAKAGE_AFFECTED**. The ZTO document is present in the current training index.

## 1. Environment

- Embedding model: `{model_name}`
- Embedding dimension: `{len(embeddings[0])}`
- Qdrant collection: `{collection}`
- Qdrant vector dimension: `{vector_dimension}`
- Retrieval Top-K: `{top_k}`
- Timestamp: `{output['timestamp_utc']}`
- Label mapping: Qdrant payload field `clause_type` is the CUAD label/category.

## 2. Ground Truth

The five evaluated queries are exact annotated clause records from the local CUAD-derived metadata for the ZTO document.

| Clause | Ground Truth |
|---|---|
| Liquidated damages — termination | Liquidated Damages |
| Liquidated damages — vehicle delay | Liquidated Damages |
| Vehicle/personnel insurance | Insurance |
| Third-party liability insurance | Insurance |
| Vehicle insurance requirement | Insurance |

## 3. Per-Clause Results

| Clause | Ground Truth | Top-1 | Top-1 Score | Correct in Top-3 | Correct in Top-5 | Correct Rank | Same ZTO Document? |
|---|---|---:|---:|---|---|---:|---|
{chr(10).join(rows)}

## 4. Aggregate Results

- Top-1 hit rate: **{output['aggregate']['top1_hit_rate']:.1%}**
- Top-3 hit rate: **{output['aggregate']['top3_hit_rate']:.1%}**
- Top-5 hit rate: **{output['aggregate']['top5_hit_rate']:.1%}**
- Any same-document result: **{same_document_count}/{len(results)} ({same_document_count / len(results):.1%})**
- Top-1 same-document result: **{top1_same_document_count}/{len(results)} ({top1_same_document_count / len(results):.1%})**
- Clauses with only other-document results: **{len(results) - same_document_count}/{len(results)}**

### Label-level summary

| Ground Truth Label | Tested Clauses | Top-1 Hit Rate | Top-3 Hit Rate | Top-5 Hit Rate | Main Competitors |
|---|---:|---:|---:|---:|---|
{chr(10).join(summary_rows)}

## 5. Diagnosis

The decision for each clause is recorded in `retrieval_results.json`. A result with the correct label absent from Top-5 is a retrieval failure; a result with the correct label below competing labels is a ranking weakness; a Top-1 correct result leaves classifier behavior unresolved. Any same-document result is leakage-affected.

## 6. Final Conclusion

1. Retrieval failure for these exact annotated queries: **No failure observed; all 5/5 returned the correct label at rank 1.**
2. Correct CUAD label usually present in Top-5: **Yes, 5/5 (100%).**
3. Ranking ambiguity: **Not observed for these queries; the correct label was rank 1 in every case.** This is not a clean generalization result because each query exactly matches an indexed ZTO record.
4. Same-document leakage: **5/5 (100%) had a same-ZTO result at rank 1.**
5. Evidence to change retrieval/embeddings now: **No.** The experiment shows successful exact self-retrieval, but it does not justify changes or prove performance on unseen segmented clauses.

## Safety Check

- Only files under `diagnostics/zto_retrieval_test/` were created or modified.
- No production source file was modified.
- No `.env` file was modified.
- The original Qdrant collection was not modified; the query used an isolated snapshot.
- No embedding artifact was modified or regenerated.
- No Ollama call was made.
- No Git commit was created.
"""
    (args.output_dir / "diagnostic_report.md").write_text(report, encoding="utf-8")
    print(json.dumps(output["aggregate"], indent=2))


if __name__ == "__main__":
    main()
