"""Conservative deterministic cross-clause interaction signals.

These are candidate signals, not legal conclusions. They identify combinations
that deserve explicit model/human review and provide exact contract evidence.
"""

from __future__ import annotations

from typing import Any


def _has_type(clauses: list[dict[str, Any]], terms: tuple[str, ...]) -> list[dict[str, Any]]:
    lowered = tuple(term.lower() for term in terms)
    return [
        c for c in clauses
        if any(term in str(c.get("predicted_label") or "").lower() for term in lowered)
    ]


def _contains(clauses: list[dict[str, Any]], terms: tuple[str, ...]) -> list[dict[str, Any]]:
    lowered = tuple(term.lower() for term in terms)
    return [
        c for c in clauses
        if any(term in str(c.get("clause_text") or "").lower() for term in lowered)
    ]


def _evidence(clauses: list[dict[str, Any]], limit: int = 4) -> list[dict[str, Any]]:
    return [
        {"clause_id": int(c["clause_index"]), "quote": str(c.get("clause_text") or "")[:1000]}
        for c in clauses[:limit]
        if c.get("clause_index") is not None and str(c.get("clause_text") or "").strip()
    ]


def run_deterministic_cross_checks(clauses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    scope_terms = ("license", "exclusivity", "non-compete", "noncompete", "no-solicit", "affiliate")
    scope_hits = _contains(clauses, scope_terms)
    scope_markers = [c for c in scope_hits if any(x in str(c.get("clause_text") or "").lower() for x in ("territory", "geographic", "customer", "affiliate", "duration", "term"))]
    if len(scope_markers) >= 2:
        results.append({"id": "DET-SCOPE-CONFLICT", "name": "scope_conflict", "candidate": True, "clause_ids": [int(c["clause_index"]) for c in scope_markers[:6]], "evidence": _evidence(scope_markers[:4]), "reason": "Multiple scope-sensitive clause families should be checked for inconsistent territory, customer, affiliate, product, or duration boundaries."})

    economic_hits = _has_type(clauses, ("Exclusivity", "Minimum Commitment", "Volume Restriction", "Price Restriction", "Most Favored Nation", "Revenue/Profit Sharing"))
    if len(economic_hits) >= 2:
        results.append({"id": "DET-ECONOMIC-STACK", "name": "economic_stack", "candidate": True, "clause_ids": [int(c["clause_index"]) for c in economic_hits[:8]], "evidence": _evidence(economic_hits[:5]), "reason": "Multiple commercial constraints can compound spend, capacity, margin, or payment exposure."})

    exit_hits = _has_type(clauses, ("Renewal Term", "Termination For Convenience", "Notice Period To Terminate Renewal", "Post-Termination Services"))
    if len(exit_hits) >= 2:
        results.append({"id": "DET-EXIT-FAILURE", "name": "exit_failure", "candidate": True, "clause_ids": [int(c["clause_index"]) for c in exit_hits[:8]], "evidence": _evidence(exit_hits[:5]), "reason": "Renewal, termination notice, convenience termination, and post-termination obligations require a coherent exit path."})

    remedy_hits = _has_type(clauses, ("Cap On Liability", "Uncapped Liability", "Indemnification", "Warranty", "Liquidated Damages"))
    if len(remedy_hits) >= 2:
        results.append({"id": "DET-REMEDY-MISMATCH", "name": "remedy_mismatch", "candidate": True, "clause_ids": [int(c["clause_index"]) for c in remedy_hits[:8]], "evidence": _evidence(remedy_hits[:5]), "reason": "Liability, indemnity, warranty, damages, and remedy provisions should be reconciled for scope and cap interactions."})

    control_hits = _has_type(clauses, ("Anti-Assignment", "Change Of Control", "ROFR/ROFO/ROFN", "Third-Party Beneficiary"))
    if len(control_hits) >= 2:
        results.append({"id": "DET-CONTROL-MISMATCH", "name": "control_mismatch", "candidate": True, "clause_ids": [int(c["clause_index"]) for c in control_hits[:8]], "evidence": _evidence(control_hits[:5]), "reason": "Transfer, control, pre-emption, and beneficiary provisions can allocate control inconsistently."})

    ip_hits = _has_type(clauses, ("IP Ownership Assignment", "License Grant", "Source Code Escrow", "Post-Termination Services", "Irrevocable Or Perpetual License"))
    if len(ip_hits) >= 2:
        results.append({"id": "DET-IP-CONTINUITY-GAP", "name": "ip_continuity_gap", "candidate": True, "clause_ids": [int(c["clause_index"]) for c in ip_hits[:8]], "evidence": _evidence(ip_hits[:5]), "reason": "IP ownership, license, escrow, and post-termination continuity should be checked as one rights chain."})

    evidence_hits = _has_type(clauses, ("Audit Rights", "Revenue/Profit Sharing", "Most Favored Nation", "Price Restrictions", "Minimum Commitment"))
    evidence_markers = [c for c in evidence_hits if any(x in str(c.get("clause_text") or "").lower() for x in ("records", "report", "audit", "books", "accounting", "retention", "measurement"))]
    if evidence_hits and len(evidence_markers) < len(evidence_hits):
        results.append({"id": "DET-EVIDENCE-GAP", "name": "evidence_gap", "candidate": True, "clause_ids": [int(c["clause_index"]) for c in evidence_hits[:8]], "evidence": _evidence(evidence_hits[:5]), "reason": "A financial or audit-linked obligation may lack visible measurement, records, reporting, or verification mechanics."})

    precedence_hits = _contains(clauses, ("order of precedence", "priority", "in case of conflict", "master agreement", "order form", "exhibit", "schedule", "online terms"))
    if len(precedence_hits) >= 2 and not any(
        any(marker in str(c.get("clause_text") or "").lower()
            for marker in ("order of precedence", "prevail over", "prevails over", "takes precedence", "priority over"))
        for c in precedence_hits
    ):
        results.append({"id": "DET-PRECEDENCE-GAP", "name": "precedence_gap", "candidate": True, "clause_ids": [int(c["clause_index"]) for c in precedence_hits[:8]], "evidence": _evidence(precedence_hits[:5]), "reason": "Multiple incorporated-document references were found without an explicit hierarchy in the visible text."})

    # Single-clause document signals are included because some contract-wide
    # checks are triggered by explicit incorporation/versioning language rather
    # than by the interaction of two clause types. These remain review candidates,
    # not automatic legal conclusions.
    for clause in clauses:
        text = str(clause.get("clause_text") or "")
        lowered = text.lower()
        if clause.get("clause_index") is None or not text.strip():
            continue
        refers_to_external_terms = any(term in lowered for term in (
            "online terms", "website", "incorporated by reference", "terms at",
            "terms available at", "policies referenced",
        ))
        has_missing_or_mutable_version = any(term in lowered for term in (
            "no fixed version", "not attached", "not included", "may be updated",
            "as updated from time to time", "current version",
        ))
        if refers_to_external_terms and has_missing_or_mutable_version:
            results.append({
                "id": "DET-INCORPORATED-UNREAD",
                "name": "incorporated_terms_unread",
                "candidate": True,
                "clause_ids": [int(clause["clause_index"])],
                "evidence": _evidence([clause], limit=1),
                "reason": "The agreement references external terms or policies whose fixed version is missing or mutable; verify the referenced material before review is considered complete.",
            })
        has_precedence_language = any(term in lowered for term in (
            "prevail", "in case of conflict", "notwithstanding anything",
            "order of precedence", "takes precedence",
        ))
        names_external_precedence = any(term in lowered for term in (
            "online terms", "website", "supplier's terms", "supplier terms",
            "policies referenced", "terms of service",
        ))
        if has_precedence_language and names_external_precedence and has_missing_or_mutable_version:
            results.append({
                "id": "DET-PRECEDENCE-OVERRIDE",
                "name": "mutable_external_precedence",
                "candidate": True,
                "clause_ids": [int(clause["clause_index"])],
                "evidence": _evidence([clause], limit=1),
                "reason": "A mutable or unattached external term is stated to prevail in a conflict; inspect which protections it can override.",
            })
        has_law_by_external_form = (
            ("governed by the laws specified in" in lowered or "governing law" in lowered)
            and ("order form" in lowered or "each order form" in lowered)
            and ("different forum" in lowered or "different dispute" in lowered or "forum and dispute procedure" in lowered)
        )
        if has_law_by_external_form:
            results.append({
                "id": "DET-DISPUTE-MECHANISM-AMBIGUITY",
                "name": "dispute_mechanism_ambiguity",
                "candidate": True,
                "clause_ids": [int(clause["clause_index"])],
                "evidence": _evidence([clause], limit=1),
                "reason": "Governing law or dispute mechanics are delegated to order forms that may vary; check that the governing-law, forum and procedure combination is determinable for this contract.",
            })

    return results


__all__ = ["run_deterministic_cross_checks"]