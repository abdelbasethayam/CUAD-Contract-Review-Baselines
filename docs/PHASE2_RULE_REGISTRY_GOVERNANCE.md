# Rule registry governance and expansion plan

## Current truth, not marketing counts

The baseline playbook currently contains 101 clause checks, 10 cross-clause checks, 3 document checks, and 7 deterministic text rules: 121 base rules. The registry generator creates 16 contract-profile applicability candidates per base rule, producing 1,936 disabled candidates and 2,057 total records. These candidates are **not 1,936 new independently authored or approved legal rules**. They are an auditable backlog of context-specific applicability hypotheses. They must not execute until applicability, sources, counterexamples, and reviewer approval are complete.

## Rule lifecycle

1. **DRAFT_UNVALIDATED** — generated or imported; no claim of legal correctness.
2. **IN_REVIEW** — a named legal reviewer checks rule wording, jurisdiction, scope, exceptions, and source.
3. **ADJUDICATED** — independent reviewers have labeled the regression suite and resolved disagreements.
4. **APPROVED** — authorized policy owner has approved the specific jurisdiction/contract-type scope and source set.
5. **REJECTED** — unsafe, duplicate, unsupported, or not useful.

The repository baseline remains `UNAPPROVED`. Runtime may use base rules only as pilot review triggers. No generated context candidate is eligible for execution. Do not mark a rule approved merely because CI passes.

## Required rule record

Each record contains stable identity and family; perspective; contract-type and jurisdiction scope; explicit applicability status; question/trigger/counterconditions/dependencies; evidence requirements and clause identity; source IDs; source completeness; a non-severity impact note; confidence/calibration policy; regression-case slots; validation/approval status; and an execution gate.

## Source metadata policy

All legacy source IDs are represented with explicit fields, including nulls and a machine-readable reason for missing information. Missing fields are not filled with guesses. Current source citations are incomplete: no legacy record has a verified pinpoint citation. In particular, a generic Practical Law reference, a general publisher homepage, a drafting treatise without edition/page, a market-practice assertion, or an unsourced doctrine note cannot support a binding legal conclusion.

Use source tiers as source-type metadata, not as a ranking of legal force. A source may be binding only for the jurisdiction, court/authority, date, and proposition it actually governs. Professional practice sources support review guidance, not legal conclusions. Jurisdiction-sensitive issues remain blocked from legal-conclusion language when governing law is unknown.

## Confidence, not severity

Ordinal `LOW/MEDIUM/HIGH/CRITICAL` labels and the legacy 0–20 severity score are retired from the user-facing risk result. They are not calibrated against adjudicated outcomes. The product should report:
- finding status: `POTENTIAL_RISK`, `NO_RISK`, or `INSUFFICIENT_EVIDENCE`;
- exact contract evidence and source-clause identity;
- a raw support score only as an explicitly uncalibrated diagnostic;
- a numerical confidence probability only when a versioned calibrator has been fit on adjudicated, contract-disjoint data and passed a locked test set;
- mandatory human review for unsupported, ambiguous, jurisdiction-sensitive, or unapproved rules.

Confidence target is **prediction correctness** (whether the system's YES/NO conclusion matches an adjudicated reviewer), not probability that a contract is risky and not severity or financial impact. Do not average clause probabilities into an overall contract probability without a separately trained and tested contract-level calibrator.

## Benchmark substitute

No public dataset is a complete gold standard for this project's buyer-side risk policy. Use a multi-benchmark validation stack:

- **CUAD** — expert-derived clause presence and span evidence. Use for clause retrieval/presence only; not risk correctness or severity.
- **ContractNLI** — document-level entailment/contradiction/not-mentioned with evidence spans. Use for long-context evidence and exception/negation robustness.
- **ACORD** — attorney-rated query-to-clause relevance. Use for retrieval ranking, not risk labels.
- **MAUD** — expert-annotated M&A deal points. Use only for matching M&A question types and deal-point extraction.
- **ContractEval** — closest published clause-level legal-risk identification comparison, but it uses CUAD-derived tasks and does not validate this buyer-side taxonomy, jurisdiction, or severity policy.
- **LegalBench** — broad legal reasoning tasks; use only where the exact task maps to a rule's reasoning primitive.

The actual risk policy requires a project-specific, contract-disjoint, dual-annotator and adjudicated benchmark. Keep calibration and locked test contracts separate. Report finding precision/recall, evidence exact-match and clause-ID accuracy, cross-clause precision/recall, unresolved rate, unsupported-positive rate, and calibration metrics separately. Synthetic tests assess robustness, not population accuracy.

## Independent assessment workstreams

### Workstream A — source and jurisdiction audit
Finding: legacy source references are generic and not pinpointed; target jurisdiction is not configured. Decision: source records expose explicit missing metadata; do not fabricate dates, legal citations, or approval. Legal-conclusion language is disabled.

### Workstream B — confidence/statistical audit
Finding: the legacy severity scale uses hand-chosen thresholds and model-supplied factors, with no adjudicated benchmark. Decision: remove severity from user-facing output; retain raw support only as uncalibrated diagnostics; introduce a versioned correctness calibrator that refuses to produce an artifact without adequate calibration and locked-test data.

### Workstream C — benchmark/coverage audit
Finding: CUAD labels clause presence, not whether a clause is risky; ContractNLI and ACORD target different tasks. Decision: benchmark only the matching task and use independent buyer-side expert adjudication for final risk accuracy.

### Orchestrator decision
The only safe immediate status is **PILOT_REVIEW_ONLY / UNAPPROVED**. The registry can scale the review backlog, but production approval requires real sources, target-jurisdiction decisions, regression counterexamples, dual annotation, adjudication, and a passing locked test.
