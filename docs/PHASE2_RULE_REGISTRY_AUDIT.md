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

### F-08 - Trigger polarity and duplicate check IDs

**Status:** MITIGATED IN RUNTIME; REGRESSION TESTED

A code-path review found that positive clause findings were accepted only when the model answer was YES. Existing rules also use NO, missing, silent, and future-tense-only trigger conditions. Supported negative answers could therefore be downgraded to insufficient evidence. The customer and employee non-solicitation categories also reused NS-1 and NS-2, while runtime selection deduplicated on the bare ID. Three prompts were open-ended even though the response schema only accepts YES, NO, or DON'T KNOW.

The runtime now checks answer polarity against the rule's trigger wording, namespaces duplicate non-solicitation IDs by category, and normalizes those three prompts to binary questions. Provenance records the base check ID, category, expected trigger answer, and polarity-policy version. Regression tests cover these paths.

This is a compatibility mitigation for legacy wording, not validation of the underlying policy. The rules still need explicit authoring metadata and independent legal/policy adjudication.

## Release sequence

1. Select and document the first supported jurisdiction(s), contract types, buyer/seller perspective, and effective-date policy.
2. Resolve each rule's legal-authority references and pinpoint citations; keep unverified rules review-only.
3. Have two qualified reviewers independently label findings and exact evidence. A third, independent adjudicator resolves disagreement and records rationale.
4. Freeze the playbook, prompt, model, score version, source registry, and dataset version. Split by whole contract; do not allow clauses from one contract into both calibration and test partitions.
5. Report finding precision/recall/F1 by rule family and jurisdiction, exact-evidence and clause-ID accuracy, unsupported-positive rate, unresolved rate, reviewer agreement, Brier score, ECE, and contract-cluster uncertainty intervals.
6. Approve rules individually through a documented legal-governance process. Re-run validation after every material policy or model change.

## Orchestrator conclusion

The implementation now prevents unsupported ordinal severity outputs, records rule/source provenance, keeps applicability variants disabled, and withholds calibrated confidence until a matching adjudicated artifact passes explicit gates. The remaining blockers are substantive—not cosmetic: source verification, jurisdictional scope, rule approval, and project-specific adjudicated evaluation. Until they are resolved, the defensible output is a **review status plus evidence and an uncalibrated support diagnostic**, not a severity label or confidence percentage.
