# Phase 2 Rule Registry — Independent Review and Release Gates

**Review date:** 2026-10-17  
**Disposition:** `PILOT_REVIEW_ONLY`; **not approved for production legal conclusions**.

This report consolidates implementation, adversarial-rule, statistical-calibration, and benchmark-fit review passes. It is a software and evaluation audit, not a legal opinion.

## Audited state

- **121 base rule records** derived from the current playbook.
- **1,936 disabled context-applicability candidates** (121 × 16 contract profiles).
- **2,057 total registry records**; the 1,936 candidates are hypotheses, not new independently validated rules.
- **0 production-approved rules**.
- **7 source records; 0 verified pinpoint citations**.
- The source playbook remains `UNAPPROVED`.
- No project-specific adjudicated risk gold set or validated calibration artifact is present. Consequently, the system must not emit a numerical prediction-confidence probability.

## Findings

### F-01 — Policy approval is missing

**Status:** `BLOCKS_PRODUCTION`

The baseline policy remains `UNAPPROVED`, every base rule is `DRAFT_UNVALIDATED`, and no rule is approved for a legal conclusion. The rules may produce review prompts during a controlled pilot, but neither a registry count nor a passing CI run constitutes legal approval.

**Required resolution:** assign a responsible legal owner, define the buyer/seller perspective and supported contract types, and approve each rule only after its authority, scope, exceptions, and tests are reviewed.

### F-02 — Legal authority is traceable but not yet verified

**Status:** `BLOCKS_LEGAL_CONCLUSIONS`

Every base rule now has rule-level authority metadata: source tier, authority jurisdiction, effective-date status, pinpoint citation, citation status, URL, license status, and a source-reference array. Missing values remain explicit. The current source registry has **zero verified pinpoints**, so adding metadata fields has improved traceability but has not cured the underlying evidence gap.

**Required resolution:** replace generic homepages, composite citations, and market-practice hypotheses with identifiable source editions and exact pinpoints. For legal propositions, verify primary authority and the jurisdiction/effective period; a source tier is not itself proof of binding force or applicability.

### F-03 — Confidence probability is correctly withheld pending adjudication

**Status:** `BLOCKS_CONFIDENCE_OUTPUT`

The reported target is **prediction correctness**: whether a system YES/NO decision matches the adjudicated reviewer label. It is not legal severity, probability of financial loss, or enforceability. Model-self-reported confidence is ignored. The runtime returns no confidence probability without a matching calibration artifact.

The raw support feature was changed so YES does not receive a higher score merely because the answer is YES. It now depends on evidence validity, model-pass agreement, and indicator matching; it remains a heuristic, not a probability.

**Required resolution:** collect a frozen, dual-annotated and independently adjudicated dataset. Fit only on a contract-disjoint calibration partition and preserve a locked test partition. The fitter requires minimum sample/contract counts, both correctness classes, a calibration-only prevalence baseline, Brier improvement, a positive 95% contract-cluster-bootstrap interval for Brier improvement, and ECE at or below the project's release threshold. Runtime rechecks audit fields and metric gates. These are project guardrails, not universal scientific cutoffs.

### F-04 — The 2,000-record target must not be misrepresented

**Status:** `MITIGATED_WITH_LABELING_REQUIREMENT`

The registry contains 2,057 records, but only 121 are base rules. The 1,936 remaining records represent 16 possible contract-profile applicability variants for each base rule. They inherit the base rule and are disabled until reviewed. They must not be described as 2,057 validated rules or used to inflate an accuracy denominator.

### F-05 — External benchmarks are useful only for task-matched tests

**Status:** `MAPPED_WITH_LIMITATIONS`

