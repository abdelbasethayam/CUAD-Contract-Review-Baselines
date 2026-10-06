#!/usr/bin/env python3
"""Create a deterministic human-gold annotation queue from the training split.

This produces annotation *work*, not labels. Gold labels must be assigned by
human annotators and adjudicated before calibration or final significance tests.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.core.rag.eval_data import load_clauses
from backend.app.core.risk.risk_playbook import applicable_checks, load_playbook


def sample_rows(source: Path, n: int, seed: int) -> list[dict]:
    df = load_clauses(source)
    playbook = load_playbook()
    pool = []
    for row in df.to_dict("records"):
        clause_index = int(row["clause_index"])
        checks = applicable_checks(playbook, row["clause_type"])
        for check in checks:
            sample_id = hashlib.sha256(
                f"{row['document_id']}|{row['clause_type']}|{row['clause_text']}|{check['id']}".encode("utf-8")
            ).hexdigest()[:16]
            pool.append({
                "sample_id": sample_id,
                "document_id": row["document_id"],
                "clause_index": clause_index,
                "clause_type": row["clause_type"],
                "clause_text": row["clause_text"],
                "check_id": check["id"],
                "question": check["question"],
                "flag_if": check["flag_if"],
                "gold_risk": "",
                "gold_risk_type": "",
                "gold_severity": "",
                "gold_evidence": "",
                "annotator_1": "",
                "annotator_2": "",
                "adjudicated_by": "",
                "adjudicated_risk": "",
                "adjudicated_risk_type": "",
                "adjudicated_severity": "",
                "adjudicated_evidence": "",
                "notes": "",
            })

    # Stratify across check ids first, then fill deterministically.
    rng = random.Random(seed)
    buckets = {}
    for item in pool:
        buckets.setdefault(item["check_id"], []).append(item)
    selected = []
    keys = sorted(buckets)
    while len(selected) < min(n, len(pool)):
        progressed = False
        for key in keys:
            bucket = buckets[key]
            if not bucket:
                continue
            item = bucket.pop(rng.randrange(len(bucket)))
            selected.append(item)
            progressed = True
            if len(selected) >= n:
                break
        if not progressed:
            break
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=ROOT / "data" / "splits" / "train" / "master_clauses_train.csv",
    )
    parser.add_argument("--n", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "risk" / "gold" / "annotation_queue.csv",
    )
    args = parser.parse_args()

    rows = sample_rows(args.source, max(1, args.n), args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise SystemExit("No applicable clause/check pairs found.")
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} gold-annotation tasks -> {args.out}")


if __name__ == "__main__":
    main()
