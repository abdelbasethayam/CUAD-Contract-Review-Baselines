"""Versioned commercial-contract risk playbook loader.

The playbook is policy/guidance, not ground-truth labels. Findings derived from
it are marked PLAYBOOK_DERIVED until manually adjudicated against a gold set.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..config import RISK_PLAYBOOK_PATH, RISK_PLAYBOOK_VERSION
from .evidence_policy import normalize_source_record


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def playbook_hash(playbook: dict) -> str:
    return hashlib.sha256(canonical_json(playbook).encode("utf-8")).hexdigest()


def normalize_playbook(raw: dict) -> dict:
    clause_types = {}
    for name, payload in (raw.get("clause_types") or {}).items():
        payload = payload or {}
        checklist = []
        for item in payload.get("checklist") or []:
            checklist.append(
                {
                    "id": str(item.get("id") or "").strip(),
                    "risk_domain": str(item.get("risk_domain") or "").strip() or None,
                    "risk_type": str(item.get("risk_type") or "").strip() or None,
                    "perspective": str(item.get("perspective") or raw.get("perspective") or "customer_buyer"),
                    "applies_when": item.get("applies_when") or [],
                    "question": str(item.get("question") or "").strip(),
                    "flag_if": str(item.get("flag_if") or "").strip(),
                    "do_not_flag_if": item.get("do_not_flag_if") or [],
                    "required_evidence": item.get("required_evidence") or [],
                    "evidence_location": str(item.get("evidence_location") or "clause").strip(),
                    "severity_factors": item.get("severity_factors") or [],
                    "dependencies": item.get("dependencies") or [],
                    "jurisdiction_scope": item.get("jurisdiction_scope") or ["unspecified"],
                    "rationale": str(item.get("rationale") or "").strip() or None,
                    "version": str(item.get("version") or raw.get("version") or RISK_PLAYBOOK_VERSION),
                    "sources": [str(x) for x in (item.get("sources") or [])],
                }
            )
        clause_types[str(name)] = {
            "keywords": [str(x).strip() for x in (payload.get("keywords") or []) if str(x).strip()],
            "checklist": [item for item in checklist if item["id"] and item["question"]],
        }

    raw_sources = raw.get("sources") or {}
    normalized_sources = {}
    for source_id, source in raw_sources.items():
        # Uploaded checklist references are conservatively treated as
        # professional-practice sources until stronger authority metadata is
        # supplied. This prevents accidental presentation as binding law.
        normalized_sources[str(source_id)] = normalize_source_record(
            str(source_id),
            source,
            default_tier="B",
        )

    normalized = {
        "schema_version": 3,
        "source_version": str(raw.get("version") or RISK_PLAYBOOK_VERSION),
        "title": str(raw.get("title") or "Commercial Contract Risk Playbook"),
        "perspective": str(raw.get("perspective") or "customer_buyer"),
        "policy_tier": "D",
        "owner": raw.get("owner"),
        "effective_date": raw.get("effective_date"),
        "approval_status": str(raw.get("approval_status") or "UNAPPROVED"),
        "disclaimer": str(raw.get("disclaimer") or ""),
        "sources": normalized_sources,
        "clause_types": clause_types,
        "cross_clause_checks": [
            {
                "id": str(item.get("id") or "").strip(),
                "pair": [str(x) for x in (item.get("pair") or [])],
                "risk_domain": str(item.get("risk_domain") or "").strip() or None,
                "risk_type": str(item.get("risk_type") or "").strip() or None,
                "question": str(item.get("question") or "").strip(),
                "flag_if": str(item.get("flag_if") or "").strip(),
                "do_not_flag_if": item.get("do_not_flag_if") or [],
                "dependencies": item.get("dependencies") or [],
                "jurisdiction_scope": item.get("jurisdiction_scope") or ["unspecified"],
                "sources": [str(x) for x in (item.get("sources") or [])],
            }
            for item in (raw.get("cross_clause_checks") or [])
            if str(item.get("id") or "").strip()
        ],
        "document_level_checks": [
            {
                "id": str(item.get("id") or "").strip(),
                "risk_domain": str(item.get("risk_domain") or "").strip() or None,
                "risk_type": str(item.get("risk_type") or "").strip() or None,
                "question": str(item.get("question") or "").strip(),
                "flag_if": str(item.get("flag_if") or "").strip(),
                "dependencies": item.get("dependencies") or [],
                "jurisdiction_scope": item.get("jurisdiction_scope") or ["unspecified"],
                "sources": [str(x) for x in (item.get("sources") or [])],
            }
            for item in (raw.get("document_level_checks") or [])
            if str(item.get("id") or "").strip()
        ],
        "output_template": raw.get("output_template") or {
            "clause_type": "string",
            "checklist_item_id": "string",
            "question": "string",
            "flagged": "boolean|unknown",
            "evidence_span": "string",
            "sources": "list",
            "note": "string",
        },
    }
    normalized["playbook_hash"] = playbook_hash(normalized)
    return normalized


def starter_playbook() -> dict:
    """Small fallback playbook so Phase 2 is runnable before import."""
    generic = {
        "Limitation of Liability": [
            ("LOL-1", "Is there an express monetary or fee-based liability cap?", "No"),
            ("LOL-2", "Is the cap mutual?", "One-sided"),
            ("LOL-3", "Are important liability carve-outs coordinated with the cap?", "No or unclear"),
        ],
        "Uncapped Liability": [
            ("UNC-1", "Is any liability described as unlimited or uncapped?", "Yes"),
            ("UNC-2", "Does uncapped liability extend to ordinary breach?", "Yes"),
            ("UNC-3", "Is the uncapped scope limited to high-risk heads?", "No or unclear"),
        ],
        "Indemnification": [
            ("IND-1", "Is the indemnity one-sided or unusually broad?", "Yes"),
            ("IND-2", "Are defense, notice, settlement, and claim-scope mechanics clear?", "No or unclear"),
        ],
        "IP Ownership Assignment": [
            ("IP-1", "Is ownership of relevant intellectual property clearly allocated?", "No or unclear"),
            ("IP-2", "Does the assignment clearly identify the subject matter and scope?", "No or unclear"),
        ],
        "License Grant": [
            ("LIC-1", "Is the license scope bounded by purpose, territory, duration, and field of use?", "No or unclear"),
            ("LIC-2", "Is the license broad, perpetual, irrevocable, exclusive, transferable, or sublicensable?", "Yes"),
        ],
        "Termination": [
            ("TER-1", "Can a party terminate without notice or cure where a process would normally be expected?", "Yes"),
            ("TER-2", "Are survival, transition, accrued payment, and data-return effects addressed?", "No or unclear"),
        ],
        "Renewal Term": [
            ("REN-1", "Is automatic renewal paired with a clear non-renewal notice window?", "No or unclear"),
        ],
        "Anti-Assignment": [
            ("ASS-1", "Are assignment or change-of-control consent rights materially restrictive or ambiguous?", "Yes"),
        ],
        "Change Of Control": [
            ("COC-1", "Does a change of control trigger consent, termination, or other material consequences?", "Yes"),
        ],
        "Liquidated Damages": [
            ("LD-1", "Are liquidated damages materially exposed, unclear, or outside the liability cap?", "Yes or unclear"),
        ],
        "Insurance": [
            ("INS-1", "Are coverage types, limits, duration, or proof requirements unclear?", "Yes or unclear"),
        ],
        "Governing Law": [
            ("LAW-1", "Are governing law, venue, or dispute mechanics unclear or internally inconsistent?", "Yes or unclear"),
        ],
        "Audit Rights": [
            ("AUD-1", "Are audit scope, frequency, records, notice, cost, or remediation controls unclear?", "Yes or unclear"),
        ],
        "Exclusivity": [
            ("EXC-1", "Does exclusivity materially constrain the reviewing party without clear scope or exit mechanics?", "Yes or unclear"),
        ],
        "Minimum Commitment": [
            ("MIN-1", "Is there a fixed minimum commitment without adequate flexibility, credit, or exit mechanics?", "Yes or unclear"),
        ],
    }
    clause_types = {}
    for category, items in generic.items():
        clause_types[category] = {
            "keywords": [category.lower()],
            "checklist": [
                {"id": i, "question": q, "flag_if": f, "sources": []}
                for i, q, f in items
            ],
        }
    return normalize_playbook(
        {
            "version": RISK_PLAYBOOK_VERSION,
            "title": "Commercial Contract Risk Playbook (starter)",
            "perspective": "customer_buyer",
            "disclaimer": "Starter fallback. Import the project playbook before final evaluation.",
            "sources": {},
            "clause_types": clause_types,
            "cross_clause_checks": [
                {"id": "X-1", "pair": ["Limitation of Liability", "Uncapped Liability"], "question": "Are capped and uncapped heads consistent?", "flag_if": "No or unclear"},
                {"id": "X-2", "pair": ["Limitation of Liability", "Indemnification"], "question": "Are indemnity obligations coordinated with the liability cap?", "flag_if": "No or unclear"},
                {"id": "X-3", "pair": ["Renewal Term", "Termination"], "question": "Are renewal and termination windows consistent?", "flag_if": "No or unclear"},
            ],
            "document_level_checks": [
                {"id": "DOC-1", "question": "Are incorporated schedules, URLs, or order forms missing from the review package?", "flag_if": "Yes"},
                {"id": "DOC-2", "question": "Do definitions or precedence clauses materially change substantive protections?", "flag_if": "Yes"},
            ],
        }
    )


def load_playbook(path: Path | None = None) -> dict:
    path = Path(path or RISK_PLAYBOOK_PATH)
    if path.exists():
        try:
            return normalize_playbook(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            raise RuntimeError(
                f"Configured risk playbook is present but invalid: {path}: {exc}"
            ) from exc
    return starter_playbook()


def applicable_checks(playbook: dict, clause_type: str) -> list[dict]:
    entry = playbook.get("clause_types", {}).get(clause_type)
    if entry:
        return list(entry.get("checklist") or [])
    lower = str(clause_type or "").lower()
    for name, payload in playbook.get("clause_types", {}).items():
        if name.lower() in lower or lower in name.lower():
            return list(payload.get("checklist") or [])
    return []


def source_records(playbook: dict, ids: list[str]) -> list[dict]:
    return [
        dict(playbook.get("sources", {}).get(source_id) or {"id": source_id})
        for source_id in ids
    ]
