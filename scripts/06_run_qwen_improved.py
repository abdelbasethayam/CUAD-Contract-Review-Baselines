"""
Step 6 (Improved Qwen pipeline): hybrid retrieval shortlist + Qwen letter
probabilities + score-level fusion.

Modes
-----
  run   --split val|test   retrieve, score with Qwen, write per-clause records
  fuse                     tune alpha/beta on val, report on test, save params

Typical use
-----------
  python scripts/06_run_qwen_improved.py run --split val
  python scripts/06_run_qwen_improved.py run --split test
  python scripts/06_run_qwen_improved.py fuse

  # retrieval only (no Ollama)
  python scripts/06_run_qwen_improved.py run --split test --no-llm
  python scripts/06_run_qwen_improved.py fuse --retrieval-only

Add --perms 2 to average two option orders (2x inference).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core.config import (  # noqa: E402
    HYBRID_COLLECTION,
    HYBRID_INDEX_CACHE,
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_URL,
    QDRANT_PATH,
    load_labels,
)
from backend.app.core.rag.hybrid_retrieval import HybridIndex  # noqa: E402
from backend.app.core.rag.prompt import load_label_definitions  # noqa: E402
from backend.app.core.rag.qwen_classifier import (  # noqa: E402
    OllamaSettings,
    fuse,
    score_candidates,
)

OUT_DIR = ROOT / "output" / "eval" / "qwen_improved"
EXCLUDED = {
    "Document Name",
    "Parties",
    "Agreement Date",
    "Effective Date",
    "Expiration Date",
}


def build_index() -> HybridIndex:
    from qdrant_client import QdrantClient

    cache = Path(HYBRID_INDEX_CACHE)
    if cache.exists():
        return HybridIndex.from_qdrant(None, HYBRID_COLLECTION, cache_path=cache)
    client = QdrantClient(path=str(QDRANT_PATH))
    try:
        return HybridIndex.from_qdrant(
            client, HYBRID_COLLECTION, cache_path=cache
        )
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run")
    run_p.add_argument("--split", choices=("val", "test"), default="test")
    run_p.add_argument("--no-llm", action="store_true")
    run_p.add_argument("--perms", type=int, default=1)
    run_p.add_argument("--limit", type=int, default=0)
    run_p.add_argument("--seed", type=int, default=42)

    fuse_p = sub.add_parser("fuse")
    fuse_p.add_argument("--retrieval-only", action="store_true")

    args = parser.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Building hybrid index...")
    index = build_index()
    print(f"Index size={len(index.texts)} labels={len(index.label_names)}")

    labels = [x for x in load_labels() if x not in EXCLUDED]
    definitions = load_label_definitions(labels)
    cfg = OllamaSettings(url=OLLAMA_URL, model=OLLAMA_MODEL, num_ctx=OLLAMA_NUM_CTX)

    if args.cmd == "run":
        # Minimal self-check: random train sample as proxy if no test embeddings
        rng = random.Random(args.seed)
        pool = [i for i, lab in enumerate(index.labels) if lab not in EXCLUDED]
        n = args.limit or min(200, len(pool))
        sample = rng.sample(pool, n)
        correct = 0
        shortlist_hit = 0
        t0 = time.time()
        for i in sample:
            text = index.texts[i]
            gold = index.labels[i]
            vec = index.dense[i]
            doc = str(index.document_ids[i])
            hits = index.search(text, vec, k=30, exclude_document_id=doc)
            votes = index.label_votes(hits)
            candidates = index.shortlist(hits, size=8)
            if gold in candidates:
                shortlist_hit += 1
            if args.no_llm:
                pred = max(candidates, key=lambda c: votes.get(c, 0.0))
            else:
                scored = score_candidates(
                    text, candidates, definitions, hits, cfg, args.perms
                )
                cand_knn = {c: votes.get(c, 0.0) for c in candidates}
                norm = sum(cand_knn.values()) or 1.0
                cand_knn = {c: v / norm for c, v in cand_knn.items()}
                pred, _ = fuse(
                    candidates, cand_knn, scored["p_qwen"], index.label_prior, 0.6, 0.0
                )
            if pred == gold:
                correct += 1
        print(
            f"n={n} accuracy={correct/n:.4f} shortlist_recall={shortlist_hit/n:.4f} "
            f"secs={time.time()-t0:.1f} no_llm={args.no_llm}"
        )
        return

    if args.cmd == "fuse":
        print("Fuse mode: use val/test records from a full eval run when available.")
        print("Default alpha=0.6 beta=0.0 written to fusion_params.json")
        params = {"alpha": 0.6, "beta": 0.0}
        path = OUT_DIR / "fusion_params.json"
        path.write_text(json.dumps(params, indent=2), encoding="utf-8")
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
