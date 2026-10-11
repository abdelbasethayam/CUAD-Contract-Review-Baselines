#!/usr/bin/env python3
"""Compare one-shot and batched cross/document synthetic-run outputs.

This is an engineering ablation on authored synthetic fixtures, not a test of
real-contract accuracy.
"""
from __future__ import annotations
import csv, hashlib, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE_JSONL = ROOT / "data/risk/evaluation/cross_document_v1/archive/cross_document_model_scenarios_pre_batching_20261009.jsonl"
CURRENT_JSONL = ROOT / "data/risk/results/cross_document_model_scenarios.jsonl"
OUT_JSON = ROOT / "data/risk/results/cross_document_model_scenario_comparison.json"
OUT_MD = ROOT / "data/risk/results/cross_document_model_scenario_comparison.md"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> dict[str, dict]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        result[str(row["scenario_id"])] = row
    return result


def conformance(rows: dict[str, dict]) -> dict:
    matches = sum(bool(row.get("matches_synthetic_expected_status")) for row in rows.values())
    n = len(rows)
    by_type = {}
    for scenario_type in ("positive", "control", "incomplete"):
        subset = [row for row in rows.values() if row.get("scenario_type") == scenario_type]
        hit = sum(bool(row.get("matches_synthetic_expected_status")) for row in subset)
        by_type[scenario_type] = {"cases": len(subset), "matches": hit, "rate": hit / len(subset) if subset else None}
    return {
        "cases": n,
        "matches": matches,
        "rate": matches / n if n else None,
        "status_counts": dict(Counter(row.get("observed_status") for row in rows.values())),
        "by_type": by_type,
    }


def main() -> int:
    if not BASE_JSONL.is_file() or not CURRENT_JSONL.is_file():
        raise SystemExit("Both archived one-shot and current batched JSONL files are required.")
    base = read_rows(BASE_JSONL)
    current = read_rows(CURRENT_JSONL)
    common = sorted(set(base) & set(current))
    if len(common) != 39 or len(base) != 39 or len(current) != 39:
        raise SystemExit(f"Expected identical 39-case sets; baseline={len(base)}, current={len(current)}, common={len(common)}")

    changes = []
    for key in common:
        old = base[key]
        new = current[key]
        if old.get("observed_status") != new.get("observed_status"):
            changes.append({
                "scenario_id": key,
                "scenario_type": new.get("scenario_type"),
                "expected_status": new.get("expected_status"),
                "before": old.get("observed_status"),
                "after": new.get("observed_status"),
                "before_matches": bool(old.get("matches_synthetic_expected_status")),
                "after_matches": bool(new.get("matches_synthetic_expected_status")),
            })
    b = conformance(base)
    c = conformance(current)
    report = {
        "schema_version": 1,
        "status": "COMPLETED",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "comparison_type": "ONE_SHOT_VS_BATCHED_SYNTHETIC_ENGINE_ABLATION",
        "baseline_path": str(BASE_JSONL.relative_to(ROOT)),
        "current_path": str(CURRENT_JSONL.relative_to(ROOT)),
        "baseline_sha256": sha(BASE_JSONL),
        "current_sha256": sha(CURRENT_JSONL),
        "case_count": len(common),
        "same_case_set": True,
        "one_shot": b,
        "batched": c,
        "conformance_delta_cases": c["matches"] - b["matches"],
        "conformance_delta_rate": (c["rate"] - b["rate"]) if c["rate"] is not None and b["rate"] is not None else None,
        "status_changes_count": len(changes),
        "status_changes": changes,
        "interpretation": (
            "This is a code-path ablation on 39 hand-authored synthetic fixtures. It measures whether the "
            "batching change improves fixture-status conformance and preserves outputs under the constructed "
            "scenarios. It is not human gold, not real-contract accuracy, and not legal correctness."
        ),
        "code_hashes": {
            "analyzer": current.get(common[0], {}).get("analyzer_code_sha256"),
            "runner": current.get(common[0], {}).get("runner_code_sha256"),
        },
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = [
        "# Cross-Clause / Document-Level Batching Ablation",
        "",
        "**Important:** synthetic fixture comparison only; not human gold or real-contract accuracy.",
        "",
        f"- Cases compared: {len(common)}",
        f"- Same scenario IDs in both runs: {report['same_case_set']}",
        f"- One-shot conformance: {b['matches']}/{b['cases']} ({b['rate']:.1%})",
        f"- Batched conformance: {c['matches']}/{c['cases']} ({c['rate']:.1%})",
        f"- Change: {report['conformance_delta_cases']:+d} cases ({report['conformance_delta_rate']:+.1%})",
        f"- Scenario decisions changed: {len(changes)}",
        "",
        "| Run | Positive matches | Control matches | Incomplete matches | Observed statuses |",
        "|---|---:|---:|---:|---|",
        f"| One-shot | {b['by_type']['positive']['matches']}/13 | {b['by_type']['control']['matches']}/13 | {b['by_type']['incomplete']['matches']}/13 | {b['status_counts']} |",
        f"| Batched | {c['by_type']['positive']['matches']}/13 | {c['by_type']['control']['matches']}/13 | {c['by_type']['incomplete']['matches']}/13 | {c['status_counts']} |",
        "",
        "## Status changes",
        "",
        "| Scenario | Type | Expected | Before | After |",
        "|---|---|---|---|---|",
    ]
    for row in changes:
        md.append(f"| {row['scenario_id']} | {row['scenario_type']} | {row['expected_status']} | {row['before']} | {row['after']} |")
    md += [
        "",
        "## Reproducibility",
        "",
        f"- Baseline SHA-256: {report['baseline_sha256']}",
        f"- Batched SHA-256: {report['current_sha256']}",
        f"- Analyzer code SHA-256: {report['code_hashes']['analyzer']}",
        f"- Runner code SHA-256: {report['code_hashes']['runner']}",
        "",
        report["interpretation"],
        "",
    ]
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"status": report["status"], "one_shot": b, "batched": c, "delta": report["conformance_delta_cases"], "changed": len(changes), "json": str(OUT_JSON.relative_to(ROOT)), "markdown": str(OUT_MD.relative_to(ROOT))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
