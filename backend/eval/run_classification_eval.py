#!/usr/bin/env python3
"""Reproducible evaluation entrypoint for CUAD clause classification.

Usage examples:
  python -m backend.eval.run_classification_eval --limit 50
  python -m backend.eval.run_classification_eval --fixed-json path/to/selected_rows.json

Metrics reported:
  - accuracy (exact label match)
  - Recall@1 / @3 / @5 (whether GT appears in retrieved candidates)
  - MRR
  - error taxonomy: retrieval_miss | classification_error | abstention | other
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.fixed_json:
        data = json.loads(Path(args.fixed_json).read_text(encoding="utf-8"))
        if isinstance(data, dict) and "rows" in data:
            return list(data["rows"])
        if isinstance(data, list):
            return data
        raise SystemExit(f"Unsupported fixed JSON structure in {args.fixed_json}")

    from backend.app.core.config import TEST_DATA_PATH
    import pandas as pd

    if not TEST_DATA_PATH.exists():
        raise SystemExit(
            f"Test CSV not found at {TEST_DATA_PATH}. "
            "Provide --fixed-json with a pre-selected row list."
        )
    df = pd.read_csv(TEST_DATA_PATH)
    if "is_metadata" in df.columns:
        df = df.loc[~df["is_metadata"].astype(bool)]
    if args.limit and args.limit > 0:
        df = df.sample(n=min(args.limit, len(df)), random_state=args.seed)
    rows = []
    for _, row in df.iterrows():
        rows.append(
            {
                "clause_text": str(row.get("clause_text") or row.get("text") or ""),
                "ground_truth": str(row.get("clause_type") or row.get("label") or ""),
                "document_id": str(row.get("document_id") or ""),
            }
        )
    return rows


def _recall_at_k(gt: str, candidates: list[str], k: int) -> float:
    return 1.0 if gt in candidates[:k] else 0.0


def _mrr(gt: str, candidates: list[str]) -> float:
    try:
        rank = candidates.index(gt) + 1
        return 1.0 / rank
    except ValueError:
        return 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="CUAD classification evaluation")
    parser.add_argument("--fixed-json", type=str, default=None)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260910)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = _load_rows(args)
    print(f"Loaded {len(rows)} evaluation rows")

    if args.dry_run:
        labels = Counter(r.get("ground_truth") for r in rows)
        print("Label distribution (top 15):")
        for lab, cnt in labels.most_common(15):
            print(f"  {lab}: {cnt}")
        return

    from backend.app.core.config import OLLAMA_MODEL, TOP_K, load_labels
    from backend.app.core.rag.prompt import load_label_definitions
    from backend.app.core.rag.text_preprocessor import preprocess_clause

    labels = load_labels()
    label_defs = load_label_definitions(labels)
    print(f"Using OLLAMA_MODEL={OLLAMA_MODEL}, TOP_K={TOP_K}, n_labels={len(labels)}")

    try:
        from backend.app.core.rag.generator import classify_clause
        from backend.app.core.rag.embedder import embed_queries  # type: ignore
        from qdrant_client import QdrantClient
        from backend.app.core.config import QDRANT_PATH, QDRANT_URL, QDRANT_API_KEY

        if QDRANT_URL:
            client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        else:
            client = QdrantClient(path=QDRANT_PATH)
    except Exception as exc:
        print(f"WARNING: full pipeline deps unavailable ({exc}). Preprocessing smoke check.")
        for r in rows[:5]:
            cleaned = preprocess_clause(r["clause_text"])
            print(f"  GT={r['ground_truth']!r}  cleaned_len={len(cleaned)}")
        return

    stats = {
        "n": 0, "correct": 0,
        "recall_at_1": 0.0, "recall_at_3": 0.0, "recall_at_5": 0.0, "mrr": 0.0,
        "retrieval_miss": 0, "classification_error": 0, "abstention": 0, "other": 0,
    }

    for row in rows:
        clause = preprocess_clause(row["clause_text"])
        gt = row["ground_truth"]
        vectors = embed_queries([clause])
        result = classify_clause(
            clause_text=clause,
            query_vector=vectors[0],
            qdrant_client=client,
            labels=labels,
            label_definitions=label_defs,
            top_k=TOP_K,
        )
        pred = result.get("predicted_label") or ""
        candidates = result.get("candidate_labels") or result.get("retrieved_labels") or []

        stats["n"] += 1
        stats["recall_at_1"] += _recall_at_k(gt, candidates, 1)
        stats["recall_at_3"] += _recall_at_k(gt, candidates, 3)
        stats["recall_at_5"] += _recall_at_k(gt, candidates, 5)
        stats["mrr"] += _mrr(gt, candidates)

        if pred == gt:
            stats["correct"] += 1
        elif gt not in candidates:
            stats["retrieval_miss"] += 1
        elif pred in ("NO_APPLICABLE_LABEL", "", None):
            stats["abstention"] += 1
        elif pred != gt:
            stats["classification_error"] += 1
        else:
            stats["other"] += 1

    n = max(stats["n"], 1)
    print("\n=== Results ===")
    print(f"Accuracy:          {stats['correct'] / n:.4f}  ({stats['correct']}/{stats['n']})")
    print(f"Recall@1:          {stats['recall_at_1'] / n:.4f}")
    print(f"Recall@3:          {stats['recall_at_3'] / n:.4f}")
    print(f"Recall@5:          {stats['recall_at_5'] / n:.4f}")
    print(f"MRR:               {stats['mrr'] / n:.4f}")
    print(f"Retrieval misses:  {stats['retrieval_miss']}")
    print(f"Classif. errors:   {stats['classification_error']}")
    print(f"Abstentions:       {stats['abstention']}")
    print(f"Other:             {stats['other']}")


if __name__ == "__main__":
    main()
