#!/usr/bin/env python3
"""Reproducible evaluation entrypoint for CUAD clause classification."""
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
            f"Test CSV not found at {TEST_DATA_PATH}. Provide --fixed-json."
        )
    df = pd.read_csv(TEST_DATA_PATH)
    if "is_metadata" in df.columns:
        df = df.loc[~df["is_metadata"].astype(bool)]
    if args.limit and args.limit > 0:
        df = df.sample(n=min(args.limit, len(df)), random_state=args.seed)
    return [
        {
            "clause_text": str(row.get("clause_text") or row.get("text") or ""),
            "ground_truth": str(row.get("clause_type") or row.get("label") or ""),
            "document_id": str(row.get("document_id") or ""),
        }
        for _, row in df.iterrows()
    ]


def _recall_at_k(gt: str, candidates: list[str], k: int) -> float:
    return 1.0 if gt in candidates[:k] else 0.0


def _mrr(gt: str, candidates: list[str]) -> float:
    try:
        return 1.0 / (candidates.index(gt) + 1)
    except ValueError:
        return 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixed-json", type=str, default=None)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260910)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = _load_rows(args)
    print(f"Loaded {len(rows)} evaluation rows")
    if args.dry_run:
        for lab, cnt in Counter(r.get("ground_truth") for r in rows).most_common(15):
            print(f"  {lab}: {cnt}")
        return

    from backend.app.core.config import OLLAMA_MODEL, TOP_K, load_labels
    from backend.app.core.rag.prompt import load_label_definitions
    from backend.app.core.rag.text_preprocessor import preprocess_clause

    labels = load_labels()
    label_defs = load_label_definitions(labels)
    print(f"Using OLLAMA_MODEL={OLLAMA_MODEL}, TOP_K={TOP_K}")

    try:
        from backend.app.core.rag.generator import classify_clause
        from backend.app.core.rag.embedder import embed_queries  # type: ignore
        from qdrant_client import QdrantClient
        from backend.app.core.config import QDRANT_PATH, QDRANT_URL, QDRANT_API_KEY

        client = (
            QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
            if QDRANT_URL
            else QdrantClient(path=QDRANT_PATH)
        )
    except Exception as exc:
        print(f"WARNING: full pipeline unavailable ({exc})")
        for r in rows[:5]:
            print(f"  GT={r['ground_truth']!r} len={len(preprocess_clause(r['clause_text']))}")
        return

    stats = {"n": 0, "correct": 0, "recall_at_1": 0.0, "recall_at_5": 0.0, "mrr": 0.0,
             "retrieval_miss": 0, "classification_error": 0, "abstention": 0}
    for row in rows:
        clause = preprocess_clause(row["clause_text"])
        gt = row["ground_truth"]
        result = classify_clause(
            clause_text=clause,
            query_vector=embed_queries([clause])[0],
            qdrant_client=client,
            labels=labels,
            label_definitions=label_defs,
            top_k=TOP_K,
        )
        pred = result.get("predicted_label") or ""
        candidates = result.get("candidate_labels") or result.get("retrieved_labels") or []
        stats["n"] += 1
        stats["recall_at_1"] += _recall_at_k(gt, candidates, 1)
        stats["recall_at_5"] += _recall_at_k(gt, candidates, 5)
        stats["mrr"] += _mrr(gt, candidates)
        if pred == gt:
            stats["correct"] += 1
        elif gt not in candidates:
            stats["retrieval_miss"] += 1
        elif pred in ("NO_APPLICABLE_LABEL", "", None):
            stats["abstention"] += 1
        else:
            stats["classification_error"] += 1

    n = max(stats["n"], 1)
    print(f"Accuracy: {stats['correct']/n:.4f} ({stats['correct']}/{stats['n']})")
    print(f"Recall@1: {stats['recall_at_1']/n:.4f}  Recall@5: {stats['recall_at_5']/n:.4f}")
    print(f"MRR: {stats['mrr']/n:.4f}")


if __name__ == "__main__":
    main()
