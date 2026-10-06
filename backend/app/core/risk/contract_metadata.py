"""Deterministic contract metadata extraction.

All inferred metadata is explicitly marked heuristic/candidate rather than
treated as authoritative legal fact.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

DATE_VALUE = (
    r"[A-Z][A-Za-z]{2,12}\s+\d{1,2},\s+\d{4}"
    r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|\d{4}[/-]\d{1,2}[/-]\d{1,2}"
)


def _first_match(patterns: list[str], text: str) -> tuple[str | None, str | None]:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            value = match.group(1).strip(" \t\r\n:;,.")
            return value or None, match.group(0).strip()
    return None, None


def _candidate_contract_types(text: str) -> list[str]:
    lower = str(text or "").lower()
    rules = [
        ("saas_software", ("saas", "software as a service", "cloud services", "subscription service")),
        ("technology_license", ("software license", "licence grant", "intellectual property", "source code")),
        ("supply_goods", ("goods", "purchase order", "delivery", "supplier", "buyer")),
        ("services", ("statement of work", "professional services", "services agreement", "service provider")),
        ("distribution", ("distributor", "reseller", "distribution territory")),
        ("technology_transfer", ("technology transfer", "know-how", "technology assignment")),
        ("commercial_general", ()),
    ]
    hits = []
    for label, terms in rules:
        if terms and any(term in lower for term in terms):
            hits.append(label)
    return hits or ["commercial_general"]


def _jurisdiction_candidates(governing_law: str | None) -> list[str]:
    if not governing_law:
        return []
    value = governing_law.strip()
    return [value]


def extract_contract_metadata(
    filename: str,
    clauses: list[dict],
    *,
    document_hash: str | None = None,
    document_version: str = "1",
) -> dict[str, Any]:
    text = "\n".join(str(item.get("clause_text") or "") for item in clauses)
    document_hash = document_hash or hashlib.sha256(text.encode("utf-8")).hexdigest()
    contract_types = _candidate_contract_types(text)

    metadata: dict[str, Any] = {
        "name": Path(filename).stem if filename else None,
        "document_hash": document_hash,
        "document_version": str(document_version),
        "source_filename": filename,
        "contract_type": contract_types[0] if len(contract_types) == 1 else "commercial_general",
        "contract_type_candidates": contract_types,
        "contract_type_status": "HEURISTIC_CANDIDATE",
        "jurisdiction_candidates": [],
        "parties": [],
        "agreement_date": None,
        "effective_date": None,
        "expiration_date": None,
        "governing_law": None,
        "evidence": {},
        "provenance": "DETERMINISTIC_EXTRACTOR",
        "metadata_status": "PARTIAL_HEURISTIC",
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

    metadata["jurisdiction_candidates"] = _jurisdiction_candidates(
        metadata["governing_law"]
    )
    return metadata
