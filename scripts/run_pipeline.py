#!/usr/bin/env python3
"""Run or resume the complete Phase 1 + Phase 2 contract review pipeline."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def emit(event: dict) -> None:
    if event.get("type") == "progress":
        parts = [event.get("stage", "pipeline"), event.get("message", "")]
        if event.get("current") is not None and event.get("total") is not None:
            parts.append(f"({event['current']}/{event['total']})")
        if event.get("analysis_id"):
            parts.append(f"[{event['analysis_id']}]")
        print(" ".join(str(x) for x in parts))


def run(source: Path) -> dict:
    from backend.app.services.rag_service import classify_contract

    return classify_contract(
        source,
        progress_callback=emit,
        filename=source.name,
    )


def resume(analysis_id: str) -> dict:
    from backend.app.core.config import RUNS_DIR
    from backend.app.core.risk.run_store import AnalysisRun
    from backend.app.services.rag_service import classify_contract

    root = Path(RUNS_DIR) / analysis_id
    if not root.exists():
        raise SystemExit(f"Run not found: {root}")

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    source = next(root.glob("source.*"), root / "source")
    if not source.exists():
        raise SystemExit("The persistent source artifact is missing.")

    return classify_contract(
        source,
        progress_callback=emit,
        filename=manifest.get("source", {}).get("filename") or source.name,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run")
    run_p.add_argument("source", type=Path)

    resume_p = sub.add_parser("resume")
    resume_p.add_argument("analysis_id")

    args = parser.parse_args()
    result = run(args.source) if args.command == "run" else resume(args.analysis_id)
    print(json.dumps({
        "analysis_id": result["analysis_id"],
        "filename": result["filename"],
        "clauses": len(result["clauses"]),
        "risk_status": result["contract_risk_assessment"].get("status"),
        "run_dir": result["run_dir"],
    }, indent=2))


if __name__ == "__main__":
    main()
