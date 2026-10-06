#!/usr/bin/env python3
"""Evaluate human-reviewed clause-family absence candidates.

A NOT_FOUND_BY_SEARCH row becomes a measured search miss only after a human
adjudicates full-contract presence. This metric is deliberately separate from
risk classification precision/recall.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/risk/results/absence_metrics.json"),
    )
    parser.add_argument(
        "--partition",
        choices=["calibration", "development", "locked_test"],
        default="locked_test",
    )
    args = parser.parse_args()

    df = pd.read_csv(args.queue)
    if "annotation_partition" not in df.columns:
        raise SystemExit("Absence evaluation requires annotation_partition.")
    df = df[df["annotation_partition"].astype(str) == args.partition].copy()
    if df.empty:
        raise SystemExit("No rows in selected partition.")

    presence = df["adjudicated_presence"].astype(str).str.upper().str.strip()
    labeled = presence.isin({"PRESENT", "NOT_FOUND", "NOT_APPLICABLE", "UNCERTAIN"})
    df = df.loc[labeled].copy()
    presence = presence.loc[labeled]

    present = presence.eq("PRESENT")
    not_found = presence.eq("NOT_FOUND")
    uncertain = presence.eq("UNCERTAIN")
    not_applicable = presence.eq("NOT_APPLICABLE")

    result = {
        "partition": args.partition,
        "n_reviewed": int(len(df)),
        "search_miss_count": int(present.sum()),
        "search_miss_rate": float(present.mean()) if len(df) else None,
        "confirmed_not_found_rate": float(not_found.mean()) if len(df) else None,
        "not_applicable_rate": float(not_applicable.mean()) if len(df) else None,
        "uncertain_rate": float(uncertain.mean()) if len(df) else None,
        "metric_definition": (
            "Among candidate clause families initially marked NOT_FOUND_BY_SEARCH, "
            "the search miss rate is the fraction a human finds present somewhere "
            "in the full contract."
        ),
    }

    if "adjudicated_risk" in df.columns:
        risk = df["adjudicated_risk"].astype(str).str.upper().str.strip()
        applicable = presence.eq("PRESENT") | presence.eq("NOT_FOUND")
        risk = risk.loc[applicable]
        result["risk_when_present_or_reviewed"] = {
            "n": int(len(risk)),
            "positive_rate": float(risk.eq("YES").mean()) if len(risk) else None,
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
