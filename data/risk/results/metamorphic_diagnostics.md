# Metamorphic diagnostics — Phase 2

- Status: COMPLETED
- Cases: 10
- Relation checks passed: 4/10 (40.0%)
- Interpretation: controlled consistency diagnostics, **not** real-contract accuracy or legal correctness.

| Case | Target | Observed | Relation | Time |
|---|---|---|---|---:|
| X1-BASELINE | X-1 | INSUFFICIENT_EVIDENCE | FAIL | 43.9s |
| X1-EVIDENCE-DELETION | X-1 | INSUFFICIENT_EVIDENCE | PASS | 54.1s |
| X1-NEGATION-CONTROL | X-1 | POTENTIAL_RISK | FAIL | 33.1s |
| X1-SCOPE-CHANGE | X-1 | POTENTIAL_RISK | PASS | 30.9s |
| X1-REPAIR | X-1 | POTENTIAL_RISK | FAIL | 31.7s |
| X1-MISSING-CONTEXT | X-1 | INSUFFICIENT_EVIDENCE | PASS | 34.6s |
| X1-ORDER-INVARIANCE | X-1 | POTENTIAL_RISK | FAIL | 34.0s |
| X1-DUPLICATE-UNRELATED | X-1 | INSUFFICIENT_EVIDENCE | PASS | 38.2s |
| X4-BASELINE | X-4 | INSUFFICIENT_EVIDENCE | FAIL | 36.8s |
| X4-EXIT-REPAIR | X-4 | INSUFFICIENT_EVIDENCE | FAIL | 37.6s |

## Counterexamples

### X1-BASELINE
- Expected relation: POTENTIAL_RISK expected for constructed stress case; exact evidence required.
- Observed: INSUFFICIENT_EVIDENCE / DON'T KNOW
- Rationale: No usable model answer was returned.
- Evidence: `[]`

### X1-NEGATION-CONTROL
- Expected relation: Should move away from POTENTIAL_RISK; NO_RISK or abstention is acceptable.
- Observed: POTENTIAL_RISK / YES
- Rationale: The liability cap explicitly includes indemnification and liquidated damages, but the clause on insurance states a higher required insurance limit ($150,000) than the liability cap ($100,000), creating a potential inconsistency or overlap between capped and uncapped liability heads.
- Evidence: `[{"clause_id": 0, "quote": "Supplier liability is capped at $100,000, including indemnification obligations and liquidated damages."}, {"clause_id": 1, "quote": "Liquidated damages for delay are expressly subject to and included within the liability cap."}, {"clause_id": 9, "quote": "Indemnification obligations are expressly subject to and included within the liability cap."}]`

### X1-REPAIR
- Expected relation: Should move away from POTENTIAL_RISK; NO_RISK or abstention is acceptable.
- Observed: POTENTIAL_RISK / YES
- Rationale: The liability cap explicitly includes indemnification and liquidated damages, but the clause also states that no liability head is outside or uncapped. This creates an ambiguity about whether the cap applies to all liability heads or if there are exceptions, which could lead to inconsistent or unclear overlap between capped and uncapped liability heads.
- Evidence: `[{"clause_id": 0, "quote": "Supplier liability is capped at $100,000, including indemnification obligations and liquidated damages. No liability head is outside or uncapped under this Agreement."}, {"clause_id": 1, "quote": "Liquidated damages for delay are expressly subject to and included within the liability cap."}, {"clause_id": 9, "quote": "Indemnification obligations are expressly subject to and included within the liability cap."}]`

### X1-ORDER-INVARIANCE
- Expected relation: Status should match baseline; evidence locators may change.
- Observed: POTENTIAL_RISK / YES
- Rationale: The liquidated damages are explicitly outside the liability cap, but the clause also states that other liability heads are capped, creating an overlap and potential inconsistency in liability treatment.
- Evidence: `[{"clause_id": 11, "quote": "2. LIQUIDATED DAMAGES. Supplier shall pay $1,000,000 in liquidated damages for delay, and those liquidated damages are expressly outside the cap."}, {"clause_id": 12, "quote": "1. LIABILITY CAP. Supplier liability is capped at $100,000, except that indemnification obligations and liquidated damages are uncapped and remain outside the cap. Other liability heads are capped, creating overlap between capped and uncapped heads."}]`

### X4-BASELINE
- Expected relation: Constructed stress case expected POTENTIAL_RISK; exact evidence required.
- Observed: INSUFFICIENT_EVIDENCE / DON'T KNOW
- Rationale: No usable model answer was returned.
- Evidence: `[]`

### X4-EXIT-REPAIR
- Expected relation: Should move away from POTENTIAL_RISK; NO_RISK or abstention is acceptable.
- Observed: INSUFFICIENT_EVIDENCE / DON'T KNOW
- Rationale: No usable model answer was returned.
- Evidence: `[]`

## Provenance

- Model config: `qwen3:8b`
- Fixture SHA-256: `c67f5c7e3dee8eaa295d4ea823da9212e2308609d155ecb0b5f528ed9edbff6c`
- Playbook SHA-256: `e677e1d1e88deb1f9c2cb30c0cd994b1b6835cda593804c807941a11c5e04440`
- Analyzer SHA-256: `860fb72c34c0bf9d8eecdc7247fe13d85b050821039f517346b820b17494a7a9`
- Runner SHA-256: `8f017943079e27d7e8965880e976ebf6058b72069f7c9bd35c4354190dd2d79d`
- Labels: `AUTHORED_METAMORPHIC_SPECIFICATION_NOT_HUMAN_GOLD`.
