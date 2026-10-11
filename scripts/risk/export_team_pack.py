#!/usr/bin/env python3
"""Export risk playbook, taxonomy and source registry for team review."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK = ROOT / "data" / "risk" / "commercial_clause_risk_playbook.json"
TAXONOMY = ROOT / "backend" / "data" / "legal_knowledge" / "risk_taxonomy.json"
REGISTRY = ROOT / "backend" / "data" / "legal_knowledge" / "source_registry.json"
OUT = ROOT / "data" / "risk" / "team_export"


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def json_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def write_csv(path: Path, columns: list[str], records: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({column: json_cell(record.get(column)) for column in columns})


def main() -> int:
    playbook = json.loads(PLAYBOOK.read_text(encoding="utf-8"))
    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)

    clause_rows: list[dict] = []
    for clause_type, payload in (playbook.get("clause_types") or {}).items():
        for check in payload.get("checklist") or []:
            clause_rows.append({"clause_type": clause_type, "check_id": check.get("id"), **check})

    cross_rows = list(playbook.get("cross_clause_checks") or [])
    doc_rows = list(playbook.get("document_level_checks") or [])

    clause_columns = [
        "clause_type", "check_id", "risk_domain", "risk_subdomain", "risk_type",
        "perspective", "question", "flag_if", "do_not_flag_if", "required_evidence",
        "evidence_location", "dependencies", "jurisdiction_scope", "sources",
        "version", "rationale",
    ]
    cross_columns = [
        "id", "pair", "risk_domain", "risk_subdomain", "risk_type", "question",
        "flag_if", "do_not_flag_if", "dependencies", "jurisdiction_scope", "sources",
    ]
    doc_columns = [
        "id", "risk_domain", "risk_subdomain", "risk_type", "question", "flag_if",
        "dependencies", "jurisdiction_scope", "sources",
    ]

    write_csv(OUT / "risk_clause_checks.csv", clause_columns, clause_rows)
    write_csv(OUT / "risk_cross_clause_checks.csv", cross_columns, cross_rows)
    write_csv(OUT / "risk_document_checks.csv", doc_columns, doc_rows)
    shutil.copyfile(PLAYBOOK, OUT / "risk_playbook_exact.json")
    shutil.copyfile(TAXONOMY, OUT / "risk_taxonomy.json")
    shutil.copyfile(REGISTRY, OUT / "source_registry.json")

    canonical_domains = {
        str(item.get("risk_domain"))
        for item in taxonomy.get("risk_domains") or []
        if item.get("risk_domain")
    }
    all_checks = clause_rows + cross_rows + doc_rows
    invalid = [
        (item.get("id") or item.get("check_id"), item.get("risk_domain"))
        for item in all_checks
        if item.get("risk_domain") not in canonical_domains
    ]
    if invalid:
        raise SystemExit(f"Export contains missing/non-canonical domains: {invalid[:20]}")

    files = [
        "risk_clause_checks.csv", "risk_cross_clause_checks.csv",
        "risk_document_checks.csv", "risk_playbook_exact.json",
        "risk_taxonomy.json", "source_registry.json",
    ]
    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "playbook_source_version": playbook.get("source_version", playbook.get("version")),
        "clause_check_count": len(clause_rows),
        "cross_clause_check_count": len(cross_rows),
        "document_check_count": len(doc_rows),
        "canonical_domain_count": len(canonical_domains),
        "domain_mapping_validation": "PASS",
        "sources": {
            "playbook_sha256": digest(PLAYBOOK),
            "taxonomy_sha256": digest(TAXONOMY),
            "source_registry_sha256": digest(REGISTRY),
        },
        "exports": {name: {"sha256": digest(OUT / name)} for name in files},
        "warning": (
            "Playbook and taxonomy are review guidance, not human gold labels "
            "or evidence of a fact in an uploaded contract."
        ),
    }
    (OUT / "export_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT / "README.md").write_text(
        f"""# Commercial Contract Risk Detection — Team Export

Source-of-truth playbook version: {manifest['playbook_source_version']}.

## Contents

- risk_clause_checks.csv — {len(clause_rows)} clause-level checks.
- risk_cross_clause_checks.csv — {len(cross_rows)} cross-clause checks.
- risk_document_checks.csv — {len(doc_rows)} document-level checks.
- risk_playbook_exact.json — byte-for-byte copy of the source playbook.
- risk_taxonomy.json — canonical broad risk domains and guidance.
- source_registry.json — legal-knowledge source metadata.
- export_manifest.json — source/export hashes and validation counts.

## Risk-domain policy

Every check maps to one of the {len(canonical_domains)} canonical domains in risk_taxonomy.json.
The declared playbook domain is the primary review-routing/aggregation domain. A
more specific legacy label is retained as risk_subdomain. Taxonomy keyword
matches are supplementary signals and must not override an explicit domain.

## Evidence and evaluation caveat

The playbook and taxonomy are **review guidance, not contract evidence and not
human gold labels**. A positive risk finding must be supported by exact evidence
from the uploaded contract. The project still requires expert annotation and
adjudication of its 300-task gold queue before reporting human-gold accuracy for
the custom risk predicates.
""",
        encoding="utf-8",
    )

    print(json.dumps({
        "status": "PASS",
        "playbook_source_version": manifest["playbook_source_version"],
        "clause_checks": len(clause_rows),
        "cross_clause_checks": len(cross_rows),
        "document_checks": len(doc_rows),
        "canonical_domains": len(canonical_domains),
        "missing_or_noncanonical_domains": len(invalid),
        "export_directory": str(OUT),
        "manifest": str(OUT / "export_manifest.json"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
