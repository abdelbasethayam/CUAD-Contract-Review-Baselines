"""Versioned commercial-contract risk playbook loader.

The playbook is policy/guidance, not ground-truth labels. Findings derived from
it are marked PLAYBOOK_DERIVED until manually adjudicated against a gold set.
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..config import RISK_PLAYBOOK_PATH, RISK_PLAYBOOK_VERSION
from .evidence_policy import normalize_source_record


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def playbook_hash(playbook: dict) -> str:
    return hashlib.sha256(canonical_json(playbook).encode("utf-8")).hexdigest()


def _normalize_deterministic_rules(raw: dict) -> list[dict]:
    """Validate executable predicates that inspect only uploaded contract text."""
    rules: list[dict] = []
    seen: set[str] = set()
    for item in (raw.get("deterministic_rules") or []):
        if not isinstance(item, dict):
            continue
        rule_id = str(item.get("id") or "").strip()
        pattern = str(item.get("pattern") or "").strip()
        if not rule_id or not pattern or rule_id in seen:
            raise ValueError("Deterministic playbook rules require unique non-empty IDs and patterns.")
        try:
            re.compile(pattern, re.IGNORECASE | re.DOTALL)
            exclusions = [str(x).strip() for x in (item.get("exclude_patterns") or []) if str(x).strip()]
            for exclusion in exclusions:
                re.compile(exclusion, re.IGNORECASE | re.DOTALL)
        except re.error as exc:
            raise ValueError(f"Invalid regex in deterministic playbook rule {rule_id}: {exc}") from exc
        seen.add(rule_id)
        rules.append({
            "id": rule_id,
            "risk_domain": str(item.get("risk_domain") or "").strip() or "Commercial Risk",
            "risk_type": str(item.get("risk_type") or "").strip() or rule_id,
            "question": str(item.get("question") or "").strip(),
            "pattern": pattern,
            "exclude_patterns": exclusions,
            "explanation": str(item.get("explanation") or "").strip(),
            "sources": [str(x).strip() for x in (item.get("sources") or []) if str(x).strip()],
        })
    return rules


def normalize_playbook(raw: dict) -> dict:
    clause_types = {}
    for name, payload in (raw.get("clause_types") or {}).items():
        payload = payload or {}
        checklist = []
        for item in payload.get("checklist") or []:
            checklist.append(
                {
                    "id": str(item.get("id") or "").strip(),
                    "clause_type": str(name),
                    "risk_domain": str(item.get("risk_domain") or "").strip() or None,
                    "risk_subdomain": str(item.get("risk_subdomain") or "").strip() or None,
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
                "risk_subdomain": str(item.get("risk_subdomain") or "").strip() or None,
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
                "risk_subdomain": str(item.get("risk_subdomain") or "").strip() or None,
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
        "deterministic_rules": _normalize_deterministic_rules(raw),
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


def _git_blob_sha(data: bytes) -> str:
    """Return Git's content-addressed blob SHA for exact file bytes."""
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


