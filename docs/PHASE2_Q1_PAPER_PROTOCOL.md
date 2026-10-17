# Q1-journal research protocol: evidence-grounded commercial contract risk review

## Working title

**Evidence-Grounded and Jurisdiction-Aware Contract Risk Review: A Rule-First, Exception-Tested Evaluation Framework**

## Research question

Can a rule-first contract-review system produce more evidence-grounded, scope-aware, and calibrated buyer-side risk findings than retrieval-only or LLM-only baselines on a frozen, contract-disjoint evaluation set?

## Contribution claims to test (not results to assume)

1. Separate clause presence, contract evidence, commercial review triggers, jurisdictional legal propositions, and calibrated confidence into distinct evaluation targets.
2. Use a traceable authority catalog with scope limits and a 37-clause authority map instead of an unapproved generic playbook.
3. Test positive cases, negative controls, exceptions, cross-clause interactions, missing evidence, and jurisdiction mismatch explicitly.
4. Report calibration only when an adjudicated project-specific gold set supports it; never present an uncalibrated support score as probability or severity.
5. Provide reproducible code, pinned data versions, dataset provenance/licensing notes, and fail-closed CI gates.

## Scope and taxonomy

The existing 37 clause categories are the target taxonomy. The initial legal research scope is U.S. commercial contracts, with federal authority where applicable and narrow New York/Delaware UCC modules for transactions actually within those states' Article 2 sales-of-goods law. These jurisdictions are not default governing law. The system must abstain from legal conclusions when the governing law, transaction type, relevant date, or necessary facts are unresolved.

## Data and benchmark roles

- **CUAD** — clause presence and span evidence over 41 types and 510 commercial contracts; use for classification/localization, not as gold for legal adversity or enforceability. Official dataset page: https://www.atticusprojectai.org/cuad/ ; paper: https://arxiv.org/abs/2103.06268.
- **ContractNLI** — contract-level entailment/contradiction/not-mentioned and evidence spans; use for negation, exceptions, and evidence consistency. Paper: https://aclanthology.org/2021.findings-emnlp.164/ ; DOI: 10.18653/v1/2021.findings-emnlp.164.
- **ACORD** — attorney-rated clause retrieval relevance; use for retrieval quality, not risk correctness. Dataset: https://www.atticusprojectai.org/acord/ ; paper: https://arxiv.org/abs/2411.01120.
- **ContractEval** — clause-level risk-identification benchmark using CUAD; use as a published baseline/task comparator, not as a substitute for project-specific jurisdictional gold. Paper: https://aclanthology.org/2025.nllp-1.19/ ; DOI: 10.18653/v1/2025.nllp-1.19.
- **Project-specific risk gold** — required for risk correctness and confidence calibration. External datasets do not provide the full buyer-side, jurisdiction-aware, adjudicated labels required here.

Do not bundle external contract datasets into this repository unless the exact distribution licence, attribution, source-document rights, and privacy constraints have been checked.

## Gold annotation protocol

For each candidate finding, collect: contract ID; clause category; buyer/customer perspective; exact contiguous contract quote and character offsets; predicted review trigger; reviewer decision (`POTENTIAL_RISK`, `NO_RISK`, `INSUFFICIENT_EVIDENCE`, or `NOT_APPLICABLE`); rationale; applicable law and relevant date where a legal proposition is asserted; source pinpoint; exception/countercondition; and reviewer identity.

- Two qualified reviewers label independently before seeing each other's labels.
- A separate adjudicator resolves disagreements and records rationale and timestamp.
- Separate commercial-preference labels from legal propositions. Reviewers must not label a term legally invalid solely because it is commercially asymmetric.
- Include positive examples, negative controls, boundary/exception cases, contradictory clauses, missing clauses, and jurisdiction-mismatch cases.
- Deduplicate and group related documents/templates before splitting; no contract or near-duplicate template may leak across train, calibration, and test sets.
- Publish the annotation guide, adjudication policy, sampling plan, and inter-annotator agreement statistics before reporting final test results.

