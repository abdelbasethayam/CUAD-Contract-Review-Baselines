#!/usr/bin/env python3
"""Import the team's commercial risk playbook into the reproducible repo format.

Accepts the team's JSON export directly. If a .rar/.zip is supplied, the script
looks for commercial_clause_risk_checklists*.json inside it.
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
import hashlib

try:
    import rarfile
except ImportError:
    rarfile = None


def load_input(path: Path) -> dict:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))

    suffix = path.suffix.lower()
    if suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            candidates = [
                name for name in archive.namelist()
                if name.lower().endswith(".json")
                and "commercial_clause_risk_checklists" in name.lower()
            ]
            if not candidates:
                raise FileNotFoundError("No commercial risk checklist JSON found in archive.")
            return json.loads(archive.read(sorted(candidates)[0]).decode("utf-8"))

    if suffix == ".rar":
        if rarfile is None:
            raise SystemExit("Install rarfile and a system RAR extractor before importing .rar files.")
        with rarfile.RarFile(path) as archive:
            candidates = [
                name for name in archive.namelist()
                if name.lower().endswith(".json")
                and "commercial_clause_risk_checklists" in name.lower()
            ]
            if not candidates:
                raise FileNotFoundError("No commercial risk checklist JSON found in RAR.")
            return json.loads(archive.read(sorted(candidates)[0]).decode("utf-8"))

    raise ValueError(f"Unsupported source format: {path.suffix}")


def normalize(raw: dict) -> dict:
    clause_types = {}
    n_items = 0
    for name, payload in (raw.get("clause_types") or {}).items():
        checklist = []
        for item in payload.get("checklist") or []:
            record = {
                "id": str(item.get("id") or "").strip(),
                "question": str(item.get("question") or "").strip(),
                "flag_if": str(item.get("flag_if") or "").strip(),
                "sources": [str(x) for x in (item.get("sources") or [])],
            }
            if record["id"] and record["question"]:
                checklist.append(record)
        n_items += len(checklist)
        clause_types[str(name)] = {
            "keywords": [str(x).strip() for x in (payload.get("keywords") or [])],
            "checklist": checklist,
        }

    result = {
        "schema_version": 2,
        "source_version": str(raw.get("version") or "unknown"),
        "owner": str(raw.get("owner") or "research-team"),
        "effective_date": str(raw.get("effective_date") or "") or None,
        "approval_status": str(raw.get("approval_status") or "DRAFT").upper(),
        "approved_by": str(raw.get("approved_by") or "") or None,
        "title": str(raw.get("title") or "Commercial Contract Risk Playbook"),
        "perspective": str(raw.get("perspective") or "customer_buyer"),
        "disclaimer": str(raw.get("disclaimer") or ""),
        "sources": raw.get("sources") or {},
        "clause_types": clause_types,
        "cross_clause_checks": raw.get("cross_clause_checks") or [],
        "document_level_checks": raw.get("document_level_checks") or [],
        "output_template": raw.get("output_template") or {},
        "import_stats": {
            "clause_type_count": len(clause_types),
            "clause_check_count": n_items,
            "cross_clause_check_count": len(raw.get("cross_clause_checks") or []),
            "document_check_count": len(raw.get("document_level_checks") or []),
        },
    }
    canonical = json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    result["playbook_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/risk/commercial_clause_risk_playbook.json"),
    )
    args = parser.parse_args()

    playbook = normalize(load_input(args.source))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(playbook, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "output": str(args.out),
        "playbook_hash": playbook["playbook_hash"],
        **playbook["import_stats"],
    }, indent=2))


if __name__ == "__main__":
    main()
