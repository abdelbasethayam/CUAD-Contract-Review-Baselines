"""Advanced preprocessing for legal clause classification.

Pipeline:
1. Unicode / whitespace / quote normalization
2. Legal abbreviation expansion
3. Light boilerplate stripping (page headers, exhibit stamps)
4. Optional lowercasing for retrieval only (not for LLM prompt fidelity)
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .text_preprocessor import (
    expand_legal_abbreviations,
    normalize_quotes,
    normalize_whitespace,
    preprocess_clause,
)

_PAGE_NOISE = re.compile(
    r"(?im)^\s*(page\s+\d+(\s+of\s+\d+)?|exhibit\s+[a-z0-9\-\.]+)\s*$",
)
_MULTI_NL = re.compile(r"\n{3,}")
_BRACKET_OCR = re.compile(r"\[{2,}|\]{2,}|\{{2,}|\}{2,}")


@dataclass
class PreprocessResult:
    text: str
    for_embedding: str
    notes: list[str]


def strip_page_boilerplate(text: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    lines = text.splitlines()
    kept: list[str] = []
    removed = 0
    for line in lines:
        if _PAGE_NOISE.match(line.strip()):
            removed += 1
            continue
        kept.append(line)
    if removed:
        notes.append(f"removed_{removed}_boilerplate_lines")
    out = "\n".join(kept)
    out = _MULTI_NL.sub("\n\n", out)
    return out, notes


def advanced_preprocess(raw: str, *, for_llm: bool = True) -> PreprocessResult:
    notes: list[str] = []
    text = str(raw or "")
    text = normalize_quotes(text)
    text = _BRACKET_OCR.sub("", text)
    text, n = strip_page_boilerplate(text)
    notes.extend(n)
    text = preprocess_clause(text, expand_abbrevs=True, normalize=True)
    text = expand_legal_abbreviations(text)
    text = normalize_whitespace(text)

    embed = text.lower()  # retrieval often benefits from case-folding
    # LLM keeps casing for legal fidelity when for_llm=True
    return PreprocessResult(
        text=text if for_llm else embed,
        for_embedding=embed,
        notes=notes,
    )


__all__ = ["PreprocessResult", "advanced_preprocess", "strip_page_boilerplate"]
