"""Contract-level Phase 2 risk aggregation with no fake probability or severity."""
from __future__ import annotations

from collections import defaultdict
from typing import Callable

from .knowledge_base import match_risk_domains
from .risk_playbook import load_playbook
from .risk_engine import _evidence_valid, _emit
from .risk_scoring import aggregate_contract_triage

ProgressCallback = Callable[[dict], None]


def _valid_positive(findings: list[dict]) -> list[dict]:
    return [
        finding
        for finding in findings
        if finding.get("risk_status") == "POTENTIAL_RISK"
        and bool(finding.get("risk"))
        and (
            bool(finding.get("evidence"))
            if finding.get("scope") in {"cross_clause", "document"}
            else _evidence_valid(
                str(finding.get("evidence") or ""),
                str(finding.get("clause_text") or ""),
                finding.get("related_contract_context") or [],
            )
        )
    ]


def _domain_clause_ids(findings: list[dict]) -> list[int]:
    clause_ids: set[int] = set()
    for finding in findings:
        candidates = []
        if finding.get("clause_index") is not None:
            candidates.append(finding.get("clause_index"))
        candidates.extend(finding.get("clause_ids") or [])
        for candidate in candidates:
            try:
                clause_ids.add(int(candidate))
            except (TypeError, ValueError):
                continue
    return sorted(clause_ids)


