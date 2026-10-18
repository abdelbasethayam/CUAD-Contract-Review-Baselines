"""Deterministic contract metadata extraction with source evidence.

The extractor prefers explicitly labelled fields and avoids treating SEC filing
citations or dispute-forum language as agreement dates or governing law.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

DATE_VALUE = r"[A-Z][A-Za-z]{2,12}\s+\d{1,2},\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}"


def _text_of(item: dict[str, Any]) -> str:
    return str(item.get("clause_text") or item.get("text") or "")


def _first_match(patterns: list[str], text: str) -> tuple[str | None, str | None]:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            value = match.group(1).strip(" \t\r\n:;,.\")(")
            return value or None, match.group(0).strip()
    return None, None


def _party(text: str, side: str) -> tuple[str | None, str | None]:
    # Prefer the document's own Party A/B labels (including role labels), and
    # stop at the following Address field rather than swallowing addresses.
    pattern = rf"\bParty\s+{side}\s*(?:\([^)]*\))?\s*:\s*(.+?)(?=\s+Address\s*:|\s+Party\s+[AB]\b|[\r\n]|$)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        name = re.sub(r"\s+", " ", match.group(1)).strip(" \t\r\n,;:.\")(")
        # Avoid emitting labels, address fragments, or empty captures.
        if name and len(name) <= 180:
            return name, match.group(0).strip()
    return None, None


def extract_contract_metadata(filename: str, clauses: list[dict]) -> dict:
    text = "\n".join(_text_of(item) for item in clauses)
    metadata: dict[str, Any] = {
        "name": Path(filename).stem if filename else None,
        "source_filename": filename,
        "parties": [],
        "agreement_date": None,
        "effective_date": None,
        "effective_date_condition": None,
        "expiration_date": None,
        "expiration_terms": None,
        "governing_law": None,
        "dispute_forum": None,
        "evidence": {},
        "provenance": "DETERMINISTIC_EXTRACTOR",
    }

    a, ev_a = _party(text, "A")
    b, ev_b = _party(text, "B")
    if a and b:
        metadata["parties"] = [a, b]
        metadata["evidence"]["parties"] = [ev_a, ev_b]
    else:
        # Fallback for a conventional "by and between X and Y" opening.
        parties = re.search(
            r"(?:by and between|between)\s+(.{2,160}?)\s+and\s+(.{2,160}?)(?:\.|,|\n|\s+as of\b)",
            text,
            re.IGNORECASE,
        )
        if parties:
            metadata["parties"] = [parties.group(1).strip(" \t\r\n,;"), parties.group(2).strip(" \t\r\n,;")]
            metadata["evidence"]["parties"] = parties.group(0).strip()

    date_patterns = {
        "agreement_date": [
            rf"(?:agreement date|date of this agreement|dated as of|this agreement is dated|this agreement dated)\s*[:\-]?\s*({DATE_VALUE})",
            rf"this agreement (?:is )?(?:made|entered into) on\s+({DATE_VALUE})",
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
        "dispute_forum": [
            r"(?:subject to the jurisdiction of|exclusive jurisdiction of|submit(?:ted)? to the jurisdiction of)\s+(?:the\s+)?([^.;\n]{3,160})",
            r"disputes? (?:shall be )?(?:brought|heard|resolved) in\s+([^.;\n]{3,160})",
        ],
    }
    for field, patterns in date_patterns.items():
        value, evidence = _first_match(patterns, text)
        if value:
            metadata[field] = value
        if evidence:
            metadata["evidence"][field] = evidence

    effective_trigger = re.search(
        r"([^.;\n]{0,100}(?:takes effect|effective)\s+upon\s+[^.;\n]{3,180})",
        text,
        re.IGNORECASE,
    )
    if effective_trigger and not metadata["effective_date"]:
        metadata["effective_date_condition"] = re.sub(r"\s+", " ", effective_trigger.group(1)).strip()
        metadata["evidence"]["effective_date_condition"] = effective_trigger.group(0).strip()

    indefinite = re.search(
        r"([^.;\n]{0,120}(?:valid for an indefinite term|for an indefinite term|continues? indefinitely)[^.;\n]{0,100})",
        text,
        re.IGNORECASE,
    )
    if indefinite and not metadata["expiration_date"]:
        metadata["expiration_terms"] = re.sub(r"\s+", " ", indefinite.group(1)).strip()
        metadata["evidence"]["expiration_terms"] = indefinite.group(0).strip()

    return metadata

[executed on device: jupyter-group-digi2026-g6 (a8417900-e68e-4ee2-bbe7-fc3493ade5e1)]
