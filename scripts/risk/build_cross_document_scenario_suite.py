#!/usr/bin/env python3
"""Build a versioned synthetic scenario suite for all cross/document risk checks.

This suite tests end-to-end behavior on constructed texts. It is not human gold,
not legal advice, and must not be used to claim generalization or legal accuracy.
"""
from __future__ import annotations
import csv, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK = ROOT / "data/risk/commercial_clause_risk_playbook.json"
OUT = ROOT / "data/risk/evaluation/cross_document_v1"
POSITIVE_SOURCE = OUT / "positive_risk_stress_contract.txt"

POSITIVE_TEXT = """SYNTHETIC POSITIVE RISK-STRESS AGREEMENT
Constructed solely for pipeline regression and coverage diagnostics; not legal advice.

1. LIABILITY CAP. Supplier liability is capped at $100,000, except that indemnification obligations and liquidated damages are uncapped and remain outside the cap. Other liability heads are capped, creating overlap between capped and uncapped heads.

2. LIQUIDATED DAMAGES. Supplier shall pay $1,000,000 in liquidated damages for delay, and those liquidated damages are expressly outside the cap.

3. TERM AND RENEWAL. The Agreement has a 12-month term and renews automatically unless non-renewal notice is received at least 18 months before the end of the 12-month term.

4. CONVENIENCE TERMINATION AND MINIMUMS. Customer may terminate for convenience on 30 days notice but remains liable for every remaining minimum commitment and all fees for the remaining term.

5. ASSIGNMENT AND CHANGE OF CONTROL. Assignment requires consent that may be withheld in Supplier's sole discretion. A change of control is deemed assignment but the change-of-control section says it requires no consent, creating different standards for the same event.

6. LICENSE AND TERMINATION. Supplier grants a perpetual, irrevocable, worldwide license, but a separate termination clause says all license rights end automatically on termination.

7. IP OWNERSHIP AND LICENSE GRANT. Customer assigns all newly developed IP to Supplier without a separate license-back. The license grant only covers Supplier-owned materials and does not clearly grant Customer continued rights in its assigned deliverables.

8. CRITICAL SOFTWARE. The licensed software is business-critical, but no source code escrow, continuity commitment, or post-termination support is provided.

9. INSURANCE. Supplier liability is capped at $100,000 while required insurance limits are only $50,000, leaving exposure above stated coverage.

10. INDEMNIFICATION. Indemnification obligations are expressly uncapped and outside the liability cap.

11. INCORPORATED MATERIALS. Services are subject to Supplier's online terms and policies, which may be updated at any time. No fixed version of these terms is attached to the contract package.

12. ORDER OF PRECEDENCE. Supplier's online terms prevail over this signed Agreement in a conflict and may narrow the protective remedies negotiated in this Agreement.

13. GOVERNING LAW AND DISPUTES. Governing law is stated only in the Order Form, while each Order Form may select a different forum and dispute procedure. The current Order Form is not attached.
"""

