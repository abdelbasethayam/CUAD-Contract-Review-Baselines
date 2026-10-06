#!/usr/bin/env python3
"""Audit-focused evaluation: evidence support, citation support, coverage, and abstention."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def parse_json(value):
    try:
        parsed = json.loads(str(value or ""))
        return parsed
    except (TypeError, json.JSONDecodeError):
        return None


def evidence_support_rate(df: pd.DataFrame) -> dict:
    if "evidence" not in df.columns or "clause_text" not in df.columns:
        return {"available": False}
    positives = df["pred_risk"].astype(str).str.upper().isin({"YES", "1", "TRUE"})
    rows = df.loc[positives]
    if rows.empty:
        return {"available": True, "n_positive": 0, "support_rate": None}
    supported = [
        bool(str(ev or "").strip()) and str(ev).strip() in str(text or "")
        for ev, text in zip(rows["evidence"], rows["clause_text"])
    ]
    return {
        "available": True,
        "n_positive": int(len(rows)),
        "support_rate": float(np.mean(supported)),
    }


def citation_support_rate(df: pd.DataFrame) -> dict:
    if "cited_source_ids" not in df.columns or "retrieved_source_ids" not in df.columns:
        return {"available": False}
    valid = 0
    total = 0
    for cited, retrieved in zip(df["cited_source_ids"], df["retrieved_source_ids"]):
        cited_list = parse_json(cited)
        retrieved_list = parse_json(retrieved)
        if not isinstance(cited_list, list) or not cited_list:
            continue
        total += 1
        valid += int(set(map(str, cited_list)).issubset(set(map(str, retrieved_list or []))))
    return {
        "available": True,
        "n_citations": total,
        "supported_citation_rate": float(valid / total) if total else None,
    }


def checklist_completeness(df: pd.DataFrame) -> dict:
    if not {"expected_check_count", "returned_check_count"} <= set(df.columns):
        return {"available": False}
    expected = pd.to_numeric(df["expected_check_count"], errors="coerce")
    returned = pd.to_numeric(df["returned_check_count"], errors="coerce")
    mask = expected > 0
    ratios = (returned[mask] / expected[mask]).clip(0, 1)
    return {
        "available": True,
        "mean_completeness": float(ratios.mean()) if len(ratios) else None,
        "complete_rate": float(np.mean(ratios >= 1.0)) if len(ratios) else None,
    }


def review_override_rate(df: pd.DataFrame) -> dict:
    if "review_decision" not in df.columns or "pred_risk" not in df.columns:
        return {"available": False}
    review = df[df["review_decision"].astype(str).str.strip() != ""].copy()
    if review.empty:
        return {"available": True, "n_reviewed": 0, "override_rate": None}
    pred = review["pred_risk"].astype(str).str.upper()
    decision = review["review_decision"].astype(str).str.upper()
    overrides = decision != pred
    return {
        "available": True,
        "n_reviewed": int(len(review)),
        "override_rate": float(overrides.mean()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("data/risk/results/audit_quality.json"))
    args = parser.parse_args()

    df = pd.read_csv(args.predictions)
    result = {
        "evidence": evidence_support_rate(df),
        "citation_support": citation_support_rate(df),
        "checklist_completeness": checklist_completeness(df),
        "review_override": review_override_rate(df),
        "scope": {
            "n_rows": int(len(df)),
            "n_contracts": int(df["contract_id"].nunique()) if "contract_id" in df.columns else None,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
