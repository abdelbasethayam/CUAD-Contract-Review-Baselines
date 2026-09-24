# Legal Knowledge Clause Coverage

Coverage means usable local source text exists and is ingested into the
separate `legal_knowledge` Qdrant collection. CUAD classification remains
unchanged and does not provide risk labels.

| Clause Type | Primary Source | Supporting Source(s) | Coverage Status | Risk Indicator Availability |
|---|---|---|---|---|
| Limitation of Liability | WorldCC | ABA | covered | specific cap, uncapped, and exclusion indicators |
| Indemnification | WorldCC | ABA; IBA | covered | scope, defense, notice, and settlement indicators |
| Termination | WorldCC | ABA | covered | unilateral termination, cure, notice, and mechanics indicators |
| Intellectual Property | WIPO | WorldCC | covered | ownership, assignment, license-scope indicators |
| Confidentiality | WIPO | WorldCC | covered | definition, access, and duration indicators |
| Payment | WorldCC | none | covered | payment terms and late-payment indicators |
| Force Majeure | ICC | WorldCC (reference topic) | covered | definition, notice, and mitigation indicators |
| Insurance | WorldCC | none | covered | coverage and policy-term indicators |
| Warranties | WorldCC | none | covered | scope and disclaimer indicators |
| Assignment and Novation | WorldCC | none | covered | assignment and change-of-control indicators |
| Arbitration / ADR | UNCITRAL | ICC public catalog reference only | covered | ADR mechanics indicator |
| Non-Solicitation | none | none | not configured | unavailable; no local source text |
| Sub-Contracting | none | none | not configured | unavailable; no local source text |
| Suspension Rights | none | none | not configured | unavailable; no local source text |
| Termination Assistance | none | none | not configured | unavailable; no local source text |
| Order of Precedence | none | none | not configured | unavailable; no local source text |

The last five rows are intentionally not represented as ingested sources.

## Intellectual Property

primary source: World Intellectual Property Organization - Technology Transfer
Agreements

supporting source: World Commerce & Contracting - Contracting Principles -
Intellectual Property Rights and Indemnification for Third Party IP Claims

coverage status: covered; local source text has been ingested into
`legal_knowledge` and real retrieval returns IP payloads

risk indicator availability: available for unclear IP ownership, broad license
scope, unclear assignment scope, and unclear license rights
