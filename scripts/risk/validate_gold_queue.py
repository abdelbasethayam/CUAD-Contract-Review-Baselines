#!/usr/bin/env python3
"""Validate risk gold/absence queues before human annotation or evaluation."""
from __future__ import annotations
import argparse, csv
from collections import defaultdict, Counter
from pathlib import Path

def read_csv(path):
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def validate_main(rows):
    required={"sample_id","annotation_partition","document_id","clause_index","check_id","clause_text","adjudicated_risk"}
    missing=required-set(rows[0]) if rows else required
    assert not missing, f"Missing columns: {sorted(missing)}"
    ids=[r["sample_id"] for r in rows]
    assert len(ids)==len(set(ids)), "Duplicate sample_id values"
    by_contract=defaultdict(set)
    for r in rows:
        by_contract[r["document_id"]].add(r["annotation_partition"])
        assert r["annotation_partition"] in {"calibration","development","locked_test"}
    crossed={k:v for k,v in by_contract.items() if len(v)>1}
    assert not crossed, f"Contracts cross partitions: {len(crossed)}"
    print("main_rows",len(rows))
    print("main_partitions",dict(Counter(r["annotation_partition"] for r in rows)))
    print("main_contracts",len(by_contract))
    print("main_cross_partition_contracts",len(crossed))
    return True

def validate_absence(rows):
    if not rows:
        return True
    required={"sample_id","annotation_partition","contract_id","check_id","adjudicated_presence"}
    missing=required-set(rows[0])
    assert not missing, f"Missing absence columns: {sorted(missing)}"
    ids=[r["sample_id"] for r in rows]
    assert len(ids)==len(set(ids)), "Duplicate absence sample_id values"
    by_contract=defaultdict(set)
    for r in rows:
        by_contract[r["contract_id"]].add(r["annotation_partition"])
        assert r["annotation_partition"] in {"calibration","development","locked_test"}
    crossed={k:v for k,v in by_contract.items() if len(v)>1}
    assert not crossed, f"Absence contracts cross partitions: {len(crossed)}"
    print("absence_rows",len(rows))
    print("absence_partitions",dict(Counter(r["annotation_partition"] for r in rows)))
    print("absence_contracts",len(by_contract))
    print("absence_cross_partition_contracts",len(crossed))
    return True

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--main",type=Path,default=Path("data/risk/gold/gold_annotations.csv"))
    ap.add_argument("--absence",type=Path)
    args=ap.parse_args()
    main_rows=read_csv(args.main)
    validate_main(main_rows)
    if args.absence and args.absence.exists():
        validate_absence(read_csv(args.absence))
    print("GOLD_QUEUE_VALIDATION_OK")

if __name__=="__main__":
    main()
