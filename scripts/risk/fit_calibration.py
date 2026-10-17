#!/usr/bin/env python3
"""Fit a confidence calibrator only from adjudicated, contract-disjoint labels.

No artifact is written unless both calibration and locked-test partitions meet
minimum sample/contract diversity gates and calibrated Brier score beats the
constant-prevalence baseline. These are release guardrails, not proof of legal
correctness or universal calibration.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.core.risk.risk_playbook import load_playbook
from app.core.risk.confidence_calibration import SUPPORT_SCORE_VERSION

DEFAULT_DATA = ROOT / "data" / "risk" / "gold" / "risk_finding_adjudication.csv"
DEFAULT_OUTPUT = ROOT / "data" / "risk" / "calibration" / "confidence_calibration.json"
REQUIRED = {
    "contract_id", "finding_id", "check_id", "playbook_hash",
    "support_score_version", "predicted_risk", "adjudicated_risk",
    "raw_support_score", "split", "adjudication_status",
    "annotator_1_id", "annotator_1_risk", "annotator_2_id", "annotator_2_risk",
    "adjudicator_id", "adjudication_notes",
}


def _yes_no(value: str) -> int | None:
    token = str(value or "").strip().upper()
    if token in {"YES", "TRUE", "1"}:
        return 1
    if token in {"NO", "FALSE", "0"}:
        return 0
    return None


def _ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for index, (low, high) in enumerate(zip(edges[:-1], edges[1:])):
        mask = (p >= low) & ((p < high) if index < bins - 1 else (p <= high))
        if not np.any(mask):
            continue
        total += float(np.mean(mask)) * abs(float(np.mean(y[mask])) - float(np.mean(p[mask])))
    return total


def _brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((y - p) ** 2))


def _prepare(path: Path, current_playbook_hash: str) -> tuple[list[dict], list[str]]:
    problems = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = sorted(REQUIRED - fields)
        if missing:
            return [], [f"missing_columns:{','.join(missing)}"]
        rows = list(reader)

    prepared = []
    seen = set()
    for line_number, row in enumerate(rows, start=2):
        if str(row.get("adjudication_status") or "").strip().upper() != "ADJUDICATED":
            continue
        predicted = _yes_no(row.get("predicted_risk"))
        gold = _yes_no(row.get("adjudicated_risk"))
        annotator_1 = _yes_no(row.get("annotator_1_risk"))
        annotator_2 = _yes_no(row.get("annotator_2_risk"))
        annotator_1_id = str(row.get("annotator_1_id") or "").strip()
        annotator_2_id = str(row.get("annotator_2_id") or "").strip()
        adjudicator_id = str(row.get("adjudicator_id") or "").strip()
        adjudication_notes = str(row.get("adjudication_notes") or "").strip()
        if predicted is None or gold is None:
            problems.append(f"line_{line_number}:invalid_predicted_or_adjudicated_label")
            continue
        if annotator_1 is None or annotator_2 is None:
            problems.append(f"line_{line_number}:both_independent_annotator_labels_required")
            continue
        if not annotator_1_id or not annotator_2_id or annotator_1_id == annotator_2_id:
            problems.append(f"line_{line_number}:two_distinct_annotator_identities_required")
            continue
        if not adjudicator_id:
            problems.append(f"line_{line_number}:adjudicator_identity_required")
            continue
        if (annotator_1 != annotator_2 or gold not in {annotator_1, annotator_2}) and not adjudication_notes:
            problems.append(f"line_{line_number}:disagreement_or_override_requires_adjudication_notes")
            continue
        contract_id = str(row.get("contract_id") or "").strip()
        finding_id = str(row.get("finding_id") or "").strip()
        if not contract_id or not finding_id:
            problems.append(f"line_{line_number}:missing_contract_or_finding_id")
            continue
        if finding_id in seen:
            problems.append(f"duplicate_finding_id:{finding_id}")
            continue
        seen.add(finding_id)
        if str(row.get("playbook_hash") or "").strip() != current_playbook_hash:
            problems.append(f"line_{line_number}:playbook_hash_mismatch")
            continue
        if str(row.get("support_score_version") or "").strip() != SUPPORT_SCORE_VERSION:
            problems.append(f"line_{line_number}:support_score_version_mismatch")
            continue
        try:
            score = float(row.get("raw_support_score"))
        except (TypeError, ValueError):
            problems.append(f"line_{line_number}:invalid_support_score")
            continue
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            problems.append(f"line_{line_number}:support_score_out_of_range")
            continue
        split = str(row.get("split") or "").strip().lower()
        if split not in {"calibration", "test"}:
            problems.append(f"line_{line_number}:split_must_be_calibration_or_test")
            continue
        prepared.append({
            "contract_id": contract_id,
            "finding_id": finding_id,
            "check_id": str(row.get("check_id") or ""),
            "predicted": predicted,
            "gold": gold,
            "correct": int(predicted == gold),
            "score": score,
            "split": split,
        })
    return prepared, problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not args.csv.exists():
        print(json.dumps({"status": "BLOCKED", "reason": f"adjudicated dataset not found: {args.csv}"}))
        return 2

    playbook = load_playbook()
    rows, problems = _prepare(args.csv, str(playbook.get("playbook_hash") or ""))
    calibration = [row for row in rows if row["split"] == "calibration"]
    test = [row for row in rows if row["split"] == "test"]
    report = {
        "status": "BLOCKED",
        "calibration_rows": len(calibration),
        "test_rows": len(test),
        "calibration_contracts": len({row["contract_id"] for row in calibration}),
        "test_contracts": len({row["contract_id"] for row in test}),
        "problems": problems,
    }
    if problems:
        print(json.dumps(report, indent=2))
        return 2

    cal_y = np.asarray([row["correct"] for row in calibration], dtype=float)
    cal_x = np.asarray([row["score"] for row in calibration], dtype=float).reshape(-1, 1)
    test_y = np.asarray([row["correct"] for row in test], dtype=float)
    test_x = np.asarray([row["score"] for row in test], dtype=float).reshape(-1, 1)
    cal_counts = np.bincount(cal_y.astype(int), minlength=2)
    test_counts = np.bincount(test_y.astype(int), minlength=2)
    overlap = {row["contract_id"] for row in calibration} & {row["contract_id"] for row in test}
    gates = {
        "calibration_rows_at_least_300": len(calibration) >= 300,
        "calibration_contracts_at_least_50": len({row["contract_id"] for row in calibration}) >= 50,
        "calibration_correct_and_incorrect_at_least_30": int(cal_counts.min()) >= 30,
        "calibration_score_has_at_least_5_unique_values": len({row["score"] for row in calibration}) >= 5,
        "locked_test_rows_at_least_100": len(test) >= 100,
        "locked_test_contracts_at_least_25": len({row["contract_id"] for row in test}) >= 25,
        "locked_test_correct_and_incorrect_at_least_15": int(test_counts.min()) >= 15,
        "contract_disjoint_calibration_test": not overlap,
    }
    report["gates"] = gates
    if not all(gates.values()):
        report["failed_gates"] = [name for name, passed in gates.items() if not passed]
        print(json.dumps(report, indent=2))
        return 2

    model = LogisticRegression(C=1e6, solver="lbfgs", max_iter=2000)
    model.fit(cal_x, cal_y)
    coefficient = float(model.coef_[0][0])
    intercept = float(model.intercept_[0])
    test_prob = model.predict_proba(test_x)[:, 1]
    prevalence = float(np.mean(test_y))
    baseline_prob = np.full_like(test_y, prevalence)
    calibrated_brier = _brier(test_y, test_prob)
    baseline_brier = _brier(test_y, baseline_prob)
    calibrated_ece = _ece(test_y, test_prob)
    test_metrics = {
        "brier_calibrated": calibrated_brier,
        "brier_constant_prevalence_baseline": baseline_brier,
        "brier_improvement_over_baseline": baseline_brier - calibrated_brier,
        "ece_10_bins": calibrated_ece,
        "test_prevalence_of_correct_predictions": prevalence,
        "test_correct_count": int(np.sum(test_y)),
        "test_incorrect_count": int(len(test_y) - np.sum(test_y)),
    }
    report["locked_test_metrics"] = test_metrics
    if not (calibrated_brier < baseline_brier and calibrated_ece <= 0.15):
        report["status"] = "BLOCKED"
        report["failed_gates"] = ["calibrator_did_not_beat_constant_baseline_or_ece_exceeded_0.15"]
        print(json.dumps(report, indent=2))
        return 2

    artifact = {
        "schema_version": 1,
        "calibration_version": "prediction-correctness-logistic-v1",
        "calibration_status": "VALIDATED_ON_LOCKED_TEST",
        "target": "PREDICTION_CORRECTNESS",
        "target_definition": "Probability that the system's predicted YES/NO risk decision matches the adjudicated reviewer label.",
        "model_type": "logistic_sigmoid",
        "calibration_method": "one-feature logistic regression on raw_support_score",
        "support_score_version": SUPPORT_SCORE_VERSION,
        "playbook_hash": playbook.get("playbook_hash"),
        "coefficient": coefficient,
        "intercept": intercept,
        "calibration_rows": len(calibration),
        "calibration_contract_count": len({row["contract_id"] for row in calibration}),
        "calibration_correct_count": int(np.sum(cal_y)),
        "calibration_incorrect_count": int(len(cal_y) - np.sum(cal_y)),
        "locked_test_rows": len(test),
        "locked_test_contract_count": len({row["contract_id"] for row in test}),
        "locked_test_metrics": test_metrics,
        "dataset_sha256": hashlib.sha256(args.csv.read_bytes()).hexdigest(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "Calibration applies only to prediction correctness for this playbook and support-score version.",
            "It is not a probability of loss, legal enforceability, or severity.",
            "Recalibration is required after material changes to prompts, rules, models, or score construction.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    report["status"] = "PASS"
    report["artifact"] = str(args.output)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
