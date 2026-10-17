#!/usr/bin/env python3
"""Audit a completed end-to-end contract-upload smoke run."""
from __future__ import annotations
import argparse
import hashlib, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data/risk/results/smoke_upload_api_result.json"
OUT_DIR = ROOT / "data/risk/results"

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--suffix", default="")
    args = parser.parse_args()
    input_path = args.input if args.input.is_absolute() else ROOT / args.input
    record = json.loads(input_path.read_text(encoding="utf-8"))
    response = record.get("response") or {}
    analysis_id = response.get("analysis_id")
    if not analysis_id:
        raise SystemExit("Smoke output contains no analysis_id.")
    run_dir = ROOT / "data" / "runs" / analysis_id
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    saved_result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    contract_checks = json.loads((run_dir / "contract_checks.json").read_text(encoding="utf-8"))
    clauses = response.get("clauses") or []
    assessment = response.get("contract_risk_assessment") or {}
    clause_map = {
        int(c.get("clause_index")): str(c.get("clause_text") or "")
        for c in clauses if c.get("clause_index") is not None
    }
    positives, target_valid, related_valid, invalid = [], [], [], []
    for clause in clauses:
        for finding in clause.get("risk_findings") or []:
            if finding.get("risk_status") != "POTENTIAL_RISK":
                continue
            evidence = str(finding.get("evidence") or "")
            item = {
                "target_clause": clause.get("clause_index"),
                "check_id": finding.get("check_id"),
                "risk_domain": finding.get("risk_domain"),
                "risk_type": finding.get("risk_type"),
                "evidence_clause_index": finding.get("evidence_clause_index"),
                "evidence_scope": finding.get("evidence_scope"),
                "evidence": evidence,
            }
            positives.append(item)
            if not evidence:
                invalid.append(item)
            elif evidence in str(clause.get("clause_text") or ""):
                target_valid.append(item)
            else:
                context = finding.get("related_contract_context") or []
                source = next((c for c in context if evidence in str(c.get("clause_text") or "")), None)
                if source:
                    related_valid.append({
                        **item,
                        "evidence_clause_index": source.get("clause_index"),
                        "evidence_scope": "related_contract_clause",
                    })
                else:
                    invalid.append(item)

    cross = contract_checks.get("cross_clause_findings") or []
    docs = contract_checks.get("document_findings") or []
    def status_counts(rows):
        return dict(Counter(str(row.get("risk_status") or "MISSING") for row in rows))
    cross_doc_positive = []
    cross_doc_invalid = []
    for finding in cross + docs:
        if finding.get("risk_status") != "POTENTIAL_RISK":
            continue
        evidence = finding.get("evidence") or []
        valid = bool(evidence) and all(
            bool(item.get("quote"))
            and int(item.get("clause_id", -1)) in clause_map
            and str(item.get("quote")) in clause_map[int(item.get("clause_id"))]
            for item in evidence
        )
        item = {
            "check_id": finding.get("check_id"),
            "scope": finding.get("scope"),
            "clause_ids": finding.get("clause_ids") or [],
            "evidence_valid": valid,
            "evidence": evidence,
        }
        (cross_doc_positive if valid else cross_doc_invalid).append(item)

    trace_lines = []
    trace_path = run_dir / "trace.jsonl"
    if trace_path.exists():
        for line in trace_path.read_text(encoding="utf-8").splitlines():
            try: trace_lines.append(json.loads(line))
            except json.JSONDecodeError: pass
    legal_searches = [
        event for event in trace_lines
        if event.get("stage") == "legal_search" and "matches" in event
    ]
    deterministic = assessment.get("deterministic_cross_checks") or saved_result.get("deterministic_cross_checks") or []
    validation = {
        "http_200": int(record.get("http_status") or 0) == 200,
        "run_completed": manifest.get("status") == "COMPLETED",
        "source_hash_matches_manifest": bool((manifest.get("source") or {}).get("sha256")) and (manifest.get("source") or {}).get("sha256") == record.get("source_sha256"),
        "all_clause_positive_findings_have_valid_evidence": not invalid,
        "all_cross_document_positive_findings_have_valid_evidence": not cross_doc_invalid,
        "run_has_core_artifacts": all((run_dir / n).is_file() for n in (
            "manifest.json", "segments.json", "validated.json", "classification.jsonl",
            "risk_findings.jsonl", "contract_checks.json", "contract_risk.json",
            "result.json", "trace.jsonl", "risk_findings.csv", "clauses.csv"
        )),
    }
    summary = {
        "pipeline_status": response.get("pipeline_status"),
        "clause_count": len(clauses),
        "classified_labels": [
            {"clause_index": c.get("clause_index"), "label": c.get("predicted_label"), "classification_status": c.get("classification_status")}
            for c in clauses
        ],
        "clause_risk_finding_count": sum(len(c.get("risk_findings") or []) for c in clauses),
        "clause_positive_count": len(positives),
        "target_clause_evidence_valid_count": len(target_valid),
        "related_clause_evidence_valid_count": len(related_valid),
        "invalid_or_unmapped_positive_evidence_count": len(invalid),
        "cross_clause_statuses": status_counts(cross),
        "document_statuses": status_counts(docs),
        "cross_or_document_positive_evidence_valid_count": len(cross_doc_positive),
        "cross_or_document_positive_evidence_invalid_count": len(cross_doc_invalid),
        "overall_status": assessment.get("status") or assessment.get("overall_status"),
        "overall_risk": assessment.get("overall_risk"),
        "deterministic_candidate_signal_ids": [item.get("id") for item in deterministic],
        "legal_guidance_search_calls": len(legal_searches),
        "legal_guidance_matches_total": sum(int(event.get("matches") or 0) for event in legal_searches),
    }
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "interpretation": "Synthetic plumbing smoke test only. The input is invented. Results do not estimate model accuracy, legal correctness or sensitivity on real contracts.",
        "http_status": record.get("http_status"),
        "elapsed_seconds": record.get("elapsed_seconds"),
        "analysis_id": analysis_id,
        "run_dir": str(run_dir.relative_to(ROOT)),
        "source_file": record.get("source_file"),
        "source_sha256": record.get("source_sha256"),
        "manifest_source": manifest.get("source"),
        "pipeline_config": manifest.get("pipeline"),
        "summary": summary,
        "positive_clause_findings": positives,
        "valid_related_clause_evidence": related_valid,
        "positive_cross_document_findings": cross_doc_positive + cross_doc_invalid,
        "checks": validation,
        "failed_checks": [name for name, passed in validation.items() if not passed],
        "core_artifact_sha256": {
            name: sha256(run_dir / name)
            for name in ("manifest.json", "contract_checks.json", "contract_risk.json", "result.json", "risk_findings.csv", "clauses.csv", "trace.jsonl")
            if (run_dir / name).is_file()
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = ("_" + args.suffix.strip("_")) if args.suffix.strip("_") else ""
    json_path = OUT_DIR / f"smoke_test_audit{suffix}.json"
    md_path = OUT_DIR / f"smoke_test_audit{suffix}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = [
        "# End-to-End Upload Smoke Test Audit",
        "",
        "**Status:** " + ("PASS" if not report["failed_checks"] else "FAIL"),
        "**Interpretation:** Synthetic plumbing test only—not an accuracy benchmark.",
        "Analysis ID: " + str(analysis_id),
        "Input: " + str(record.get("source_file")),
        "Input SHA-256: " + str(record.get("source_sha256")),
        "Runtime seconds: " + str(record.get("elapsed_seconds")),
        "Git commit in manifest: " + str((manifest.get("environment") or {}).get("git_commit")),
        "Code fingerprint: " + str((manifest.get("pipeline") or {}).get("code_fingerprint")),
        "Playbook hash: " + str((manifest.get("pipeline") or {}).get("playbook_hash")),
        "",
        "## End-to-end outcome",
        "",
        "| Metric | Observed |",
        "|---|---:|",
        "| HTTP status | " + str(record.get("http_status")) + " |",
        "| Pipeline status | " + str(response.get("pipeline_status")) + " |",
        "| Clauses returned | " + str(len(clauses)) + " |",
        "| Clause-level findings | " + str(summary["clause_risk_finding_count"]) + " |",
        "| Positive clause findings | " + str(summary["clause_positive_count"]) + " |",
        "| Positive quotes in target clause | " + str(summary["target_clause_evidence_valid_count"]) + " |",
        "| Positive quotes from related clause | " + str(summary["related_clause_evidence_valid_count"]) + " |",
        "| Invalid/unmapped positive quotes | " + str(summary["invalid_or_unmapped_positive_evidence_count"]) + " |",
        "| Cross-clause status counts | " + json.dumps(summary["cross_clause_statuses"]) + " |",
        "| Document status counts | " + json.dumps(summary["document_statuses"]) + " |",
        "| Valid positive cross/document results | " + str(summary["cross_or_document_positive_evidence_valid_count"]) + " |",
        "| Overall triage | " + str(summary["overall_status"]) + " / " + str(summary["overall_risk"]) + " |",
        "| Legal guidance matches | " + str(summary["legal_guidance_matches_total"]) + " across " + str(summary["legal_guidance_search_calls"]) + " searches |",
        "",
        "## Clause classifications",
    ]
    md.extend("- Clause " + str(x["clause_index"]) + ": " + str(x["label"]) + " (" + str(x["classification_status"]) + ")" for x in summary["classified_labels"])
    md.extend(["", "## Deterministic interaction candidates"])
    md.extend("- " + str(signal) for signal in summary["deterministic_candidate_signal_ids"])
    if not summary["deterministic_candidate_signal_ids"]:
        md.append("- None recorded in this run.")
    md.extend(["", "## Validation"])
    md.extend("- [" + ("x" if passed else " ") + "] " + name for name, passed in validation.items())
    md.extend([
        "",
        "## Limitations observed",
        "",
        "- The contract fixture is invented and intentionally contains test stimuli. This is not measured legal-risk accuracy.",
        "- Model-silver and synthetic fixtures do not replace human adjudication.",
        "- New runs identify whether exact evidence came from the target clause or a related clause; the source clause ID is preserved.",
        "- If legal-guidance matches are zero, check that the local Qdrant collection has been populated with the legal knowledge ingestion command before launching the API. This report captures the actual result for this run and does not retroactively change it.",
        "- Full response, manifest, trace and per-finding exports are under " + str(run_dir.relative_to(ROOT)) + ".",
    ])
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS" if not report["failed_checks"] else "FAIL",
        "analysis_id": analysis_id,
        "elapsed_seconds": record.get("elapsed_seconds"),
        "json": str(json_path.relative_to(ROOT)),
        "markdown": str(md_path.relative_to(ROOT)),
        "checks": validation,
    }, indent=2))
    return 0 if not report["failed_checks"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
