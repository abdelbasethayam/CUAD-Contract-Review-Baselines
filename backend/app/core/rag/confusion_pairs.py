"""Resolve frequent CUAD near-confusions with lightweight lexical disambiguation.

When the model or retrieval oscillates between known hard pairs, apply
deterministic tie-breakers grounded in clause language.
"""
from __future__ import annotations

import re
from typing import Iterable

# (label_a, label_b, prefer_a_if, prefer_b_if)
# Patterns are checked only when both labels appear in the candidate set or
# when the predicted label is one of the pair.
_PAIR_RULES: list[tuple[str, str, re.Pattern[str], re.Pattern[str]]] = [
    (
        "Cap On Liability",
        "Uncapped Liability",
        re.compile(r"\b(shall not exceed|maximum|aggregate|cap(ped)?)\b", re.I),
        re.compile(r"\b(unlimited|uncapped|without (any )?limitation)\b", re.I),
    ),
    (
        "Termination For Convenience",
        "Notice Period To Terminate Renewal",
        re.compile(r"\b(for any reason|without cause|for convenience)\b", re.I),
        re.compile(r"\b(not to renew|non-?renewal|notice to terminate renewal)\b", re.I),
    ),
    (
        "Non-Compete",
        "Exclusivity",
        re.compile(r"\b(compet(e|ing|ition)|non-?compete)\b", re.I),
        re.compile(r"\b(exclusive|exclusivity|sole (distributor|licensee|supplier))\b", re.I),
    ),
    (
        "No-Solicit Of Employees",
        "No-Solicit Of Customers",
        re.compile(r"\b(employee|personnel|staff|hire|hiring)\b", re.I),
        re.compile(r"\b(customer|client|account)s?\b", re.I),
    ),
    (
        "License Grant",
        "Ip Ownership Assignment",
        re.compile(r"\b(license|licence|right to use|grants? a license)\b", re.I),
        re.compile(r"\b(assign(s|ment)? (all )?right|hereby assigns|ownership shall vest)\b", re.I),
    ),
    (
        "Renewal Term",
        "Notice Period To Terminate Renewal",
        re.compile(r"\b(automatic(ally)? renew|renewal term|shall renew)\b", re.I),
        re.compile(r"\b(notice.{0,40}(not to renew|non-?renew)|prior written notice.{0,30}renew)\b", re.I),
    ),
    (
        "Affiliate License-Licensee",
        "Affiliate License-Licensor",
        re.compile(r"\b(licensee.?s affiliates|affiliates of (the )?licensee)\b", re.I),
        re.compile(r"\b(licensor.?s affiliates|affiliates of (the )?licensor)\b", re.I),
    ),
]


def resolve_confusion(
    clause_text: str,
    predicted: str | None,
    candidates: Iterable[str] | None = None,
) -> tuple[str | None, str | None]:
    """Return (resolved_label, reason) or (predicted, None) if no change.

    Only adjusts when the predicted label is in a known confusion pair and the
    opposing pattern is clearly stronger, or when both pair members are candidates
    and only one side matches.
    """
    if not predicted or not clause_text:
        return predicted, None

    cand = {c.lower() for c in (candidates or [])}
    pred_l = predicted.lower()

    for a, b, pat_a, pat_b in _PAIR_RULES:
        pair = {a.lower(), b.lower()}
        if pred_l not in pair and not (cand and pair <= cand):
            continue

        hit_a = bool(pat_a.search(clause_text))
        hit_b = bool(pat_b.search(clause_text))

        if hit_a and not hit_b:
            return a, f"confusion_pair:{a}_vs_{b}->a"
        if hit_b and not hit_a:
            return b, f"confusion_pair:{a}_vs_{b}->b"
        # both or neither: keep prediction
    return predicted, None
