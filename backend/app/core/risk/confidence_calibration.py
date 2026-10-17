"""Evidence-support calibration with explicit abstention when no valid artifact exists.

The probability target is whether the system's predicted YES/NO decision is
correct against adjudicated reviewer labels. It is not risk severity, probability
of loss, or probability that a contract is generally risky.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

SUPPORT_SCORE_VERSION = "support-score-v2-evidence-agreement-indicator"
CALIBRATION_ARTIFACT = (
    Path(__file__).resolve().parents[4]
    / "data" / "risk" / "calibration" / "confidence_calibration.json"
)


@lru_cache(maxsize=8)
def _read_artifact(path: str, mtime_ns: int, size: int) -> dict[str, Any] | None:
    del mtime_ns, size  # These values are cache invalidation keys.
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def confidence_from_support_score(
    raw_support_score: float | int | None,
    *,
    playbook_hash: str | None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Return calibrated prediction-correctness probability only if all gates pass."""
    result = {
        "confidence": None,
        "confidence_status": "UNCALIBRATED",
        "confidence_target": "PREDICTION_CORRECTNESS",
        "confidence_calibration_version": None,
    }
    try:
        score = float(raw_support_score)
    except (TypeError, ValueError):
        result["confidence_status"] = "NOT_ESTIMATED"
        return result
    if not math.isfinite(score) or not 0.0 <= score <= 1.0:
        result["confidence_status"] = "NOT_ESTIMATED"
        return result

    path = Path(artifact_path or CALIBRATION_ARTIFACT)
    try:
        stat = path.stat()
    except OSError:
        return result
    artifact = _read_artifact(str(path), stat.st_mtime_ns, stat.st_size)
    if artifact is None:
        result["confidence_status"] = "CALIBRATION_INVALID"
        return result
    if artifact.get("calibration_status") != "VALIDATED_ON_LOCKED_TEST":
        result["confidence_status"] = "CALIBRATION_NOT_VALIDATED"
        return result
    # Do not trust a status string alone. The runtime re-checks the audit
    # metadata and locked-test gates before treating an artifact as calibrated.
    metrics = artifact.get("locked_test_metrics")
    try:
        calibration_rows = int(artifact.get("calibration_rows", 0))
        calibration_contracts = int(artifact.get("calibration_contract_count", 0))
        calibration_correct = int(artifact.get("calibration_correct_count", 0))
        calibration_incorrect = int(artifact.get("calibration_incorrect_count", 0))
        test_rows = int(artifact.get("locked_test_rows", 0))
        test_contracts = int(artifact.get("locked_test_contract_count", 0))
        test_correct = int((metrics or {}).get("test_correct_count", 0))
        test_incorrect = int((metrics or {}).get("test_incorrect_count", 0))
        brier = float((metrics or {})["brier_calibrated"])
        baseline_brier = float((metrics or {})["brier_constant_prevalence_baseline"])
        ece = float((metrics or {})["ece_10_bins"])
        improvement_ci = (metrics or {})["brier_improvement_ci_95"]
        improvement_ci_low = float(improvement_ci[0])
        improvement_ci_high = float(improvement_ci[1])
        dataset_sha256 = str(artifact.get("dataset_sha256") or "")
        audit_gates_ok = (
            calibration_rows >= 300
            and calibration_contracts >= 50
            and calibration_correct >= 30
            and calibration_incorrect >= 30
            and calibration_correct + calibration_incorrect == calibration_rows
            and test_rows >= 100
            and test_contracts >= 25
            and test_correct >= 15
            and test_incorrect >= 15
            and test_correct + test_incorrect == test_rows
            and math.isfinite(brier)
            and math.isfinite(baseline_brier)
            and math.isfinite(ece)
            and math.isfinite(improvement_ci_low)
            and math.isfinite(improvement_ci_high)
            and improvement_ci_low <= improvement_ci_high
            and improvement_ci_low > 0.0
            and brier < baseline_brier
            and 0.0 <= ece <= 0.15
            and len(dataset_sha256) == 64
            and all(ch in "0123456789abcdef" for ch in dataset_sha256.lower())
            and bool(artifact.get("calibration_version"))
            and artifact.get("dual_annotator_required") is True
            and artifact.get("adjudicator_required") is True
            and artifact.get("contract_disjoint") is True
        )
    except (KeyError, TypeError, ValueError):
        audit_gates_ok = False
    if not audit_gates_ok:
        result["confidence_status"] = "CALIBRATION_AUDIT_GATES_FAILED"
        return result
    if artifact.get("target") != "PREDICTION_CORRECTNESS":
        result["confidence_status"] = "CALIBRATION_TARGET_MISMATCH"
        return result
    if artifact.get("support_score_version") != SUPPORT_SCORE_VERSION:
        result["confidence_status"] = "CALIBRATION_VERSION_MISMATCH"
        return result
    if not playbook_hash or artifact.get("playbook_hash") != playbook_hash:
        result["confidence_status"] = "CALIBRATION_STALE_FOR_PLAYBOOK"
        return result

    try:
        coefficient = float(artifact["coefficient"])
        intercept = float(artifact["intercept"])
    except (KeyError, TypeError, ValueError):
        result["confidence_status"] = "CALIBRATION_INVALID"
        return result
    if not math.isfinite(coefficient) or not math.isfinite(intercept):
        result["confidence_status"] = "CALIBRATION_INVALID"
        return result

    z = intercept + coefficient * score
    if z >= 0:
        probability = 1.0 / (1.0 + math.exp(-min(z, 700.0)))
    else:
        exp_z = math.exp(max(z, -700.0))
        probability = exp_z / (1.0 + exp_z)
    result.update({
        "confidence": round(float(probability), 6),
        "confidence_status": "CALIBRATED_PREDICTION_CORRECTNESS",
        "confidence_calibration_version": artifact.get("calibration_version"),
    })
    return result
