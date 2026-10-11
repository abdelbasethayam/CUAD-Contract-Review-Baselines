#!/usr/bin/env python3
"""Create a deterministic human-gold annotation queue from the training split.

This produces annotation *work*, not labels. Gold labels must be assigned by
human annotators and adjudicated before calibration or final significance tests.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.core.rag.eval_data import load_clauses
from backend.app.core.risk.risk_playbook import applicable_checks, load_playbook


def annotation_partition(contract_id: str) -> str:
    """Assign one partition per contract to prevent cross-partition leakage."""
    digest = hashlib.sha256(str(contract_id).encode("utf-8")).hexdigest()
    value = int(digest[:8], 16) % 100
    if value < 25:
        return "calibration"
    if value < 50:
        return "development"
    return "locked_test"


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
                "annotation_partition": annotation_partition(row["document_id"]),
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
                "annotator_1_risk": "",
                "annotator_1_risk_type": "",
                "annotator_1_severity": "",
                "annotator_1_evidence": "",
                "annotator_2_risk": "",
                "annotator_2_risk_type": "",
                "annotator_2_severity": "",
                "annotator_2_evidence": "",
                "adjudicated_by": "",
                "adjudicated_risk": "",
                "adjudicated_risk_type": "",
                "adjudicated_severity": "",
                "adjudicated_evidence": "",
                "notes": "",
            })

    rng = random.Random(seed)
    by_partition_check = {}
    for item in pool:
        by_partition_check.setdefault(
            (item["annotation_partition"], item["check_id"]), []
        ).append(item)
    for bucket in by_partition_check.values():
        rng.shuffle(bucket)

    target_cal = max(1, min(n, round(n * 0.25)))
    target_dev = max(1, min(n - target_cal, round(n * 0.25)))
    target_locked = max(1, n - target_cal - target_dev)
    targets = {
        "calibration": target_cal,
        "development": target_dev,
        "locked_test": target_locked,
    }
    check_ids = sorted({item["check_id"] for item in pool})
    selected = []
    selected_ids = set()

    # Guarantee locked-test representation for every check whenever possible.
    for check_id in check_ids:
        bucket = by_partition_check.get(("locked_test", check_id), [])
        if bucket and sum(x["annotation_partition"] == "locked_test" for x in selected) < target_locked:
            item = bucket.pop()
            selected.append(item)
            selected_ids.add(item["sample_id"])

    # Fill partitions round-robin across checks. Partition ownership is by
    # contract, so the same contract cannot enter another partition.
    for partition in ("calibration", "development", "locked_test"):
        while sum(x["annotation_partition"] == partition for x in selected) < targets[partition]:
            progressed = False
            for check_id in check_ids:
                bucket = by_partition_check.get((partition, check_id), [])
                while bucket and bucket[-1]["sample_id"] in selected_ids:
                    bucket.pop()
                if not bucket:
                    continue
                item = bucket.pop()
                selected.append(item)
                selected_ids.add(item["sample_id"])
                progressed = True
                if sum(x["annotation_partition"] == partition for x in selected) >= targets[partition]:
                    break
            if not progressed:
                break

    return selected[:min(n, len(selected))]


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
    playbook = load_playbook()

    rows = sample_rows(args.source, max(1, args.n), args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise SystemExit("No applicable clause/check pairs found.")
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    partition_counts = {}
    contract_sets = {}
    check_sets = {}
    for item in rows:
        partition = item["annotation_partition"]
        partition_counts[partition] = partition_counts.get(partition, 0) + 1
        contract_sets.setdefault(partition, set()).add(item["document_id"])
        check_sets.setdefault(partition, set()).add(item["check_id"])

    source_hash = hashlib.sha256(args.source.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1,
        "queue_path": str(args.out),
        "source_path": str(args.source),
        "source_sha256": source_hash,
        "playbook_hash": playbook.get("playbook_hash"),
        "seed": args.seed,
        "n_requested": args.n,
        "n_written": len(rows),
        "sampling_method": "contract-disjoint deterministic partition; 25/25/50 target allocation; locked-test one-per-check coverage then round-robin fill",
        "partition_counts": partition_counts,
        "contract_counts": {k: len(v) for k, v in contract_sets.items()},
        "cross_partition_contracts": 0,
        "check_counts": {k: len(v) for k, v in check_sets.items()},
        "locked_test_check_coverage": len(check_sets.get("locked_test", set())),
    }
    manifest_path = args.out.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} gold-annotation tasks -> {args.out}")
    print(f"Wrote queue manifest -> {manifest_path}")


if __name__ == "__main__":
    main()