| Benchmark | Appropriate use | What it does not establish |
|---|---|---|
| [CUAD](https://www.atticusprojectai.org/cuad/) | Clause-category presence and evidence-span extraction; 510 commercial contracts, 41 clause types | Commercial adversity, enforceability, rule-policy correctness, or calibrated confidence |
| [ContractNLI](https://stanfordnlp.github.io/contract-nli/) | Document-level entailment/contradiction/not-mentioned and evidence spans; particularly useful for negation and exceptions | General buyer-side risk-policy accuracy or jurisdiction-specific legal conclusions |
| [ACORD](https://www.atticusprojectai.org/acord/) | Attorney-rated query-to-clause retrieval and ranking | Whether a retrieved clause is legally risky |
| [ContractEval](https://aclanthology.org/2025.nllp-1.19/) | Closest published methodological comparator for clause-level legal-risk identification using CUAD-derived tasks | This repository's exact risk policy, jurisdictional validity, or probability of loss |
| [MAUD](https://www.atticusprojectai.org/maud/) | Deal-point extraction for M&A agreements only | Non-M&A contract rules or broad commercial-contract accuracy |
| [LegalBench](https://github.com/HazyResearch/legalbench) | Individual reasoning tasks when a documented mapping exists | A single aggregate score for the whole contract-risk system |

Keep each benchmark's results separate and use the dataset's own evaluation protocol. The exact data artifact and license must be checked before redistribution. None is a substitute for a project-specific adjudicated risk benchmark.

### F-06 — Exception tests cover the deterministic seed rules, not all semantic checks

**Status:** `PARTIALLY_MITIGATED`

All seven deterministic regex rules have positive, negative, and edge-case fixtures. CI executes these cases, including negation and scoped carve-outs. This is a meaningful regression gate, but it does not validate the 101 clause checks, 10 cross-clause checks, or 3 document checks as legally correct. Those require rule-family-specific adjudicated examples and ongoing exception discovery.

### F-07 — Passing automation is not a legal-accuracy claim

**Status:** `CONTROL_IN_PLACE; EXTERNAL_VALIDITY_OPEN`

Registry reproducibility, schema validation, exception fixtures, API tests, and frontend build establish software conformance. They do not demonstrate precision/recall against lawyer labels, agreement between reviewers, enforceability, or realized financial-loss prediction.

## Follow-up governance hardening — 2026-10-17

The follow-up implementation adds executable JSON Schema validation for every base/candidate registry record and source record, removes frozen exact-count and zero-verified-source assumptions, and derives candidate counts from the base-rule count and configured profiles. Source metadata can now be supplied through the governed playbook input instead of being permanently shadowed by legacy defaults. A source counts as having a verified pinpoint only when the pinpoint and retrieval date are both present.

The new `data/risk/rule_review_queue.csv` contains one work item per actual base rule and is regenerated by `scripts/risk/build_rule_review_queue.py`. It carries decision logic, required contract evidence, linked source metadata, existing regression cases, two independent reviewer decision slots, an adjudicator record, approval fields, and next actions. The queue does not generate legal facts or fill missing test cases.

**Current exception-coverage result: 7 of 121 base rules have complete positive/negative/edge suites; 114 remain incomplete.** The current source/jurisdiction audit also finds 36 rules with no linked source, 85 with incomplete or missing pinpoint citations, zero rules with verified pinpoint citations, and zero rules with verified jurisdiction scope (all 121 remain unresolved). The validator reports these coverage gaps explicitly. Incomplete exception suites block rule approval; approval also requires separate reviewer identities and decisions, an independent adjudicator, verified jurisdiction/source scope, and an approval basis. The global playbook remains `UNAPPROVED`; the review queue is an operational backlog, not evidence of legal correctness.

## 37-clause jurisdiction and authority mapping — 2026-10-17

The initial legal-scope decision is U.S. commercial contracts, aligned to the existing CUAD-derived 37-clause taxonomy. This is a research scope, not an assumption that every dataset contract is governed by U.S. law. The supplemental `data/risk/authority_catalog.json` contains 33 traceable authority records; `data/risk/clause_authority_map.json` maps all 37 categories and explicitly limits the relevance of each authority. The generated registry now embeds this authority map and source metadata on every base rule; context-profile candidates inherit the map but remain disabled. The review queue also carries these references and scope notes for the 101 clause checks; cross-clause, document-level, and regex rules are separately marked for context-specific authority review. At this snapshot, 85 of 121 base rules have one or more mapped authority references and 36 require context-specific/no-universal-authority research.

Six categories have no universal primary statute identified in this initial catalog: Audit Rights, Insurance, Post-Termination Services, Non-Disparagement, ROFR/ROFO/ROFN, and Indemnification. These are not silently treated as statute-backed legal rules. Their review triggers remain commercial/contract-text checks until relevant jurisdiction-specific law is established. UCC references are restricted to their statutory scope, especially sale-of-goods transactions; they are not generalized to every SaaS or services agreement.

The authority catalog is not a 50-state survey. The Delaware Supreme Court non-compete opinion is available through a republication host and requires official-docket and subsequent-history checks before any rule approval. The FTC's 2024 nationwide non-compete rule is explicitly not treated as current enforceable law following the agency's 2025 vacatur action. All categories still have `legal_conclusion_allowed=false`.

The new `scripts/risk/validate_clause_authority_map.py` checks the catalog schemas, exact 37-category coverage, source identifiers, HTTPS provenance, authority host class, retrieval dates, and explicit no-universal-authority notes. This is a structural coverage gate, not proof of legal correctness. The Q1 research design is documented in `docs/PHASE2_Q1_PAPER_PROTOCOL.md`.

## Release sequence

1. Select and document the first supported jurisdiction(s), contract types, buyer/seller perspective, and effective-date policy.
2. Resolve each rule's legal-authority references and pinpoint citations; keep unverified rules review-only.
3. Have two qualified reviewers independently label findings and exact evidence. A third, independent adjudicator resolves disagreement and records rationale.
4. Freeze the playbook, prompt, model, score version, source registry, and dataset version. Split by whole contract; do not allow clauses from one contract into both calibration and test partitions.
5. Report finding precision/recall/F1 by rule family and jurisdiction, exact-evidence and clause-ID accuracy, unsupported-positive rate, unresolved rate, reviewer agreement, Brier score, ECE, and contract-cluster uncertainty intervals.
6. Approve rules individually through a documented legal-governance process. Re-run validation after every material policy or model change.

## Orchestrator conclusion

The implementation now prevents unsupported ordinal severity outputs, records rule/source provenance, keeps applicability variants disabled, and withholds calibrated confidence until a matching adjudicated artifact passes explicit gates. The remaining blockers are substantive—not cosmetic: source verification, jurisdictional scope, rule approval, and project-specific adjudicated evaluation. Until they are resolved, the defensible output is a **review status plus evidence and an uncalibrated support diagnostic**, not a severity label or confidence percentage.