CONTROL_TEXT = """BALANCED SOFTWARE SERVICES AGREEMENT
Synthetic regression fixture. Not legal advice.

1. LIABILITY CAP. The aggregate liability of either party for all claims under this Agreement, including indemnification and liquidated damages, shall not exceed the greater of fees paid in the preceding twelve months or $1,000,000. No liability is uncapped unless expressly listed in the signed amendment.
2. LIQUIDATED DAMAGES. Any liquidated damages are the exclusive monetary remedy for the specified delay and count toward the aggregate liability cap; the agreed amount shall not exceed $50,000.
3. TERM AND RENEWAL. The initial term is one year. Either party may give written notice of non-renewal at least thirty days before the end of the then-current term.
4. CONVENIENCE TERMINATION. Either party may terminate for convenience on thirty days' written notice. After the effective termination date, no future minimum commitment or remaining-term fees are due; unused prepaid fees are prorated.
5. ASSIGNMENT AND CHANGE OF CONTROL. Either party may assign to an affiliate or successor in a merger or sale of substantially all assets on written notice. The same standard applies to a change of control; no inconsistent consent rule applies.
6. LICENSE DURATION. The license to use the Services continues only during the subscription term. On termination it ends, except that Customer may export its data for ninety days.
7. IP OWNERSHIP. Customer owns its pre-existing materials and customer-specific deliverables. Supplier receives only a limited license to provide the Services. No assignment occurs without a signed schedule that identifies the assigned IP and grants Customer a perpetual, irrevocable license-back.
8. SOFTWARE CONTINUITY. For the identified business-critical software, Supplier maintains source-code escrow, tests releases quarterly, and provides transition support for ninety days after termination.
9. INSURANCE. Supplier shall maintain $5,000,000 of relevant insurance. The aggregate liability cap is $1,000,000, and coverage limits do not reduce or expand the cap.
10. INDEMNIFICATION. Each party's indemnification obligations are subject to the same aggregate cap, claim notice, defense-control and settlement-consent requirements. No indemnity is outside the cap.
11. INCORPORATED MATERIALS. Every incorporated schedule and policy is attached by name, date and version. No external web terms are incorporated by reference.
12. ORDER OF PRECEDENCE. In a conflict, this signed Agreement prevails over an Order Form, schedule or other document unless a later amendment is signed by both parties and explicitly names the clause it replaces.
13. LAW AND DISPUTES. This Agreement is governed by New York law; exclusive venue is the state and federal courts in New York County. No inconsistent online forum or arbitration procedure applies.
"""

INCOMPLETE_TEXT = """INCOMPLETE AGREEMENT EXTRACT
Synthetic incomplete-package fixture. Missing attachments must be treated as unread/unknown, not assumed to be absent.

1. LIABILITY. Liability is subject to the cap in Appendix C, but Appendix C was not provided. Another sentence excludes some categories without identifying their limit.
2. DAMAGES. Any service credits and liquidated damages are defined in the missing Order Form. The cap interaction is not included in the supplied pages.
3. TERM. The agreement renews as stated in the applicable order, which is not attached. The non-renewal notice deadline is also in the missing order.
4. EXIT. Termination rights are summarized here, but minimum-commitment and early-exit charges are defined in an unavailable pricing schedule.
5. TRANSFER. Assignment is governed by the definition of Control in Schedule 4, which is missing. Change-of-control consequences are not supplied.
6. LICENSE. License duration and post-termination use are set out in an omitted technology schedule.
7. IP. Ownership and license-back terms are incorporated from an IP schedule that was not included with this copy.
8. SOFTWARE CONTINUITY. Escrow and transition-support details are in the missing service continuity appendix.
9. INSURANCE. Coverage limits are specified in the certificate and policy schedule, neither of which was included.
10. INDEMNIFICATION. The scope and cap treatment of indemnification are in a referenced exhibit not supplied for this review.
11. ONLINE TERMS. The Services are subject to Supplier's online terms, which may change from time to time; no fixed version is attached to the package.
12. PRECEDENCE. If provisions conflict, the applicable Order Form and Supplier online terms may govern, but the relevant terms were not provided.
13. LAW AND DISPUTES. Governing law is set out in the Order Form and forum/dispute procedures in Supplier policies; neither is attached.
"""

