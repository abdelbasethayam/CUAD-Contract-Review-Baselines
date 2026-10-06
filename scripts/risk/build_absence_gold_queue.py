#!/usr/bin/env python3
"""Build a human queue for clause-family absence and missing-protection review."""
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
from backend.app.core.risk.contract_coverage import build_contract_coverage
from backend.app.core.risk.risk_playbook import load_playbook


def annotation_partition(contract_id: str) -> str:
    digest = hashlib.sha256(str(contract_id).encode("utf-8")).hexdigest()
    value = int(digest[:8], 16) % 100
    if value < 25:
        return "calibration"
    if value < 50:
        return "development"
    return "locked_test"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=ROOT / "data/splits/train/master_clauses_train.csv",
    )
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data/risk/gold/absence_annotation_queue.csv",
    )
    args = parser.parse_args()

    df = load_clauses(args.source)
    rows_by_doc: dict[str, list[dict]] = {}
    for row in df.to_dict("records"):
        rows_by_doc.setdefault(str(row["document_id"]), []).append(row)

    playbook = load_playbook()
    pool: list[dict] = []

    for doc_id, clauses in sorted(rows_by_doc.items()):
        classification_rows = [
            {
                "clause_index": int(x["clause_index"]),
                "clause_text": str(x["clause_text"]),
                "predicted_label": str(x["clause_type"]),
            }
            for x in clauses
        ]
        coverage = build_contract_coverage(classification_rows, playbook)

        for item in coverage:
            if item["status"] != "NOT_FOUND_BY_SEARCH":
                continue
            for check_id in (item.get("check_ids") or [])[:1]:
                sample_id = hashlib.sha256(
                    f"{doc_id}|{item['clause_type']}|{check_id}".encode()
                ).hexdigest()[:16]
                contract_text = "\n\n".join(
                    str(x["clause_text"])
                    for x in sorted(clauses, key=lambda z: int(z["clause_index"]))
                )
                pool.append(
                    {
                        "sample_id": sample_id,
                        "annotation_partition": annotation_partition(doc_id),
                        "contract_id": doc_id,
                        "clause_type": item["clause_type"],
                        "check_id": check_id,
                        "contract_text": contract_text,
                        "search_status": "NOT_FOUND_BY_SEARCH",
                        "adjudicated_presence": "",
                        "adjudicated_risk": "",
                        "adjudicated_risk_type": "",
                        "adjudicated_evidence": "",
                        "notes": "",
                    }
                )

    rng = random.Random(args.seed)
    rng.shuffle(pool)
    rows = pool[: min(args.n, len(pool))]

    if not rows:
        raise SystemExit("No absence candidates found.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} absence-review tasks -> {args.out}")


if __name__ == "__main__":
    main()
