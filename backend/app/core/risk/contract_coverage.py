"""Deterministic clause-family coverage scan."""

from __future__ import annotations

from typing import Any


def _snippet(text: str, needle: str, radius: int = 180) -> str:
    pos = text.lower().find(needle.lower())
    if pos < 0:
        return ""
    return text[max(0, pos - radius): min(len(text), pos + len(needle) + radius)].strip()


def build_contract_coverage(clauses: list[dict[str, Any]], playbook: dict[str, Any]) -> list[dict[str, Any]]:
    full_text = "\n".join(str(item.get("clause_text") or "") for item in clauses)
    rows = []
    for clause_type, entry in sorted((playbook.get("clause_types") or {}).items()):
        keywords = [str(x).strip() for x in (entry.get("keywords") or []) if str(x).strip()]
        classifier_hits = [
            int(item.get("clause_index")) for item in clauses
            if str(item.get("predicted_label") or "").strip().lower() == str(clause_type).strip().lower()
        ]
        keyword_hits = [{"keyword": keyword, "evidence": _snippet(full_text, keyword)} for keyword in keywords if keyword.lower() in full_text.lower()]
        status = "PRESENT_CANDIDATE" if classifier_hits else ("PRESENT_BY_SEARCH" if keyword_hits else "NOT_FOUND_BY_SEARCH")
        rows.append({
            "clause_type": clause_type,
            "status": status,
            "classifier_clause_indices": classifier_hits,
            "keyword_hits": keyword_hits,
            "check_ids": [str(x.get("id")) for x in (entry.get("checklist") or [])],
            "review_required": status == "NOT_FOUND_BY_SEARCH",
        })
    return rows


__all__ = ["build_contract_coverage"]