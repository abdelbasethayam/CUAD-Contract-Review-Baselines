#!/usr/bin/env python3
"""Normalize playbook checks to the canonical 10-domain taxonomy.

Default mode validates only. Pass --apply to update the source playbook.
Existing non-canonical domain labels are retained as risk_subdomain.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK = ROOT / "data" / "risk" / "commercial_clause_risk_playbook.json"

DOMAINS = {
    "Financial Risk", "Liability Risk", "Termination Risk", "Operational Risk",
    "Compliance Risk", "Insurance Risk", "Intellectual Property Risk",
    "Assignment / Control Risk", "Dispute Resolution Risk", "Commercial Risk",
}

CLAUSE_DOMAIN = {
    "Anti-Assignment": "Assignment / Control Risk",
    "Audit Rights": "Compliance Risk",
    "Cap On Liability": "Liability Risk",
    "Change Of Control": "Assignment / Control Risk",
    "Exclusivity": "Commercial Risk",
    "Governing Law": "Dispute Resolution Risk",
    "Insurance": "Insurance Risk",
    "Ip Ownership Assignment": "Intellectual Property Risk",
    "Irrevocable Or Perpetual License": "Intellectual Property Risk",
    "License Grant": "Intellectual Property Risk",
    "Liquidated Damages": "Financial Risk",
    "Minimum Commitment": "Commercial Risk",
    "Most Favored Nation": "Commercial Risk",
    "Non-Compete": "Commercial Risk",
    "No-Solicit Of Customers": "Commercial Risk",
    "No-Solicit Of Employees": "Commercial Risk",
    "Notice Period To Terminate Renewal": "Termination Risk",
    "Post-Termination Services": "Operational Risk",
    "Price Restrictions": "Commercial Risk",
    "Renewal Term": "Termination Risk",
    "Source Code Escrow": "Operational Risk",
    "Termination For Convenience": "Termination Risk",
    "Uncapped Liability": "Liability Risk",
    "Warranty Duration": "Liability Risk",
    "Affiliate License-Licensee": "Intellectual Property Risk",
    "Affiliate License-Licensor": "Intellectual Property Risk",
    "Competitive Restriction Exception": "Commercial Risk",
    "Covenant Not To Sue": "Dispute Resolution Risk",
    "Joint Ip Ownership": "Intellectual Property Risk",
    "Non-Disparagement": "Commercial Risk",
    "Non-Transferable License": "Intellectual Property Risk",
    "Revenue/Profit Sharing": "Financial Risk",
    "Rofr/Rofo/Rofn": "Commercial Risk",
    "Third Party Beneficiary": "Dispute Resolution Risk",
    "Unlimited/All-You-Can-Eat-License": "Commercial Risk",
    "Volume Restriction": "Commercial Risk",
    "Indemnification": "Liability Risk",
}

CROSS_DOMAIN = {
    "X-1": "Liability Risk",
    "X-2": "Financial Risk",
    "X-3": "Termination Risk",
    "X-4": "Commercial Risk",
    "X-5": "Assignment / Control Risk",
    "X-6": "Intellectual Property Risk",
    "X-7": "Intellectual Property Risk",
    "X-8": "Operational Risk",
    "X-9": "Insurance Risk",
    "X-10": "Liability Risk",
}
DOCUMENT_DOMAIN = {
    "DOC-1": "Commercial Risk",
    "DOC-2": "Dispute Resolution Risk",
    "DOC-3": "Dispute Resolution Risk",
}


def assign(item: dict, domain: str) -> None:
    prior = str(item.get("risk_domain") or "").strip()
    if prior and prior not in DOMAINS and not item.get("risk_subdomain"):
        item["risk_subdomain"] = prior
    item["risk_domain"] = domain


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write normalized domain fields")
    args = parser.parse_args()

    data = json.loads(PLAYBOOK.read_text(encoding="utf-8"))
    clause_types = data.get("clause_types") or {}
    missing_mappings = sorted(set(clause_types) - set(CLAUSE_DOMAIN))
    unused_mappings = sorted(set(CLAUSE_DOMAIN) - set(clause_types))
    if missing_mappings or unused_mappings:
        raise SystemExit(
            f"Clause mapping mismatch: missing={missing_mappings}, unused={unused_mappings}"
        )

    seen_checks = 0
    for name, payload in clause_types.items():
        for item in payload.get("checklist") or []:
            assign(item, CLAUSE_DOMAIN[name])
            seen_checks += 1

    for key, mapping in (("cross_clause_checks", CROSS_DOMAIN), ("document_level_checks", DOCUMENT_DOMAIN)):
        items = data.get(key) or []
        expected_ids = set(mapping)
        actual_ids = {str(item.get("id")) for item in items}
        if actual_ids != expected_ids:
            raise SystemExit(
                f"{key} mapping mismatch: missing={sorted(actual_ids - expected_ids)}, "
                f"unmapped={sorted(expected_ids - actual_ids)}"
            )
        for item in items:
            assign(item, mapping[str(item["id"])])

    data["source_version"] = "1.1"
    data["domain_mapping_note"] = (
        "Version 1.1 maps every clause, cross-clause, and document-level check "
        "to one canonical domain from backend/data/legal_knowledge/risk_taxonomy.json. "
        "This is a review-routing taxonomy, not a legal conclusion or gold label. "
        "Earlier finer-grained domain labels are preserved as risk_subdomain."
    )

    all_checks = [
        check
        for payload in clause_types.values()
        for check in (payload.get("checklist") or [])
    ] + (data.get("cross_clause_checks") or []) + (data.get("document_level_checks") or [])
    invalid = [(x.get("id"), x.get("risk_domain")) for x in all_checks if x.get("risk_domain") not in DOMAINS]
    if invalid:
        raise SystemExit(f"Invalid canonical domains: {invalid}")

    print(f"Clause checks: {seen_checks}; cross-clause checks: {len(CROSS_DOMAIN)}; "
          f"document checks: {len(DOCUMENT_DOMAIN)}; mapped domains: {len(DOMAINS)}")
    print(f"Missing domain assignments after normalization: {sum(not x.get('risk_domain') for x in all_checks)}")
    print(f"Mode: {'APPLY' if args.apply else 'CHECK ONLY'}")
    if args.apply:
        PLAYBOOK.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Updated: {PLAYBOOK}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
