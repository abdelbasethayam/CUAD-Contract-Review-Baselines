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


def calibrate_risk_probability(raw_score: float | None, calibration: dict | None = None) -> float | None:
    data = calibration if calibration is not None else load_calibration()
    return _interp(raw_score, data.get("risk_probability"))


def calibrate_severity(raw_score: float | None, calibration: dict | None = None) -> dict | None:
    data = calibration if calibration is not None else load_calibration()
    if raw_score is None:
        return None
    med = _interp(raw_score, data.get("p_ge_medium"))
    high = _interp(raw_score, data.get("p_ge_high"))
    if med is None or high is None:
        return None
    high = min(max(high, 0.0), 1.0)
    med = min(max(med, high), 1.0)
    probs = {
        "LOW": round(1.0 - med, 6),
        "MEDIUM": round(med - high, 6),
        "HIGH": round(high, 6),
    }
    level = max(probs, key=probs.get)
    return {"level": level, "probabilities": probs}


__all__ = ["load_calibration", "calibrate_risk_probability", "calibrate_severity"]
