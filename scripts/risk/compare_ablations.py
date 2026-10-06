#!/usr/bin/env python3
"""Paired ablation statistics with contract-level permutation and Holm correction."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd


def _to_binary(series: pd.Series) -> np.ndarray:
    return series.astype(str).str.upper().map(
        {"YES": 1, "NO": 0, "1": 1, "0": 0, "TRUE": 1, "FALSE": 0}
    ).to_numpy(dtype=float)


def paired_contract_differences(a: pd.DataFrame, b: pd.DataFrame) -> np.ndarray:
    keys = ["contract_id"]
    merged = a[["contract_id", "gold_risk", "pred_risk"]].merge(
        b[["contract_id", "gold_risk", "pred_risk"]],
        on=["contract_id", "gold_risk"],
        suffixes=("_a", "_b"),
    )
    y = _to_binary(merged["gold_risk"])
    pa = _to_binary(merged["pred_risk_a"])
    pb = _to_binary(merged["pred_risk_b"])
    merged = merged.assign(_y=y, _a=pa, _b=pb)
    # Macro-average over contracts so long contracts do not dominate.
    diffs = []
    for _, group in merged.groupby("contract_id", sort=True):
        diffs.append(float((group["_b"] == group["_y"]).mean() - (group["_a"] == group["_y"]).mean()))
    return np.asarray(diffs, dtype=float)


def paired_sign_flip_pvalue(diffs: np.ndarray, permutations: int = 20000, seed: int = 42) -> float:
    diffs = np.asarray(diffs, dtype=float)
    if len(diffs) == 0:
        return 1.0
    observed = abs(float(np.mean(diffs)))
    rng = np.random.default_rng(seed)
    if len(diffs) <= 20:
        values = []
        for signs in itertools.product((-1.0, 1.0), repeat=len(diffs)):
            values.append(abs(float(np.mean(diffs * np.asarray(signs)))))
        return float((sum(value >= observed for value in values) + 1) / (len(values) + 1))
    hits = 0
    for _ in range(permutations):
        signs = rng.choice(np.asarray([-1.0, 1.0]), size=len(diffs))
        if abs(float(np.mean(diffs * signs))) >= observed:
            hits += 1
    return float((hits + 1) / (permutations + 1))


def bootstrap_ci(diffs: np.ndarray, n: int = 10000, seed: int = 42) -> dict:
    diffs = np.asarray(diffs, dtype=float)
    if len(diffs) == 0:
        return {"estimate": None, "ci95_low": None, "ci95_high": None}
    rng = np.random.default_rng(seed)
    samples = rng.choice(diffs, size=(n, len(diffs)), replace=True).mean(axis=1)
    return {
        "estimate": float(np.mean(diffs)),
        "ci95_low": float(np.quantile(samples, 0.025)),
        "ci95_high": float(np.quantile(samples, 0.975)),
        "unit": "contract",
        "n_bootstrap": n,
    }


def holm_adjust(pvalues: dict[str, float]) -> dict[str, float]:
    ordered = sorted(pvalues.items(), key=lambda item: item[1])
    m = len(ordered)
    adjusted = {}
    running = 0.0
    for index, (name, pvalue) in enumerate(ordered):
        value = min(1.0, max(running, (m - index) * pvalue))
        running = value
        adjusted[name] = value
    return adjusted


def load_manifest(path: Path) -> dict[str, Path]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(name): Path(value) for name, value in (data.get("models") or {}).items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help='JSON object like {"baseline":"a.csv","models":{"A":"a.csv","B":"b.csv"}}',
    )
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--permutations", type=int, default=20000)
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--out", type=Path, default=Path("data/risk/results/ablation_tests.json"))
    args = parser.parse_args()

    paths = load_manifest(args.manifest)
    if args.baseline not in paths:
        raise SystemExit(f"Baseline {args.baseline!r} missing from manifest.")

    baseline = pd.read_csv(paths[args.baseline])
    results = {}
    pvalues = {}

    for name, path in paths.items():
        if name == args.baseline:
            continue
        current = pd.read_csv(path)
        diffs = paired_contract_differences(baseline, current)
        p = paired_sign_flip_pvalue(
            diffs,
            permutations=args.permutations,
        )
        ci = bootstrap_ci(diffs, n=args.bootstrap)
        results[name] = {
            "baseline": args.baseline,
            "paired_contract_difference": ci,
            "p_value_uncorrected": p,
            "n_contracts": int(len(diffs)),
            "test": "paired_contract_sign_flip_permutation",
        }
        pvalues[name] = p

    adjusted = holm_adjust(pvalues)
    for name, p in adjusted.items():
        results[name]["p_value_holm"] = p

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "multiple_comparison_correction": "Holm",
        "results": results,
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