## Evaluation design

Use a frozen, contract-disjoint holdout set. Set sample size from a documented pilot and power/precision analysis; do not choose a convenient number after seeing model performance. Stratify by clause category and document type while reporting rare-class uncertainty.

Compare:
1. retrieval/classification baseline;
2. LLM-only baseline with the same input and output schema;
3. rule-first baseline;
4. rule-first plus cross-clause checks and exception tests;
5. rule-first with jurisdiction gate and abstention.

### Primary metrics

- Clause classification: macro-F1, per-class precision/recall, and exact-match accuracy.
- Evidence: exact quote match, token-level F1, evidence precision/recall, and quote provenance violations.
- Risk finding: precision/recall/F1 against adjudicated labels, false-positive rate on negative controls, false-negative rate on positive cases, and abstention coverage/risk.
- Cross-clause consistency: contradiction-detection precision/recall and missed-conflict rate.
- Calibration: Brier score, reliability curve, expected calibration error (ECE), and calibration slope/intercept when sample size permits.
- Governance: source-pinpoint coverage, jurisdiction-resolution coverage, exception-suite coverage, and rate of unsupported legal claims.

Report macro and per-class metrics; micro averages alone can hide failures in rare clause types. Use contract-clustered bootstrap confidence intervals, and paired tests for baseline comparisons. Predefine multiplicity handling and the release threshold before opening the test set.

## Confidence and severity

The system's confidence, if released, means **the calibrated probability that the finding's YES/NO label agrees with the adjudicated review label for the evaluated population**. It is not probability of litigation, monetary loss, breach, enforceability, or legal correctness outside the evaluated population. If calibration gates fail or the population shifts, confidence is null and the system abstains.

Do not use HIGH/MEDIUM/LOW as if these were scientific measurements. If a severity measure is later required, create a separate expert-rated construct with a written rubric and reliability study, or a clearly defined quantitative exposure model with independently supported inputs. Do not derive severity from model confidence.

## Release gates

- Every source record has a retrievable URL, exact pinpoint, jurisdiction, source tier, retrieval date, and currentness/effective-date status.
- Each approved rule has a verified applicability scope and positive/negative/edge regression suite.
- Each adjudicated rule has two independent reviewer records and a separate adjudicator record.
- The test set is contract-disjoint and frozen; results cannot be used to tune thresholds.
- Confidence artifact passes preregistered calibration and uncertainty gates; otherwise confidence stays null.
- Full Python test suite, authority-map validator, registry reproducibility checks, frontend build, and release checks pass.
- A clean-room reproduction command regenerates every committed derived artifact and matches its recorded hash.

## Current state and publication boundary

The repository now contains a 33-record authority catalog, a complete structural map for all 37 clause categories, and tests/CI gates for those artifacts. This closes taxonomy-to-authority *mapping coverage*, not legal validation. Six categories explicitly have no universal primary statute in the initial catalog; they remain contract-specific research items. The old playbook source registry and base rules remain unapproved, and no project-specific adjudicated gold set or validated confidence artifact is available. Consequently, this protocol must not be presented as experimental results, legal validation, or a guaranteed Q1 publication.

## References

1. Hendrycks et al. (2021). *CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review*. NeurIPS Datasets and Benchmarks. https://arxiv.org/abs/2103.06268
2. Koreeda & Manning (2021). *ContractNLI: A Dataset for Document-level Natural Language Inference for Contracts*. Findings of EMNLP. https://doi.org/10.18653/v1/2021.findings-emnlp.164
3. Atticus Project. *ACORD: Attorney-annotated Contract Retrieval Dataset*. https://arxiv.org/abs/2411.01120
4. Liu et al. (2025). *ContractEval: Benchmarking LLMs for Clause-Level Legal Risk Identification in Commercial Contracts*. Natural Legal Language Processing Workshop. https://doi.org/10.18653/v1/2025.nllp-1.19
