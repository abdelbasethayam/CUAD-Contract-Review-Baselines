"""High-precision lexical rules for high-signal CUAD clause types."""
from __future__ import annotations

import re

# (label, pattern) — first match wins; keep patterns tight to avoid false positives.
HIGH_PRECISION_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("Governing Law", re.compile(
        r"\b(governed by|governing law|laws? of (the )?(state of )?[A-Z][a-z]+|"
        r"without regard to (its )?conflicts? of laws?)\b", re.I)),
    ("Insurance", re.compile(
        r"\b(maintain|procure|carry|purchase).{0,40}\binsurance\b"
        r"|\b(certificate of insurance|liability coverage|policy limits?|insured|insurer)\b", re.I)),
    ("Termination For Convenience", re.compile(
        r"\bterminat\w*\b.{0,80}\b(for any reason|without cause|for convenience|"
        r"at (its|their) (sole )?discretion)\b"
        r"|\b(for any reason|without cause|for convenience)\b.{0,80}\bterminat\w*\b", re.I)),
    ("Non-Compete", re.compile(
        r"\b(non-?compete|not (to )?compete|refrain from compet|"
        r"competing (business|product|service|activity|computer program)|"
        r"(shall|will|may) not (directly or indirectly )?(market|sell|offer|provide|develop|operate).{0,50}\bcompeting\b)\b", re.I)),
    ("No-Solicit Of Employees", re.compile(
        r"\b(non-?solicit\w*|shall not solicit|not solicit).{0,40}\b(employee|personnel|staff)\b"
        r"|\b(employee|personnel).{0,40}\b(non-?solicit|shall not solicit)\b", re.I)),
    ("No-Solicit Of Customers", re.compile(
        r"\b(non-?solicit\w*|shall not solicit|not solicit).{0,40}\b(customer|client|account)s?\b", re.I)),
    ("Anti-Assignment", re.compile(
        r"\b(shall not assign|may not assign|anti-?assignment|"
        r"without (the )?prior written consent.{0,30}assign)\b", re.I)),
    ("Audit Rights", re.compile(
        r"\b(audit rights?|right to audit|inspect (the )?(books|records)|"
        r"examination of (books|records))\b", re.I)),
    ("Cap On Liability", re.compile(
        r"\b(aggregate liability|liability.{0,40}shall not exceed|maximum liability|"
        r"cap(ped)? (on )?liability|limitation of liability.{0,40}exceed)\b", re.I)),
    ("Uncapped Liability", re.compile(
        r"\b(unlimited liability|uncapped|without (any )?limitation of liability)\b", re.I)),
    ("Liquidated Damages", re.compile(r"\bliquidated damages\b", re.I)),
    ("Source Code Escrow", re.compile(
        r"\b(source code escrow|escrow agent|deposit.{0,30}source code)\b", re.I)),
    ("Most Favored Nation", re.compile(
        r"\b(most favored nation|most favoured nation|MFN|no less favorable)\b", re.I)),
    ("Exclusivity", re.compile(
        r"\b(exclusive (right|license|distributor|dealer|supplier)|"
        r"sole (and exclusive )?right|exclusivity)\b", re.I)),
    ("Change Of Control", re.compile(
        r"\b(change of control|change in control|change-of-control)\b", re.I)),
    ("Renewal Term", re.compile(
        r"\b(automatic(ally)? renew|renewal term|shall renew for|successive (periods?|terms?))\b", re.I)),
    ("Notice Period To Terminate Renewal", re.compile(
        r"\b(notice.{0,40}(not to renew|non-?renewal|terminate renewal)|"
        r"(not to renew|non-?renew).{0,40}notice)\b", re.I)),
    ("License Grant", re.compile(
        r"\b(hereby grants?|grants? to).{0,40}\b(license|licence|right to use)\b", re.I)),
    ("Warranty Duration", re.compile(
        r"\b(warranty period|warrant(y|ies).{0,30}(for a period|days|months|years)|"
        r"shall be warranted)\b", re.I)),
    ("Minimum Commitment", re.compile(
        r"\b(minimum (purchase|commitment|volume|order|spend)|take-or-pay)\b", re.I)),
]


def high_precision_rule_label(clause_text: str, allowed: list[str] | None = None) -> str | None:
    """Return first high-precision label match, optionally restricted to allowed."""
    allowed_set = {a.lower() for a in (allowed or [])} if allowed else None
    text = clause_text or ""
    for label, pattern in HIGH_PRECISION_RULES:
        if allowed_set is not None and label.lower() not in allowed_set:
            continue
        if pattern.search(text):
            return label
    return None


def all_matching_rule_labels(clause_text: str) -> list[str]:
    """All matching rule labels (for debugging / multi-label signals)."""
    text = clause_text or ""
    return [label for label, pattern in HIGH_PRECISION_RULES if pattern.search(text)]
