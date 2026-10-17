#!/usr/bin/env python3
"""Run an API-level synthetic-contract smoke test and save its full response."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, default=ROOT / "data/risk/demo_contract_smoke.txt")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--out", type=Path, default=ROOT / "data/risk/results/smoke_upload_api_result.json")
    args = parser.parse_args()
    source = args.file.resolve()
    if not source.is_file():
        raise SystemExit(f"Input does not exist: {source}")

    content_type = "application/pdf" if source.suffix.lower() == ".pdf" else "text/plain"
    started = time.monotonic()
    with source.open("rb") as handle:
        response = requests.post(
            args.base_url.rstrip("/") + "/documents/classify",
            files={"file": (source.name, handle, content_type)},
            timeout=(15, args.timeout),
        )
    elapsed = round(time.monotonic() - started, 3)
    try:
        payload = response.json()
    except ValueError:
        payload = {"non_json_response": response.text[:2000]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "http_status": response.status_code,
        "elapsed_seconds": elapsed,
        "source_file": str(source),
        "source_sha256": __import__("hashlib").sha256(source.read_bytes()).hexdigest(),
        "base_url": args.base_url,
        "response": payload,
    }
    args.out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    assessment = payload.get("contract_risk_assessment") or {}
    clauses = payload.get("clauses") or []
    summary = {
        "http_status": response.status_code,
        "elapsed_seconds": elapsed,
        "source_file": source.name,
        "analysis_id": payload.get("analysis_id"),
        "pipeline_status": payload.get("pipeline_status"),
        "clause_count": payload.get("total_clauses"),
        "clauses_with_risk_findings": sum(bool(x.get("risk_findings")) for x in clauses),
        "clause_risk_finding_count": sum(len(x.get("risk_findings") or []) for x in clauses),
        "cross_clause_finding_count": len(assessment.get("cross_clause_findings") or []),
        "document_finding_count": len(assessment.get("document_findings") or []),
        "assessment_status": assessment.get("status") or assessment.get("overall_status"),
        "overall_risk": assessment.get("overall_risk"),
        "download_artifacts": payload.get("downloads") or {},
        "response_path": str(args.out),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    response.raise_for_status()
    if not payload.get("analysis_id") or not clauses:
        raise SystemExit("Smoke test did not return an analysis_id and clauses.")
    if payload.get("pipeline_status") not in (None, "COMPLETED"):
        raise SystemExit(f"Pipeline did not complete: {payload.get('pipeline_status')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
