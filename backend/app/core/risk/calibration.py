"""Runtime application of persisted probability/severity calibration curves."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..config import RISK_CALIBRATION_PATH


def _interp(x: float | None, curve: dict | None) -> float | None:
    if x is None or not curve:
        return None
    xs = curve.get("x") or []
    ys = curve.get("y") or []
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    return round(float(np.interp(float(x), np.asarray(xs, dtype=float), np.asarray(ys, dtype=float))), 6)


def load_calibration(path: Path | None = None) -> dict:
    target = Path(path or RISK_CALIBRATION_PATH)
    if not target.exists():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def calibrate_risk_probability(final_score: float | None, calibration: dict | None = None) -> float | None:
    data = calibration if calibration is not None else load_calibration()
    if data.get("calibration_input") not in {"calibration_score_0_to_20_with_zero_for_nonpositive_or_unscored", "final_score_0_to_20"}:
        return None
    return _interp(final_score, data.get("risk_probability"))


def calibrate_severity(final_score: float | None, calibration: dict | None = None) -> dict | None:
    data = calibration if calibration is not None else load_calibration()
    if data.get("calibration_input") not in {None, "final_score_0_to_20"}:
        return None
    if final_score is None:
        return None
    low = _interp(final_score, data.get("p_ge_low"))
    med = _interp(final_score, data.get("p_ge_medium"))
    high = _interp(final_score, data.get("p_ge_high"))
    critical = _interp(final_score, data.get("p_ge_critical"))
    if any(value is None for value in (low, med, high, critical)):
        return None
    low, med, high, critical = [min(max(float(v), 0.0), 1.0) for v in (low, med, high, critical)]
    low = max(low, med)
    med = max(med, high)
    high = max(high, critical)
    probs = {
        "INFORMATIONAL": round(1.0 - low, 6),
        "LOW": round(low - med, 6),
        "MEDIUM": round(med - high, 6),
        "HIGH": round(high - critical, 6),
        "CRITICAL": round(critical, 6),
    }
    level = max(probs, key=probs.get)
    return {"level": level, "probabilities": probs}


__all__ = ["load_calibration", "calibrate_risk_probability", "calibrate_severity"]
