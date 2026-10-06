"""Deterministic extraction of clause structure and dependency signals."""
from __future__ import annotations

import re
from typing import Any

_SECTION_PATTERNS = [
    r"\bsection\s+([A-Za-z0-9.()\-]+)",
    r"\barticle\s+([A-Za-z0-9.()\-]+)",
    r"\bclause\s+([A-Za-z0-9.()\-]+)",
    r"§\s*([A-Za-z0-9.()\-]+)",
]
_DOCUMENT_PATTERNS = [
    r"\b(?:schedule|exhibit|appendix|attachment|order\s+form)\s+[A-Za-z0-9.()\-]+",
]
_DEPENDENCY_PATTERNS = [
    r"as\s+(?:defined|set forth|provided)\s+in\s+([^.;\n]+)",
    r"incorporat(?:e|ed|es|ing)\s+([^.;\n]+)",
    r"subject\s+to\s+([^.;\n]+)",
]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(v.strip() for v in values if v and v.strip()))


def _sentences(text: str) -> list[str]:
    return [
        s.strip()
        for s in re.split(r"(?<=[.!?;])\s+|\n+", str(text or ""))
        if s.strip()
    ]


def _referenced_identifiers(clause_text: str) -> list[str]:
    ids = []
    for pattern in _SECTION_PATTERNS:
        for match in re.finditer(pattern, str(clause_text or ""), re.IGNORECASE):
            prefix = re.match(r"[A-Za-z§]+", match.group(0).strip())
            label = (prefix.group(0) if prefix else "").strip()
            ids.append(f"{label} {match.group(1)}".strip())
    for pattern in _DOCUMENT_PATTERNS:
        ids.extend(match.group(0).strip() for match in re.finditer(pattern, str(clause_text or ""), re.IGNORECASE))
    return _unique(ids)


def extract_clause_structure(
    clause_text: str,
    *,
    section_path: str | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    full_contract_text: str | None = None,
) -> dict[str, Any]:
    text = str(clause_text or "")
    lower = text.lower()
    full_text = str(full_contract_text or text)
    full_lower = full_text.lower()

    linked_sections = _referenced_identifiers(text)
    dependency_sentences = [
        match.group(0).strip()
        for pattern in _DEPENDENCY_PATTERNS
        for match in re.finditer(pattern, text, re.IGNORECASE)
    ]

    unresolved_dependencies = []
    for reference in linked_sections:
        normalized = reference.lower().strip()
        if normalized and normalized not in full_lower:
            unresolved_dependencies.append(reference)

    defined_terms = []
    for match in re.finditer(r'["“”]([^"“”]{2,80})["“”]', text):
        value = match.group(1).strip()
        if value and len(value.split()) <= 8:
            defined_terms.append(value)
    for match in re.finditer(
        r"\b([A-Z][A-Za-z0-9&/\-]{1,30})\s+(?:means|shall mean|refers to)\b",
        text,
    ):
        defined_terms.append(match.group(1).strip())
    defined_terms = _unique(defined_terms)

    obligation_sentences = [
        sentence
        for sentence in _sentences(text)
        if re.search(
            r"\b(?:shall|must|may|will|agrees? to|is required to)\b",
            sentence,
            re.IGNORECASE,
        )
    ]
    exception_sentences = [
        sentence
        for sentence in _sentences(text)
        if re.search(
            r"\b(?:except|excluding|unless|provided that|subject to|notwithstanding|carve[- ]?out)\b",
            sentence,
            re.IGNORECASE,
        )
    ]

    scope = {
        "territory": None,
        "customer_class": None,
        "technology": None,
        "affiliates": bool(re.search(r"\baffiliate(?:s)?\b", lower)),
        "personnel": bool(re.search(r"\b(?:employee|personnel|contractor|agent)s?\b", lower)),
        "time_period": None,
        "broad_scope_markers": _unique(
            [
                "worldwide" if "worldwide" in lower else "",
                "global" if re.search(r"\bglobal\b", lower) else "",
                "perpetual" if "perpetual" in lower else "",
                "irrevocable" if "irrevocable" in lower else "",
                "exclusive" if re.search(r"\bexclusive\b", lower) else "",
                "all customers" if "all customers" in lower else "",
            ]
        ),
    }

    duration = re.findall(
        r"\b\d+\s+(?:day|days|month|months|year|years)\b|\bperpetual\b|\bindefinite\b",
        text,
        re.IGNORECASE,
    )
    if duration:
        scope["time_period"] = _unique(duration)

    transaction_role = None
    if re.search(r"\b(?:supplier|vendor|provider)\b", lower):
        transaction_role = "supplier_or_provider"
    elif re.search(r"\b(?:customer|buyer|client)\b", lower):
        transaction_role = "customer_or_buyer"

    direction = (
        "OBLIGATION"
        if re.search(r"\b(?:shall|must|is required to)\b", lower)
        else "RIGHT_OR_DISCRETION"
        if re.search(r"\bmay\b", lower)
        else "MIXED_OR_UNKNOWN"
    )

    return {
        "section_path": section_path,
        "page_start": page_start,
        "page_end": page_end,
        "defined_terms_used": defined_terms,
        "linked_sections": linked_sections,
        "dependencies": dependency_sentences,
        "unresolved_dependencies": unresolved_dependencies,
        "dependency_missing": bool(unresolved_dependencies),
        "rights_and_duties": obligation_sentences[:12],
        "exceptions_carveouts": exception_sentences[:10],
        "scope": scope,
        "transaction_role": transaction_role,
        "direction_of_obligation": direction,
        "structure_status": "DETERMINISTIC_PARTIAL",
    }


__all__ = ["extract_clause_structure"]
