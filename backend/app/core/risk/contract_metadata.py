"""Deterministic contract metadata extraction with evidence spans."""
from __future__ import annotations

import re
from pathlib import Path


DATE_VALUE = r"[A-Z][A-Za-z]{2,12}\s+\d{1,2},\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}"


def _first_match(patterns: list[str], text: str) -> tuple[str | None, str | None]:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            value = match.group(1).strip(" \t\r\n:;,.")
            return value or None, match.group(0).strip()
    return None, None


def extract_contract_metadata(filename: str, clauses: list[dict]) -> dict:
    text = "\n".join(str(item.get("clause_text") or "") for item in clauses)
    metadata = {
        "name": Path(filename).stem if filename else None,
        "source_filename": filename,
        "parties": [],
        "agreement_date": None,
        "effective_date": None,
        "expiration_date": None,
        "governing_law": None,
        "evidence": {},
        "provenance": "DETERMINISTIC_EXTRACTOR",
    }

    parties = re.search(
        r"(?:by and between|between)\s+(.{2,160}?)\s+and\s+(.{2,160}?)(?:\.|,|\n|\s+as of\b)",
        text,
        re.IGNORECASE,
    )
    if parties:
        metadata["parties"] = [
            parties.group(1).strip(" \t\r\n,;"),
            parties.group(2).strip(" \t\r\n,;"),
        ]
        metadata["evidence"]["parties"] = parties.group(0).strip()

    for field, patterns in {
        "agreement_date": [
            rf"(?:agreement date|dated as of|date of this agreement)\s*[:\-]?\s*({DATE_VALUE})",
        ],
        "effective_date": [
            rf"(?:effective date|effective as of|commencement date)\s*[:\-]?\s*({DATE_VALUE})",
        ],
        "expiration_date": [
            rf"(?:expiration date|expires? on|end date)\s*[:\-]?\s*({DATE_VALUE})",
        ],
        "governing_law": [
            r"governed by(?: and construed in accordance with)?\s+(?:the laws of\s+)?([^.;\n]{2,120})",
        ],
    }.items():
        value, evidence = _first_match(patterns, text)
        metadata[field] = value
        if evidence:
            metadata["evidence"][field] = evidence

    return metadata