# Every row is an authored test stimulus. The expected behavior describes the
# intended reading of this synthetic fixture, not a gold label for real contracts.
EXPECTATIONS = {
    "X-1": {
        "positive": ("POTENTIAL_RISK", ["LIABILITY CAP", "uncapped", "indemnification obligations"], "Capped and uncapped liability heads overlap."),
        "control": ("NO_RISK", ["including indemnification and liquidated damages", "No liability is uncapped"], "All relevant heads fall within a defined cap."),
        "incomplete": ("INSUFFICIENT_EVIDENCE", ["Appendix C", "not provided"], "The referenced cap/exception details are absent from the supplied package."),
    },
    "X-2": {
        "positive": ("POTENTIAL_RISK", ["liquidated damages", "outside the cap"], "Liquidated damages are described as outside the cap."),
        "control": ("NO_RISK", ["count toward the aggregate liability cap"], "Liquidated damages expressly count toward the cap."),
        "incomplete": ("INSUFFICIENT_EVIDENCE", ["missing Order Form", "cap interaction is not included"], "The liquidated-damages rule and cap interaction are in unavailable documents."),
    },
    "X-3": {
        "positive": ("POTENTIAL_RISK", ["18 months", "12-month term"], "Notice timing cannot fit within the contract term."),
        "control": ("NO_RISK", ["thirty days before the end of the then-current term"], "The notice deadline is calculable inside the renewal term."),
        "incomplete": ("INSUFFICIENT_EVIDENCE", ["applicable order", "not attached"], "The term/notice details are unavailable."),
    },
    "X-4": {
        "positive": ("POTENTIAL_RISK", ["terminate for convenience", "remaining term", "minimum commitment"], "Exit triggers remaining-term/minimum-payment exposure."),
        "control": ("NO_RISK", ["no future minimum commitment or remaining-term fees are due"], "Future minimum and remaining-term fees are expressly waived on exit."),
        "incomplete": ("INSUFFICIENT_EVIDENCE", ["unavailable pricing schedule"], "Exit charge amount and triggers cannot be determined."),
    },
    "X-5": {
        "positive": ("POTENTIAL_RISK", ["change of control", "sole discretion", "consent"], "Assignment and change-of-control standards are materially different."),
        "control": ("NO_RISK", ["same standard applies to a change of control"], "The same objective transfer rule covers both events."),
        "incomplete": ("INSUFFICIENT_EVIDENCE", ["Schedule 4, which is missing"], "The controlling definition is unavailable."),
    },
    "X-6": {
        "positive": ("POTENTIAL_RISK", ["perpetual, irrevocable", "license rights end automatically"], "Perpetual/irrevocable and termination language conflict."),
        "control": ("NO_RISK", ["continues only during the subscription term", "On termination it ends"], "License duration is aligned with the contract term."),
        "incomplete": ("INSUFFICIENT_EVIDENCE", ["omitted technology schedule"], "The duration/termination provisions are not supplied."),
    },
    "X-7": {
        "positive": ("POTENTIAL_RISK", ["Customer assigns all newly developed IP", "without a separate license-back"], "IP assignment leaves no clear continuing license-back."),
        "control": ("NO_RISK", ["Customer owns", "limited license", "perpetual, irrevocable license-back"], "Ownership and continuing rights are stated coherently."),
        "incomplete": ("INSUFFICIENT_EVIDENCE", ["IP schedule that was not included"], "Ownership/assignment scope cannot be confirmed without the missing schedule."),
    },
    "X-8": {
        "positive": ("POTENTIAL_RISK", ["business-critical", "no source code escrow"], "Critical software lacks continuity/escrow support."),
        "control": ("NO_RISK", ["source-code escrow", "transition support"], "Escrow and transition controls are explicit."),
        "incomplete": ("INSUFFICIENT_EVIDENCE", ["missing service continuity appendix"], "Escrow/support status is not knowable from the package."),
    },
    "X-9": {
        "positive": ("POTENTIAL_RISK", ["liability cap", "$100,000", "$50,000"], "Insurance limits are materially below a stated liability exposure."),
        "control": ("NO_RISK", ["$5,000,000", "$1,000,000"], "Coverage exceeds the cap and is specified."),
        "incomplete": ("INSUFFICIENT_EVIDENCE", ["policy schedule, neither of which was included"], "Coverage limits are missing."),
    },
    "X-10": {
        "positive": ("POTENTIAL_RISK", ["indemnification obligations are expressly uncapped", "outside the liability cap"], "Indemnification is expressly outside a monetary cap."),
        "control": ("NO_RISK", ["indemnification obligations are subject to the same aggregate cap"], "Indemnification is explicitly included within the cap."),
        "incomplete": ("INSUFFICIENT_EVIDENCE", ["referenced exhibit not supplied"], "Indemnity scope and cap treatment are unavailable."),
    },
    "DOC-1": {
        "positive": ("POTENTIAL_RISK", ["online terms", "may be updated", "No fixed version"], "Externally incorporated terms can change and are not attached."),
        "control": ("NO_RISK", ["attached by name, date and version", "No external web terms"], "Incorporated materials are identified and fixed."),
        "incomplete": ("POTENTIAL_RISK", ["subject to Supplier's online terms", "no fixed version is attached"], "Flag as UNREAD/review-required; do not claim the missing terms contain a specific risk."),
    },
    "DOC-2": {
        "positive": ("POTENTIAL_RISK", ["online terms prevail", "protective"], "Precedence favors changing external terms over negotiated protections."),
        "control": ("NO_RISK", ["this signed Agreement prevails", "later amendment is signed"], "Precedence protects the signed agreement unless explicitly amended."),
        "incomplete": ("INSUFFICIENT_EVIDENCE", ["may govern", "were not provided"], "The order of precedence cannot be fully resolved from absent terms."),
    },
    "DOC-3": {
        "positive": ("POTENTIAL_RISK", ["Governing law is stated only in the Order Form", "different forum", "dispute procedure"], "Governing law/forum/dispute mechanism is delegated inconsistently."),
        "control": ("NO_RISK", ["New York law", "exclusive venue", "No inconsistent online forum"], "Governing law and exclusive venue are explicit and consistent."),
        "incomplete": ("INSUFFICIENT_EVIDENCE", ["neither is attached"], "Governing law and dispute terms are in unavailable documents."),
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    playbook = json.loads(PLAYBOOK.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    control_path = OUT / "protected_control_contract.txt"
    incomplete_path = OUT / "incomplete_contract_pack.txt"
    POSITIVE_SOURCE.write_text(POSITIVE_TEXT.strip() + "\n", encoding="utf-8")
    control_path.write_text(CONTROL_TEXT.strip() + "\n", encoding="utf-8")
    incomplete_path.write_text(INCOMPLETE_TEXT.strip() + "\n", encoding="utf-8")
    fixtures = {
        "positive": POSITIVE_SOURCE,
        "control": control_path,
        "incomplete": incomplete_path,
    }
    fixture_hashes = {key: sha256(path) for key, path in fixtures.items()}
    check_lookup = {
        str(check.get("id")): check
        for check in list(playbook.get("cross_clause_checks") or []) + list(playbook.get("document_level_checks") or [])
    }
    expected_ids = set(check_lookup)
    if expected_ids != set(EXPECTATIONS):
        raise SystemExit(f"Playbook scenario coverage mismatch: missing={sorted(expected_ids - set(EXPECTATIONS))}; extra={sorted(set(EXPECTATIONS) - expected_ids)}")

    rows = []
    for check_id, variants in EXPECTATIONS.items():
        item = check_lookup[check_id]
        scope = "cross_clause" if check_id.startswith("X-") else "document"
        for scenario_type, (status, anchors, rationale) in variants.items():
            fixture = fixtures[scenario_type]
            rows.append({
                "scenario_id": f"{check_id}-{scenario_type.upper()}",
                "check_id": check_id,
                "scope": scope,
                "scenario_type": scenario_type,
                "expected_status": status,
                "question": item.get("question", ""),
                "risk_domain": item.get("risk_domain", ""),
                "fixture_file": str(fixture.relative_to(ROOT)),
                "fixture_sha256": fixture_hashes[scenario_type],
                "evidence_anchors": anchors,
                "rationale": rationale,
                "label_provenance": "AUTHORED_SYNTHETIC_TEST_STIMULUS_NOT_HUMAN_GOLD",
            })

    jsonl = OUT / "scenario_matrix.jsonl"
    jsonl.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "status": "SYNTHETIC_DIAGNOSTIC_FIXTURE",
        "created_at_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "case_count": len(rows),
        "cross_clause_check_count": len(playbook.get("cross_clause_checks") or []),
        "document_check_count": len(playbook.get("document_level_checks") or []),
        "check_ids_covered": sorted(expected_ids),
        "scenario_types": ["positive", "control", "incomplete"],
        "expected_status_counts": {
            status: sum(row["expected_status"] == status for row in rows)
            for status in sorted({row["expected_status"] for row in rows})
        },
        "fixture_sha256": fixture_hashes,
        "playbook_sha256": sha256(PLAYBOOK),
        "limitation": (
            "Scenario labels are authored for deterministic regression testing and are not independently "
            "annotated real-contract truth. Their pass rates measure fixture behavior only, not model accuracy."
        ),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"cases": len(rows), "checks_covered": len(expected_ids), "fixture_hashes": fixture_hashes, "manifest": str((OUT / "manifest.json").relative_to(ROOT))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
