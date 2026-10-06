#!/usr/bin/env python3
"""Run the risk engine against an adjudicated gold queue and checkpoint predictions."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.core.rag.eval_data import load_clauses
from backend.app.core.risk.risk_engine import analyze_clause_risk
from backend.app.core.risk.risk_playbook import load_playbook
from backend.app.core.risk.run_store import create_or_resume_run
from backend.app.core.rag import embed_queries, make_cohere_client


def load_queue(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("adjudicated_risk") or "").strip().upper() not in {"YES", "NO"}:
                continue
            rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--queue",
        type=Path,
        default=ROOT / "data" / "risk" / "gold" / "annotation_queue.csv",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=ROOT / "data" / "splits" / "train" / "master_clauses_train.csv",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "risk" / "gold" / "adjudicated_predictions.csv",
    )
    args = parser.parse_args()

    queue_rows = load_queue(args.queue)
    if not queue_rows:
        raise SystemExit("No adjudicated rows found in queue.")

    source_df = load_clauses(args.source)
    source_by_doc = {}
    for row in source_df.to_dict("records"):
        source_by_doc.setdefault(str(row["document_id"]), []).append(row)

    playbook = load_playbook()
    cohere = make_cohere_client()

    # Build one vector per unique gold clause, then reuse it for all checks.
    clause_keys = []
    clause_texts = []
    for row in queue_rows:
        key = (str(row["document_id"]), str(row["clause_index"]))
        if key not in clause_keys:
            clause_keys.append(key)
            clause_texts.append(str(row["clause_text"]))
    vectors = embed_queries(cohere, clause_texts)
    vector_map = {key: vector for key, vector in zip(clause_keys, vectors)}

    out_jsonl = args.out.with_suffix(".jsonl")
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    done = {}
    if out_jsonl.exists():
        for line in out_jsonl.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                done[item["sample_id"]] = item

    with out_jsonl.open("a", encoding="utf-8") as handle:
        for n, gold in enumerate(queue_rows, start=1):
            sample_id = gold["sample_id"]
            if sample_id in done:
                continue

            doc_rows = source_by_doc.get(str(gold["document_id"]), [])
            contract_clauses = []
            for pos, item in enumerate(doc_rows):
                contract_clauses.append({
                    "clause_index": pos,
                    "clause_text": item["clause_text"],
                    "vector": vector_map.get(
                        (str(item["document_id"]), str(pos)),
                        [],
                    ).tolist() if isinstance(vector_map.get((str(item["document_id"]), str(pos))), np.ndarray) else [],
                })

            key = (str(gold["document_id"]), str(gold["clause_index"]))
            vector = vector_map.get(key)
            if vector is None:
                raise RuntimeError(f"Missing vector for {key}")

            findings = analyze_clause_risk(
                clause_index=int(gold["clause_index"]),
                clause_text=str(gold["clause_text"]),
                clause_type=str(gold["clause_type"]),
                query_vector=vector.tolist(),
                contract_clauses=contract_clauses,
                playbook=playbook,
                passes=1,
            )
            finding = next(
                (item for item in findings if item["check_id"] == gold["check_id"]),
                None,
            )
            if finding is None:
                prediction = {
                    "risk_status": "INSUFFICIENT_EVIDENCE",
                    "risk": False,
                    "risk_type": None,
                    "raw_support_score": 0.0,
                    "severity_signal": None,
                    "evidence": "",
                }
            else:
                prediction = finding

            record = {
                "sample_id": sample_id,
                "contract_id": gold["document_id"],
                "clause_index": int(gold["clause_index"]),
                "check_id": gold["check_id"],
                "gold_risk": gold["adjudicated_risk"],
                "gold_severity": gold.get("adjudicated_severity", ""),
                "gold_evidence": gold.get("adjudicated_evidence", ""),
                "pred_risk": "YES" if prediction.get("risk") else "NO",
                "pred_probability": prediction.get("confidence"),
                "raw_support_score": prediction.get("raw_support_score"),
                "pred_severity": prediction.get("risk_level") or "",
                "severity_signal": prediction.get("severity_signal"),
                "evidence": prediction.get("evidence", ""),
                "risk_status": prediction.get("risk_status"),
                "risk_type": prediction.get("risk_type"),
                "ground_truth_status": "MANUAL_GOLD",
                "playbook_ground_truth_status": prediction.get("ground_truth_status"),
                "provenance": prediction.get("provenance", {}),
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            done[sample_id] = record
            print(f"{n}/{len(queue_rows)} {sample_id} -> {record['pred_risk']}")

    rows = list(done.values())
    fieldnames = [
        "sample_id", "contract_id", "clause_index", "check_id",
        "gold_risk", "gold_severity", "gold_evidence",
        "pred_risk", "pred_probability", "raw_support_score",
        "pred_severity", "severity_signal", "evidence",
        "risk_status", "risk_type", "ground_truth_status",
        "playbook_ground_truth_status",
    ]
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} prediction rows -> {args.out}")


if __name__ == "__main__":
    main()
