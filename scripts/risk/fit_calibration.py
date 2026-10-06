#!/usr/bin/env python3
"""Fit probability and ordinal-severity calibration from adjudicated gold labels."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss


def fit_curve(x: np.ndarray, y: np.ndarray) -> dict:
    order = np.argsort(x, kind="stable")
    model = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    model.fit(x[order], y[order])
    xs = np.asarray(model.X_thresholds_, dtype=float)
    ys = np.asarray(model.y_thresholds_, dtype=float)
    return {"x": xs.tolist(), "y": ys.tolist()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("data/risk/gold/calibration.json"))
    parser.add_argument("--score-column", default="raw_support_score")
    parser.add_argument("--partition", default="calibration", choices=["calibration", "development"])
    parser.add_argument("--severity-score-column", default="final_score")
    parser.add_argument("--gold-risk-column", default="adjudicated_risk")
    parser.add_argument("--gold-severity-column", default="adjudicated_severity")
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    if "annotation_partition" not in df.columns:
        raise SystemExit("Calibration requires annotation_partition metadata.")
    df = df[df["annotation_partition"].astype(str) == args.partition].copy()
    if not len(df):
        raise SystemExit(f"No adjudicated rows found in partition {args.partition!r}.")
    required = {args.score_column, args.gold_risk_column}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Missing columns: {sorted(missing)}")

    risk_df = df.dropna(subset=[args.score_column]).copy()
    risk_df = risk_df[risk_df[args.gold_risk_column].astype(str).str.strip().isin({"0", "1", "YES", "NO", "TRUE", "FALSE"})]
    if len(risk_df) < 30:
        raise SystemExit("At least 30 adjudicated risk examples are recommended for calibration.")

    x = risk_df[args.score_column].astype(float).to_numpy()
    y = risk_df[args.gold_risk_column].map(
        {"0": 0, "1": 1, "YES": 1, "NO": 0, "TRUE": 1, "FALSE": 0}
    ).astype(float).to_numpy()
    risk_curve = fit_curve(x, y)
    risk_pred = np.interp(x, risk_curve["x"], risk_curve["y"])

    result = {
        "schema_version": 1,
        "method": "isotonic",
        "n_risk_calibration": int(len(x)),
        "risk_probability": risk_curve,
        "calibration_partition": args.partition,
        "severity_score_column": args.severity_score_column,
        "risk_brier": float(brier_score_loss(y, risk_pred)),
    }

    if args.gold_severity_column in df.columns:
        severity_input = args.severity_score_column if args.severity_score_column in df.columns else args.score_column
        sev = df.dropna(subset=[severity_input, args.gold_severity_column]).copy()
        sev = sev[sev[args.gold_severity_column].isin(["LOW", "MEDIUM", "HIGH"])]
        if len(sev) >= 30 and sev[args.gold_severity_column].nunique() >= 2:
            xs = sev[severity_input].astype(float).to_numpy()
            levels = sev[args.gold_severity_column].to_numpy()
            p_med = np.array([1.0 if level in {"MEDIUM", "HIGH"} else 0.0 for level in levels])
            p_high = np.array([1.0 if level == "HIGH" else 0.0 for level in levels])
            result["p_ge_medium"] = fit_curve(xs, p_med)
            result["p_ge_high"] = fit_curve(xs, p_high)
            result["n_severity_calibration"] = int(len(sev))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
