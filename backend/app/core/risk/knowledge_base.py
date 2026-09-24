"""Structured, contract-independent risk taxonomy and guidance loader."""

from __future__ import annotations

import json
from pathlib import Path

from ..config import PROJECT_ROOT

RISK_KNOWLEDGE_PATH = PROJECT_ROOT / "backend" / "data" / "legal_knowledge" / "risk_taxonomy.json"


def load_risk_knowledge(path: Path = RISK_KNOWLEDGE_PATH) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "risk_domains": []}


def match_risk_domains(clause_text: str, clause_type: str = "", indicators: list[str] | None = None) -> list[dict]:
    """Return taxonomy matches as guidance metadata, never as evidence."""
    text = f"{clause_type} {clause_text} {' '.join(indicators or [])}".lower()
    matches = []
    for domain in load_risk_knowledge().get("risk_domains", []):
        terms = [str(term).lower() for term in domain.get("indicators", [])]
        hit_count = sum(1 for term in terms if term and term in text)
        if hit_count:
            matches.append({**domain, "match_count": hit_count})
    return sorted(matches, key=lambda item: item["match_count"], reverse=True)


def risk_guidance_for_prompt(domains: list[dict]) -> list[dict]:
    return [
        {
            "risk_domain": item.get("risk_domain"),
            "risk_types": item.get("risk_types", []),
            "description": item.get("description"),
            "severity_guidance": item.get("severity_guidance"),
            "mitigation_guidance": item.get("mitigation_guidance"),
            "related_cuad_categories": item.get("related_cuad_categories", []),
        }
        for item in domains
    ]
