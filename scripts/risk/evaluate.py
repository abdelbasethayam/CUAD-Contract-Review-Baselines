#!/usr/bin/env python3
"""Statistical evaluation for clause-level risk predictions.

Expected prediction CSV columns:
  contract_id, gold_risk, pred_risk, pred_probability,
  gold_severity, pred_severity, evidence, gold_evidence

Bootstrap resampling is done at the contract level to respect within-contract
correlation. Optional paired model comparison uses exact McNemar plus paired
cluster bootstrap for accuracy differences.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest, spearmanr
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    brier_score_loss,
    cohen_kappa_score,
    matthews_corrcoef,
    precision_recall_fscore_support,
    precision_recall_curve,
    roc_auc_score,
    auc,
    confusion_matrix,
    f1_score,
)


def binary_metrics(y, pred, prob) -> dict:
    y = np.asarray(y).astype(int)
    pred = np.asarray(pred).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    precision, recall, f1, _ = precision_recall_fscore_support(
        y, pred, average="binary", zero_division=0
    )
    out = {
        "prevalence": float(np.mean(y)),
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "precision": float(precision),
        "recall": float(recall),
        "specificity": float(tn / (tn + fp)) if tn + fp else 0.0,
        "f1": float(f1),
        "macro_f1": float(f1_score(y, pred, average="macro", zero_division=0)),
        "mcc": float(matthews_corrcoef(y, pred)),
        "tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn),
    }
    prob = np.asarray(prob, dtype=float)
    finite = np.isfinite(prob)
    if finite.all() and np.unique(y).size == 2:
        out["auroc"] = float(roc_auc_score(y, prob))
        p, r, _ = precision_recall_curve(y, prob)
        out["pr_auc"] = float(auc(r, p))
        out["brier"] = float(brier_score_loss(y, prob))
    else:
        out["probability_metrics_available"] = False
    return out


def ece(y, prob, bins=10) -> float:
    y = np.asarray(y).astype(float)
    prob = np.asarray(prob).astype(float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    score = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (prob >= lo) & (prob < hi if hi < 1 else prob <= hi)
        if not np.any(mask):
            continue
        score += np.mean(mask) * abs(np.mean(y[mask]) - np.mean(prob[mask]))
    return float(score)


def severity_metrics(gold, pred) -> dict:
    keep = [(g, p) for g, p in zip(gold, pred) if g in {"LOW", "MEDIUM", "HIGH"} and p in {"LOW", "MEDIUM", "HIGH"}]
    if not keep:
        return {}
    g = [x[0] for x in keep]
    p = [x[1] for x in keep]
    labels = ["INFORMATIONAL", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    encoded = {label: i for i, label in enumerate(labels)}
    mae = float(np.mean([abs(encoded[a] - encoded[b]) for a, b in zip(g, p)]))
    return {
        "macro_f1": float(f1_score(g, p, labels=labels, average="macro", zero_division=0)),
        "mae": mae,
        "quadratic_weighted_kappa": float(cohen_kappa_score(
            [encoded[x] for x in g], [encoded[x] for x in p], weights="quadratic"
        )),
        "spearman_rho": float(spearmanr(
            [encoded[x] for x in g], [encoded[x] for x in p]
        ).statistic),
        "n": len(keep),
    }


def evidence_f1(gold: list[str], pred: list[str]) -> dict:
    scores = []
    exact = []
    for g, p in zip(gold, pred):
        g = str(g or "")
        p = str(p or "")
        g_tokens = g.split()
        p_tokens = p.split()
        gs, ps = set(g_tokens), set(p_tokens)
        inter = len(gs & ps)
        precision = inter / len(ps) if ps else 0.0
        recall = inter / len(gs) if gs else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 1.0 if not gs and not ps else 0.0)
        exact.append(g.strip() == p.strip())
    return {
        "mean_token_f1": float(np.mean(scores)) if scores else 0.0,
        "exact_match": float(np.mean(exact)) if exact else 0.0,
    }


def abstention_metrics(df: pd.DataFrame) -> dict:
    if "risk_status" not in df.columns:
        return {}
    abstain = df["risk_status"].astype(str).str.upper().eq("INSUFFICIENT_EVIDENCE")
    out = {"abstention_rate": float(abstain.mean()), "coverage": float((~abstain).mean()), "abstentions": int(abstain.sum())}
    if abstain.any() and "gold_risk" in df.columns:
        gold = df.loc[abstain, "gold_risk"].astype(str).str.upper()
        out["positive_rate_among_abstentions"] = float(gold.isin(["YES", "1", "TRUE"]).mean())
    return out

def cluster_bootstrap(df: pd.DataFrame, metric_fn, n: int = 2000, seed: int = 42):
    rng = np.random.default_rng(seed)
    groups = df["contract_id"].astype(str).unique()
    estimates = []
    for _ in range(n):
        sampled = rng.choice(groups, size=len(groups), replace=True)
        chunks = [df[df["contract_id"].astype(str) == group] for group in sampled]
        boot = pd.concat(chunks, ignore_index=True)
        estimates.append(metric_fn(boot))
    estimates = np.asarray(estimates, dtype=float)
    return {
        "estimate": float(metric_fn(df)),
        "ci95_low": float(np.quantile(estimates, 0.025)),
        "ci95_high": float(np.quantile(estimates, 0.975)),
        "n_bootstrap": int(n),
        "unit": "contract",
    }


def mcnemar_exact(a: np.ndarray, b: np.ndarray, y: np.ndarray) -> dict:
    a_correct = a == y
    b_correct = b == y
    b01 = int(np.sum(a_correct & ~b_correct))
    b10 = int(np.sum(~a_correct & b_correct))
    discordant = b01 + b10
    p = 1.0 if discordant == 0 else float(2 * binomtest(min(b01, b10), n=discordant, p=0.5).pvalue)
    return {"a_only_correct": b01, "b_only_correct": b10, "discordant": discordant, "p_value": min(1.0, p)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("data/risk/results/metrics.json"))
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--partition", choices=["calibration", "development", "locked_test"], default="locked_test")
    parser.add_argument("--model-a", type=Path)
    parser.add_argument("--model-b", type=Path)
    args = parser.parse_args()

    df = pd.read_csv(args.predictions)
    if "annotation_partition" in df.columns:
        df = df[df["annotation_partition"].astype(str) == args.partition].copy()
    else:
        raise SystemExit("Evaluation requires annotation_partition metadata.")
    required = {"contract_id", "gold_risk", "pred_risk", "pred_probability"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Missing columns: {sorted(missing)}")

    y = df["gold_risk"].astype(str).str.upper().map({"YES": 1, "NO": 0, "1": 1, "0": 0, "TRUE": 1, "FALSE": 0})
    pred = df["pred_risk"].astype(str).str.upper().map({"YES": 1, "NO": 0, "1": 1, "0": 0, "TRUE": 1, "FALSE": 0})
    mask = y.notna() & pred.notna()
    df = df.loc[mask].copy()
    y = y.loc[mask].to_numpy(dtype=int)
    pred = pred.loc[mask].to_numpy(dtype=int)
    prob = pd.to_numeric(df["pred_probability"], errors="coerce").to_numpy(dtype=float)

    scored_df = df.assign(_y=y, _p=pred)
    result = {
        "binary": binary_metrics(y, pred, prob),
        "calibration": (
            {"ece": ece(y[np.isfinite(prob)], prob[np.isfinite(prob)]),
             "brier": float(brier_score_loss(y[np.isfinite(prob)], prob[np.isfinite(prob)]))}
            if np.isfinite(prob).all()
            else {"available": False, "reason": "pred_probability is not calibrated or contains missing values"}
        ),
        "abstention": abstention_metrics(df),
        "cluster_bootstrap_accuracy": cluster_bootstrap(
            scored_df,
            lambda x: float(accuracy_score(x["_y"], x["_p"])),
            n=args.bootstrap,
        ),
        "cluster_bootstrap_f1": cluster_bootstrap(
            scored_df,
            lambda x: float(f1_score(x["_y"], x["_p"], zero_division=0)),
            n=args.bootstrap,
        ),
    }
    # Optional contract-level view: a contract is positive when any clause is
    # positive, avoiding artificial inflation from many clauses in one contract.
    contract_df = (
        df.assign(_gold=y, _pred=pred)
        .groupby("contract_id", as_index=False)
        .agg(gold_risk=("_gold", "max"), pred_risk=("_pred", "max"))
    )
    if len(contract_df) >= 2 and contract_df["gold_risk"].nunique() == 2:
        result["contract_level"] = {
            "n_contracts": int(len(contract_df)),
            "accuracy": float(accuracy_score(contract_df["gold_risk"], contract_df["pred_risk"])),
            "macro_f1": float(f1_score(contract_df["gold_risk"], contract_df["pred_risk"], average="macro", zero_division=0)),
            "balanced_accuracy": float(balanced_accuracy_score(contract_df["gold_risk"], contract_df["pred_risk"])),
        }

    if {"gold_severity", "pred_severity"} <= set(df.columns):
        result["severity"] = severity_metrics(
            df["gold_severity"].tolist(),
            df["pred_severity"].tolist(),
        )

    if {"annotator_1_risk", "annotator_2_risk"} <= set(df.columns):
        ann = df[["annotator_1_risk", "annotator_2_risk"]].copy()
        ann = ann[(ann["annotator_1_risk"].astype(str).str.strip() != "") & (ann["annotator_2_risk"].astype(str).str.strip() != "")]
        if len(ann):
            result["inter_annotator_cohen_kappa"] = float(
                cohen_kappa_score(ann["annotator_1_risk"], ann["annotator_2_risk"])
            )

    if {"annotator_1_severity", "annotator_2_severity"} <= set(df.columns):
        sev = df[["annotator_1_severity", "annotator_2_severity"]].copy()
        sev = sev[sev["annotator_1_severity"].isin(["INFORMATIONAL", "LOW", "MEDIUM", "HIGH", "CRITICAL"])]
        sev = sev[sev["annotator_2_severity"].isin(["INFORMATIONAL", "LOW", "MEDIUM", "HIGH", "CRITICAL"])]
        if len(sev) >= 2:
            labels = ["INFORMATIONAL", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
            enc = {label: i for i, label in enumerate(labels)}
            result["inter_annotator_severity_quadratic_kappa"] = float(
                cohen_kappa_score(
                    [enc[x] for x in sev["annotator_1_severity"]],
                    [enc[x] for x in sev["annotator_2_severity"]],
                    weights="quadratic",
                )
            )

    if {"gold_evidence", "evidence"} <= set(df.columns):
        result["evidence"] = evidence_f1(
            df["gold_evidence"].tolist(),
            df["evidence"].tolist(),
        )

    if args.model_a and args.model_b:
        a = pd.read_csv(args.model_a)
        b = pd.read_csv(args.model_b)
        merged = a[["contract_id", "gold_risk", "pred_risk"]].merge(
            b[["contract_id", "pred_risk"]], on=["contract_id", "gold_risk"], suffixes=("_a", "_b")
        )
        yy = merged["gold_risk"].astype(str).str.upper().map({"YES": 1, "NO": 0, "1": 1, "0": 0, "TRUE": 1, "FALSE": 0}).to_numpy()
        aa = merged["pred_risk_a"].astype(str).str.upper().map({"YES": 1, "NO": 0, "1": 1, "0": 0, "TRUE": 1, "FALSE": 0}).to_numpy()
        bb = merged["pred_risk_b"].astype(str).str.upper().map({"YES": 1, "NO": 0, "1": 1, "0": 0, "TRUE": 1, "FALSE": 0}).to_numpy()
        result["paired_mcnemar"] = mcnemar_exact(aa, bb, yy)
        merged["_a_correct"] = aa == yy
        merged["_b_correct"] = bb == yy
        groups = merged["contract_id"].astype(str).unique()
        rng = np.random.default_rng(42)
        diffs = []
        for _ in range(args.bootstrap):
            sampled = rng.choice(groups, size=len(groups), replace=True)
            boot = pd.concat(
                [merged[merged["contract_id"].astype(str) == g] for g in sampled],
                ignore_index=True,
            )
            diffs.append(float(boot["_b_correct"].mean() - boot["_a_correct"].mean()))
        result["paired_cluster_bootstrap_accuracy_difference"] = {
            "estimate_b_minus_a": float(merged["_b_correct"].mean() - merged["_a_correct"].mean()),
            "ci95_low": float(np.quantile(diffs, 0.025)),
            "ci95_high": float(np.quantile(diffs, 0.975)),
            "n_bootstrap": args.bootstrap,
            "unit": "contract",
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
