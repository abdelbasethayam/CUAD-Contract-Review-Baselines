"""Evidence-source tiers and claim-eligibility policy for Phase 2.

The source tier describes the evidentiary role of a source; it does not imply
that a source is binding law. Binding status is tracked separately.
"""

from __future__ import annotations

from datetime import date
from typing import Any

SOURCE_TIERS = {
    "A": "PRIMARY_OFFICIAL",
    "B": "PROFESSIONAL_PRACTICE",
    "C": "RESEARCH_METHODOLOGY",
    "D": "INTERNAL_POLICY",
}

CLAIM_TIER_POLICY = {
    "legal_conclusion": {"A"},
    "drafting_recommendation": {"A", "B"},
    "methodology": {"C"},
    "internal_policy": {"D"},
    "review_question": {"A", "B", "C", "D"},
}


def _clean(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def normalize_source_record(
    source_id: str,
    record: dict[str, Any] | None,
    *,
    default_tier: str = "B",
    retrieval_date: str | None = None,
) -> dict[str, Any]:
    raw = dict(record or {})
    tier = str(raw.get("source_tier") or default_tier).strip().upper()
    if tier not in SOURCE_TIERS:
        raise ValueError(f"Invalid source_tier {tier!r} for {source_id}; expected A/B/C/D")

    effective = _clean(raw.get("effective_date"))
    if effective:
        try:
            date.fromisoformat(effective)
        except ValueError:
            pass

    return {
        "id": str(raw.get("id") or source_id),
        "source_tier": tier,
        "source_tier_name": SOURCE_TIERS[tier],
        "authority_status": _clean(raw.get("authority_status")) or "NON_BINDING_GUIDANCE",
        "jurisdiction": _clean(raw.get("jurisdiction")) or "unspecified",
        "effective_date": effective,
        "contract_type": _clean(raw.get("contract_type")) or "commercial_general",
        "source_url": _clean(raw.get("source_url") or raw.get("url")),
        "source_title": _clean(raw.get("source_title") or raw.get("title") or raw.get("citation")),
        "source_name": _clean(raw.get("source_name") or raw.get("name")),
        "retrieval_date": _clean(raw.get("retrieval_date")) or retrieval_date,
        "supporting_quote_or_paraphrase": _clean(
            raw.get("supporting_quote_or_paraphrase") or raw.get("citation") or raw.get("note")
        ),
        "access_type": _clean(raw.get("access_type")) or "reference_only",
        "license_status": _clean(raw.get("license_status")) or "UNVERIFIED",
        "transferability": _clean(raw.get("transferability")) or "same_contract_type_preferred",
    }


def source_is_eligible(
    source: dict[str, Any],
    *,
    claim_kind: str = "review_question",
    jurisdiction: str | None = None,
    contract_type: str | None = None,
) -> bool:
    tier = str(source.get("source_tier") or "").upper()
    if tier not in CLAIM_TIER_POLICY.get(claim_kind, set()):
        return False

    if claim_kind == "legal_conclusion":
        binding = str(source.get("authority_status") or "").upper()
        if binding not in {"BINDING", "STATUTE", "REGULATION", "COURT", "TREATY"}:
            return False

    requested_jurisdiction = _clean(jurisdiction)
    available_jurisdiction = _clean(source.get("jurisdiction"))
    if requested_jurisdiction and available_jurisdiction not in {None, "unspecified", "international", requested_jurisdiction}:
        return False

    requested_contract = _clean(contract_type)
    available_contract = _clean(source.get("contract_type"))
    if requested_contract and available_contract not in {None, "commercial_general", requested_contract}:
        return False

    return True


def apply_transferability(
    source: dict[str, Any],
    *,
    contract_type: str | None = None,
) -> dict[str, Any]:
    result = dict(source)
    target = _clean(contract_type)
    source_type = _clean(source.get("contract_type"))
    if not target or not source_type or source_type in {"commercial_general", target}:
        result["transferability"] = result.get("transferability") or "direct"
    else:
        result["transferability"] = "limited_by_analogy"
    return result


__all__ = [
    "SOURCE_TIERS",
    "normalize_source_record",
    "source_is_eligible",
    "apply_transferability",
]
