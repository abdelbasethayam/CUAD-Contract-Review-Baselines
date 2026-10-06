#!/usr/bin/env python3
"""Leakage-safe hybrid retrieval + Qwen evaluation.

Run validation first, tune fusion on validation, then run the frozen setup on
the untouched 100-contract / 1,679-clause CUAD test split.

Experiments:
  hybrid-1          hybrid shortlist + 1 retrieved example per candidate
  hybrid-2          hybrid shortlist + 2 retrieved examples per candidate
  hybrid-rerank-1   hybrid top-30 -> BGE reranker -> shortlist + 1 example
  hybrid-rerank-2   hybrid top-30 -> BGE reranker -> shortlist + 2 examples

Examples:
  python scripts/06_run_qwen_improved.py run --split val --experiment hybrid-rerank-1
  python scripts/06_run_qwen_improved.py tune --experiment hybrid-rerank-1
  python scripts/06_run_qwen_improved.py run --split test --experiment hybrid-rerank-1
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, f1_score

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from backend.app.core.config import (
    HYBRID_COLLECTION,
    HYBRID_EMBEDDING_MODEL,
    HYBRID_INDEX_CACHE,
    HYBRID_K,
    HYBRID_RERANKER_MODEL,
    HYBRID_RERANK_TOP_K,
    HYBRID_SHORTLIST,
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_URL,
    QDRANT_PATH,
    load_labels,
)
from backend.app.core.rag.eval_data import (
    EXCLUDED_METADATA,
    document_disjoint_train_val,
    embed_texts,
    load_clauses,
)
from backend.app.core.rag.hybrid_retrieval import HybridIndex
from backend.app.core.rag.prompt import load_label_definitions
from backend.app.core.rag.qwen_classifier import OllamaSettings, fuse, score_candidates
from backend.app.core.rag.reranker import rerank_hits

TRAIN_CSV = ROOT / "data" / "splits" / "train" / "master_clauses_train.csv"
TEST_CSV = ROOT / "data" / "splits" / "test" / "master_clauses_test.csv"
OUT_DIR = ROOT / "output" / "eval" / "qwen_improved"
DEFAULT_ALPHA = 0.6
VAL_RATIO = 0.10
VAL_SEED = 42


def load_index() -> HybridIndex:
    from qdrant_client import QdrantClient

    cache = Path(HYBRID_INDEX_CACHE)
    if cache.exists():
        idx = HybridIndex.from_qdrant(None, HYBRID_COLLECTION, cache_path=cache)
    else:
        client = QdrantClient(path=str(QDRANT_PATH))
        try:
            idx = HybridIndex.from_qdrant(client, HYBRID_COLLECTION, cache_path=cache)
        finally:
            client.close()
    if not idx.texts:
        raise RuntimeError(
            f"Hybrid collection '{HYBRID_COLLECTION}' is empty. "
            "Run scripts/01_reembed_local.py before evaluation."
        )
    return idx


def get_eval_df(split: str):
    train_df = load_clauses(TRAIN_CSV)
    if split == "val":
        _, val_df = document_disjoint_train_val(
            train_df, val_ratio=VAL_RATIO, seed=VAL_SEED
        )
        return val_df
    return load_clauses(TEST_CSV)


def get_frozen_params(experiment: str, split: str, alpha, beta):
    if alpha is not None:
        return float(alpha), float(beta or 0.0)
    if split == "test":
        path = OUT_DIR / f"{experiment}_fusion_params.json"
        if not path.exists():
            raise SystemExit(
                f"Missing frozen validation parameters: {path}. "
                f"Run validation and tune first, or pass --alpha."
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        return float(data["alpha"]), float(data.get("beta", 0.0))
    return DEFAULT_ALPHA, float(beta or 0.0)


def metrics(records: list[dict]) -> dict:
    y_true = [r["ground_truth"] for r in records]
    y_pred = [r["prediction"] for r in records]
    return {
        "count": len(records),
        "accuracy": float(accuracy_score(y_true, y_pred)) if records else 0.0,
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0))
        if records else 0.0,
        "shortlist_recall": float(np.mean([r["gold_in_shortlist"] for r in records]))
        if records else 0.0,
    }


def settings(experiment: str) -> tuple[bool, int]:
    table = {
        "hybrid-1": (False, 1),
        "hybrid-2": (False, 2),
        "hybrid-rerank-1": (True, 1),
        "hybrid-rerank-2": (True, 2),
    }
    return table[experiment]


def run(split: str, experiment: str, *, alpha: float, beta: float,
        permutations: int, limit: int) -> Path:
    do_rerank, examples_per_candidate = settings(experiment)
    eval_df = get_eval_df(split)
    if limit:
        if split == "test":
            raise SystemExit("--limit is allowed only for validation runs.")
        eval_df = eval_df.iloc[:limit].copy()

    index = load_index()
    if split == "val":
        val_docs = set(eval_df["document_id"].astype(str))
        # Refit lexical statistics without any validation documents.
        index = index.excluding_documents(val_docs)

    texts = eval_df["clause_text"].tolist()
    vectors = embed_texts(texts, HYBRID_EMBEDDING_MODEL)
    labels = [x for x in load_labels() if x not in EXCLUDED_METADATA]
    definitions = load_label_definitions(labels)
    cfg = OllamaSettings(
        url=OLLAMA_URL,
        model=OLLAMA_MODEL,
        num_ctx=OLLAMA_NUM_CTX,
        think=False,
        temperature=0.0,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{experiment}_{split}.jsonl"
    records: list[dict] = []
    started = time.time()

    with out_path.open("w", encoding="utf-8") as handle:
        for n, (row, vector) in enumerate(
            zip(eval_df.to_dict("records"), vectors), start=1
        ):
            hits = index.search(
                row["clause_text"],
                vector.tolist(),
                k=HYBRID_K,
            )
            if do_rerank:
                hits = rerank_hits(
                    row["clause_text"],
                    hits,
                    model_name=HYBRID_RERANKER_MODEL,
                    top_k=HYBRID_RERANK_TOP_K,
                )

            candidates = index.shortlist(hits, size=HYBRID_SHORTLIST)
            if not candidates:
                raise RuntimeError(f"No candidate labels generated for row {n}.")

            qwen = score_candidates(
                row["clause_text"],
                candidates,
                definitions,
                hits,
                cfg,
                permutations=permutations,
                examples_per_candidate=examples_per_candidate,
                seed=VAL_SEED,
            )
            retrieval_votes = index.label_votes(hits)
            denom = sum(retrieval_votes.get(c, 0.0) for c in candidates) or 1.0
            p_knn = {
                c: retrieval_votes.get(c, 0.0) / denom
                for c in candidates
            }
            prediction, fused_scores = fuse(
                candidates,
                p_knn,
                qwen["p_qwen"],
                index.label_prior,
                alpha,
                beta,
            )

            record = {
                "split": split,
                "experiment": experiment,
                "document_id": row["document_id"],
                "ground_truth": row["clause_type"],
                "prediction": prediction,
                "correct": prediction == row["clause_type"],
                "gold_in_shortlist": row["clause_type"] in candidates,
                "candidate_labels": candidates,
                "reranked": do_rerank,
                "reranker_model": HYBRID_RERANKER_MODEL if do_rerank else None,
                "examples_per_candidate": examples_per_candidate,
                "qwen_probs": qwen["p_qwen"],
                "knn_probs": p_knn,
                "fused_scores": fused_scores,
            }
            records.append(record)
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()

            if n % 25 == 0 or n == len(eval_df):
                print(
                    f"[{split}/{experiment}] {n}/{len(eval_df)} "
                    f"acc={np.mean([r['correct'] for r in records]):.4f} "
                    f"shortlist={np.mean([r['gold_in_shortlist'] for r in records]):.4f} "
                    f"elapsed={(time.time()-started)/60:.1f}m"
                )

    summary = metrics(records)
    summary.update({
        "split": split,
        "experiment": experiment,
        "model": OLLAMA_MODEL,
        "embedding_model": HYBRID_EMBEDDING_MODEL,
        "retrieval_k": HYBRID_K,
        "shortlist_size": HYBRID_SHORTLIST,
        "reranker_model": HYBRID_RERANKER_MODEL if do_rerank else None,
        "examples_per_candidate": examples_per_candidate,
        "permutations": permutations,
        "alpha": alpha,
        "beta": beta,
        "validation_ratio": VAL_RATIO,
        "validation_seed": VAL_SEED,
    })
    summary_path = OUT_DIR / f"{experiment}_{split}_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return summary_path


def tune(experiment: str) -> Path:
    val_path = OUT_DIR / f"{experiment}_val.jsonl"
    if not val_path.exists():
        raise SystemExit(
            f"Missing {val_path}. Run validation first."
        )
    rows = [
        json.loads(line)
        for line in val_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    best = None
    for alpha in np.linspace(0.0, 1.0, 21):
        golds = [r["ground_truth"] for r in rows]
        preds = []
        for r in rows:
            pred, _ = fuse(
                r["candidate_labels"],
                r["knn_probs"],
                r["qwen_probs"],
                {label: 1.0 for label in r["candidate_labels"]},
                float(alpha),
                0.0,
            )
            preds.append(pred)
        score = f1_score(golds, preds, average="macro", zero_division=0)
        acc = accuracy_score(golds, preds)
        candidate = (float(score), float(acc), float(alpha))
        if best is None or candidate > best:
            best = candidate

    assert best is not None
    _, _, alpha = best
    params = {
        "alpha": alpha,
        "beta": 0.0,
        "selection_metric": "macro_f1",
        "validation_macro_f1": best[0],
        "validation_accuracy": best[1],
        "grid": "alpha 0.0..1.0 step 0.05",
        "beta": "fixed at 0.0 until per-label priors are explicitly calibrated",
    }
    path = OUT_DIR / f"{experiment}_fusion_params.json"
    path.write_text(
        json.dumps(params, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(params, indent=2))
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run")
    run_p.add_argument("--split", choices=("val", "test"), required=True)
    run_p.add_argument(
        "--experiment",
        choices=("hybrid-1", "hybrid-2", "hybrid-rerank-1", "hybrid-rerank-2"),
        default="hybrid-rerank-1",
    )
    run_p.add_argument("--perms", type=int, default=1)
    run_p.add_argument("--limit", type=int, default=0)
    run_p.add_argument("--alpha", type=float, default=None)
    run_p.add_argument("--beta", type=float, default=None)

    tune_p = sub.add_parser("tune")
    tune_p.add_argument(
        "--experiment",
        choices=("hybrid-1", "hybrid-2", "hybrid-rerank-1", "hybrid-rerank-2"),
        default="hybrid-rerank-1",
    )

    args = parser.parse_args()
    if args.command == "tune":
        tune(args.experiment)
        return

    alpha, beta = get_frozen_params(
        args.experiment, args.split, args.alpha, args.beta
    )
    run(
        args.split,
        args.experiment,
        alpha=alpha,
        beta=beta,
        permutations=max(1, args.perms),
        limit=max(0, args.limit),
    )


if __name__ == "__main__":
    main()