@lru_cache(maxsize=4)
def _load_registry_bundle(directory: str, expected_blob_sha: str) -> tuple[dict, dict, dict]:
    root = Path(directory)
    manifest_path = root / "rule_registry_manifest.json"
    registry_path = root / "rule_registry.jsonl"
    source_path = root / "source_registry.json"
    for required_path in (manifest_path, registry_path, source_path):
        if not required_path.exists():
            raise RuntimeError(f"Governed rule registry is incomplete: missing {required_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        source_registry = json.loads(source_path.read_text(encoding="utf-8"))
        records = [
            json.loads(line)
            for line in registry_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Governed rule registry cannot be parsed: {exc}") from exc

    if manifest.get("source_playbook_hash") != expected_blob_sha:
        raise RuntimeError(
            "Governed rule registry is stale: its source_playbook_hash does not match "
            "the exact committed playbook bytes. Regenerate the registry before running Phase 2."
        )
    if source_registry.get("source_playbook_hash") != expected_blob_sha:
        raise RuntimeError("Source registry fingerprint does not match the current playbook.")
    if len(records) != int(manifest.get("total_rule_records") or -1):
        raise RuntimeError("Rule registry record count does not match its manifest.")

    base_records = [item for item in records if item.get("record_kind") == "BASE_RULE"]
    candidate_records = [
        item for item in records
        if item.get("record_kind") == "CONTEXT_VARIANT_CANDIDATE"
    ]
    if len(base_records) != int(manifest.get("base_rule_count") or -1):
        raise RuntimeError("Base rule count does not match the registry manifest.")
    if len(candidate_records) != int(manifest.get("candidate_rule_count") or -1):
        raise RuntimeError("Candidate rule count does not match the registry manifest.")
    if any(item.get("execution_eligible") is not False for item in candidate_records):
        raise RuntimeError("A context candidate is incorrectly enabled for execution.")

    by_key: dict[str, dict] = {}
    for item in base_records:
        key = str(item.get("base_rule_key") or "")
        if not key or key in by_key:
            raise RuntimeError(f"Duplicate or missing base rule registry key: {key!r}")
        by_key[key] = item
    sources = {
        str(item.get("source_id")): item
        for item in (source_registry.get("sources") or [])
        if item.get("source_id")
    }
    return sources, by_key, manifest


def _registry_public_metadata(record: dict) -> dict:
    return {
        "registry_rule_id": record.get("rule_id"),
        "base_rule_key": record.get("base_rule_key"),
        "validation_status": record.get("validation_status"),
        "approval_status": record.get("approval_status"),
        "execution_status": record.get("execution_status"),
        "execution_eligible": record.get("execution_eligible"),
        "jurisdiction_scope": record.get("jurisdiction_scope") or ["UNSPECIFIED"],
        "jurisdiction_status": record.get("jurisdiction_status") or "UNRESOLVED",
        "jurisdiction_review_required": bool(record.get("jurisdiction_review_required", True)),
        "source_status": record.get("source_status") or "INCOMPLETE_SOURCE_CITATION",
        "source_ids": record.get("source_ids") or [],
        "source_tier": record.get("source_tier") or [],
        "authority_jurisdictions": record.get("authority_jurisdictions") or [],
        "effective_dates": record.get("effective_dates") or [],
        "pinpoint_citations": record.get("pinpoint_citations") or [],
        "citation_status": record.get("citation_status") or "INCOMPLETE_SOURCE_CITATION",
        "legal_authority": record.get("legal_authority") or {},
        "legal_conclusion_allowed": False,
        "source_playbook_hash": record.get("source_playbook_hash"),
    }


def _attach_rule_registry(normalized: dict, raw: dict, path: Path) -> dict:
    source_bytes = path.read_bytes()
    expected_blob_sha = _git_blob_sha(source_bytes)
    source_by_id, base_by_key, manifest = _load_registry_bundle(
        str(path.parent), expected_blob_sha
    )

    # Replace vague legacy source metadata with explicit source records. Unknown
    # fields stay null and carry a citation_status; they are never guessed.
    merged_sources = {}
    for source_id, old_record in (normalized.get("sources") or {}).items():
        record = dict(old_record)
        if source_id in source_by_id:
            record.update(source_by_id[source_id])
        record["id"] = source_id
        record["source_url"] = record.get("source_url") or record.get("url")
        record["url"] = record.get("source_url")
        merged_sources[source_id] = record
    normalized["sources"] = merged_sources

    def attach(item: dict, family: str, category: str | None = None) -> None:
        item_id = str(item.get("id") or "").strip()
        key = f"{family}::{category}::{item_id}" if category else f"{family}::{item_id}"
        record = base_by_key.get(key)
        if record is None:
            raise RuntimeError(f"Rule registry is missing active playbook check {key!r}")
        item["rule_registry_metadata"] = _registry_public_metadata(record)
        item["jurisdiction_scope"] = record.get("jurisdiction_scope") or ["UNSPECIFIED"]

    for category, payload in (normalized.get("clause_types") or {}).items():
        for item in payload.get("checklist") or []:
            attach(item, "CLAUSE_CHECK", category)
    for item in normalized.get("cross_clause_checks") or []:
        attach(item, "CROSS_CLAUSE_CHECK")
    for item in normalized.get("document_level_checks") or []:
        attach(item, "DOCUMENT_CHECK")
    for item in normalized.get("deterministic_rules") or []:
        attach(item, "DETERMINISTIC_REGEX")

    normalized["rule_registry"] = {
        "version": manifest.get("registry_version"),
        "status": "PILOT_REVIEW_ONLY",
        "policy_status": manifest.get("policy_status"),
        "source_playbook_blob_sha": expected_blob_sha,
        "base_rule_count": manifest.get("base_rule_count"),
        "candidate_rule_count": manifest.get("candidate_rule_count"),
        "production_approved_rule_count": manifest.get("production_approved_rule_count"),
        "source_citation_status": "INCOMPLETE",
        "legal_conclusion_allowed": False,
    }
    # Include the attached governance/source metadata in the run identity.
    normalized.pop("playbook_hash", None)
    normalized["playbook_hash"] = playbook_hash(normalized)
    return normalized


def load_playbook(path: Path | None = None) -> dict:
    path = Path(path or RISK_PLAYBOOK_PATH)
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            normalized = normalize_playbook(raw)
            registry_files = (
                path.parent / "rule_registry_manifest.json",
                path.parent / "rule_registry.jsonl",
                path.parent / "source_registry.json",
            )
            if any(item.exists() for item in registry_files):
                normalized = _attach_rule_registry(normalized, raw, path)
            return normalized
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            raise RuntimeError(
                f"Configured risk playbook is present but invalid: {path}: {exc}"
            ) from exc
    return starter_playbook()


_STRONG_RISK_KEYWORDS = {
    "assignment", "assign", "liability", "cap", "indemnity", "indemnify",
    "indemnification", "insurance", "audit", "inspect", "warranty", "warranties",
    "license", "licence", "sublicense", "perpetual", "irrevocable", "uncapped",
    "unlimited", "termination", "terminate", "renewal", "renew", "exclusive",
    "exclusivity", "non-compete", "noncompete", "non-solicit", "nonsolicit",
    "non-solicitation", "solicit", "escrow", "royalty", "mfn", "rofr", "rofo",
    "rofn", "ip", "transferable", "disparagement", "penalty", "discount",
    "adjustment", "price", "transition", "wind-down", "revenue sharing", "profit sharing",
    "net sales", "net revenue", "profit share", "liquidated damages",
    "minimum commitment", "take or pay", "change of control", "governing law",
    "intellectual property", "source code", "work product", "deliverables",
    "third-party beneficiary", "third party beneficiary", "covenant not to sue",
    "joint ownership", "price restriction", "volume restriction", "usage cap",
    "quantity limit", "right of first refusal", "right of first offer",
    "right of first negotiation", "post-termination", "non-renewal",
    "without limitation", "fees paid", "aggregate liability", "maximum liability",
    "liability shall not exceed", "no assignment without consent",
    "shall not assign", "may not assign", "field of use", "all right, title and interest",
}
_GENERIC_PLAYBOOK_KEYWORDS = {
    "upon reasonable notice", "for any reason", "under any circumstances",
    "requirements", "coverage", "customers", "employees", "territory",
    "duration", "fees", "notice", "term", "sole", "records", "report",
    "affiliate", "customer",
}


def _keyword_matches_clause(clause_text: str, keyword: str) -> bool:
    phrase = re.sub(r"\s+", " ", str(keyword or "").strip().lower())
    if not phrase or phrase in _GENERIC_PLAYBOOK_KEYWORDS:
        return False
    if len(phrase.split()) == 1 and phrase not in _STRONG_RISK_KEYWORDS:
        return False
    phrase_pattern = r"\s+".join(re.escape(part) for part in phrase.split())
    pattern = r"(?<!\w)" + phrase_pattern + r"(?!\w)"
    return bool(re.search(pattern, str(clause_text or ""), flags=re.IGNORECASE))


def applicable_checks(
    playbook: dict,
    clause_type: str,
    clause_text: str | None = None,
) -> list[dict]:
    """Select the predicted-label checklist plus other text-relevant playbook checks.

    CUAD's predicted category is a useful retrieval signal, not a hard gate:
    misclassification must not prevent an independently relevant risk check from
    being evaluated. Only explicit, risk-specific playbook keywords add families.
    """
    clause_types = playbook.get("clause_types", {}) or {}
    label = str(clause_type or "").strip()
    matched_categories: list[str] = []
    if label in clause_types:
        matched_categories.append(label)
    else:
        lower = label.lower()
        for name in clause_types:
            if lower and (name.lower() in lower or lower in name.lower()):
                matched_categories.append(name)
                break

    text = str(clause_text or "")
    if text.strip():
        for name, payload in clause_types.items():
            if name in matched_categories:
                continue
            keywords = payload.get("keywords") or []
            if any(_keyword_matches_clause(text, keyword) for keyword in keywords):
                matched_categories.append(name)

    # Duplicate legacy IDs exist across customer and employee non-solicitation.
    # Namespace those runtime IDs by category while retaining their original IDs.
    categories_by_id: dict[str, set[str]] = {}
    for category, payload in clause_types.items():
        for item in payload.get("checklist") or []:
            item_id = str(item.get("id") or "").strip()
            if item_id:
                categories_by_id.setdefault(item_id, set()).add(category)
    duplicate_ids = {item_id for item_id, categories in categories_by_id.items() if len(categories) > 1}

    checks: list[dict] = []
    seen_rules: set[tuple[str, str]] = set()
    for name in matched_categories:
        payload = clause_types.get(name) or {}
        for original in payload.get("checklist") or []:
            base_id = str(original.get("id") or "").strip()
            key = (name, base_id)
            if not base_id or key in seen_rules:
                continue
            seen_rules.add(key)
            check = dict(original)
            check["_playbook_category"] = name
            check["_base_check_id"] = base_id
            if base_id in duplicate_ids:
                category_slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
                check["id"] = f"{base_id}@{category_slug}"
            checks.append(check)
    return checks


def source_records(playbook: dict, ids: list[str]) -> list[dict]:
    return [
        dict(playbook.get("sources", {}).get(source_id) or {"id": source_id})
        for source_id in ids
    ]