def aggregate_clause_risks(findings: list[dict], playbook: dict | None = None) -> dict:
    playbook = playbook or load_playbook()
    positive = _valid_positive(findings)
    insufficient = [f for f in findings if f.get("risk_status") == "INSUFFICIENT_EVIDENCE"]

    # A check's declared playbook domain is authoritative. Taxonomy keyword
    # matching remains a fallback and is retained separately for audit/debugging;
    # it must not silently relabel a finding when a domain is explicitly declared.
    check_by_id = {}
    for payload in (playbook.get("clause_types") or {}).values():
        for check in payload.get("checklist") or []:
            check_by_id[str(check.get("id"))] = check
    for check in (playbook.get("cross_clause_checks") or []):
        check_by_id[str(check.get("id"))] = check
    for check in (playbook.get("document_level_checks") or []):
        check_by_id[str(check.get("id"))] = check

    domain_items = defaultdict(list)
    for finding in positive:
        check = check_by_id.get(str(finding.get("check_id") or ""), {})
        declared_domain = finding.get("risk_domain") or check.get("risk_domain")
        matches = match_risk_domains(
            str(finding.get("clause_text") or finding.get("risk_type") or finding.get("question") or ""),
            str(finding.get("predicted_label") or finding.get("risk_type") or ""),
            finding.get("provenance", {}).get("deterministic_indicators", []),
        )
        taxonomy_domains = list(dict.fromkeys(
            item.get("risk_domain") for item in matches if item.get("risk_domain")
        ))
        if declared_domain:
            domains = [str(declared_domain)]
            finding["taxonomy_suggested_domains"] = [
                domain for domain in taxonomy_domains if domain != declared_domain
            ]
        else:
            domains = taxonomy_domains
            finding["taxonomy_suggested_domains"] = []
        finding["risk_domain"] = declared_domain
        finding["risk_subdomain"] = finding.get("risk_subdomain") or check.get("risk_subdomain")
        finding["risk_domains"] = list(dict.fromkeys(domains))

        for domain in finding["risk_domains"]:
            domain_items[domain].append(finding)

    # Score after canonical domains have been attached so domain-concentration
    # adjustments operate on the declared playbook taxonomy.
    triage = aggregate_contract_triage(positive)

    key_risks = [
        {
            "clause_id": finding.get("clause_index") if finding.get("clause_index") is not None else finding.get("clause_ids"),
            "check_id": finding.get("check_id"),
            "risk_type": finding.get("risk_type"),
            "evidence_clause_index": finding.get("evidence_clause_index"),
            "evidence_scope": finding.get("evidence_scope"),
            "risk_domain": finding.get("risk_domain"),
            "risk_subdomain": finding.get("risk_subdomain"),
            "taxonomy_suggested_domains": finding.get("taxonomy_suggested_domains", []),
            "raw_support_score": finding.get("raw_support_score"),
            "severity_signal": finding.get("severity_signal"),
            "confidence": finding.get("confidence"),
            "confidence_status": finding.get("confidence_status"),
            "ground_truth_status": finding.get("ground_truth_status"),
            "evidence": finding.get("evidence"),
            "why_flagged": finding.get("why_flagged"),
            "risk_domains": finding.get("risk_domains", []),
            "provenance": finding.get("provenance", {}),
            "supporting_sources": finding.get("supporting_sources", []),
        }
        for finding in sorted(
            positive,
            key=lambda item: (
                float(item.get("raw_support_score") or 0.0),
                float(item.get("severity_signal") or 0.0),
            ),
            reverse=True,
        )
    ]

    if positive:
        status = "POTENTIAL_RISK"
        overall_raw_score = triage["overall_score"]
        overall_confidence = None
        confidence_status = "UNCALIBRATED"
        overall_risk = triage["overall_severity"]
        reason = (
            "One or more contract provisions contain evidence-supported "
            "review findings. Contract severity is a deterministic triage "
            "score with explicit interaction overrides; it is not legal advice "
            "or a probability."
        )
    elif insufficient:
        status = "INSUFFICIENT_EVIDENCE"
        overall_raw_score = 0.0
        overall_confidence = None
        confidence_status = "UNCALIBRATED"
        overall_risk = None
        reason = (
            "The available evidence did not support a positive risk finding, "
            "but one or more applicable checks could not be resolved reliably."
        )
    else:
        status = "NO_RISK"
        overall_raw_score = 0.0
        overall_confidence = None
        confidence_status = "UNCALIBRATED"
        overall_risk = None
        reason = "No evidence-supported playbook risk finding was identified."

    affected_set = set()
    for finding in positive:
        if finding.get("clause_index") is not None:
            affected_set.add(int(finding["clause_index"]))
        for clause_id in finding.get("clause_ids") or []:
            try:
                affected_set.add(int(clause_id))
            except (TypeError, ValueError):
                continue
    affected = sorted(affected_set)

    domain_summary = [
        {
            "domain": domain,
            "finding_count": len(items),
            "clauses": _domain_clause_ids(items),
            "max_raw_support_score": max(
                float(item.get("raw_support_score") or 0.0) for item in items
            ),
        }
        for domain, items in sorted(domain_items.items())
    ]

    return {
        "status": status,
        "overall_risk": overall_risk,
        "overall_confidence": overall_confidence,
        "confidence_status": confidence_status,
        "overall_raw_risk_score": overall_raw_score,
        "overall_raw_score_semantics": "deterministic 0-20 triage score; not a probability",
        "severity_status": "RULE_BASED_TRIAGE",
        "risk_domains": domain_summary,
        "key_risks": key_risks,
        "affected_clauses": affected,
        "reason": reason,
        "gold_status": "PLAYBOOK_DERIVED",
        "playbook_hash": playbook.get("playbook_hash"),
        "clause_findings": findings,
        "unresolved_check_count": len(insufficient),
        "overall_score": triage["overall_score"],
        "overall_severity": triage["overall_severity"],
        "aggregation_adjustments": triage["aggregation_adjustments"],
        "human_review_required": bool(triage["human_review_required"] or insufficient),
        "high_count": triage["high_count"],
        "critical_count": triage["critical_count"],
        "two_high_same_domain": triage["two_high_same_domain"],
    }


def build_risk_only_view(findings: list[dict]) -> list[dict]:
    return [
        {
            "clause_id": item.get("clause_index"),
            "clause_type": item.get("predicted_label"),
            "check_id": item.get("check_id"),
            "risk_type": item.get("risk_type"),
            "evidence_clause_index": item.get("evidence_clause_index"),
            "evidence_scope": item.get("evidence_scope"),
            "risk_domain": item.get("risk_domain"),
            "risk_subdomain": item.get("risk_subdomain"),
            "status": item.get("risk_status"),
            "raw_support_score": item.get("raw_support_score"),
            "confidence": item.get("confidence"),
            "confidence_status": item.get("confidence_status"),
            "severity_signal": item.get("severity_signal"),
            "severity_status": "UNCALIBRATED",
            "why_flagged": item.get("why_flagged"),
            "evidence": item.get("evidence"),
            "ground_truth_status": item.get("ground_truth_status"),
            "provenance": item.get("provenance"),
            "supporting_sources": item.get("supporting_sources"),
        }
        for item in findings
        if item.get("risk_status") != "NO_RISK"
    ]
