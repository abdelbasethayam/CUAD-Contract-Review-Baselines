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

SUPPORT_SCORE_VERSION = "support-score-v1"
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
