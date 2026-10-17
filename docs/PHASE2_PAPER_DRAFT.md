# Evidence-Grounded Contract Risk Screening with a Rule-First Playbook and Exact-Quote Validation

**Status:** Technical system-manuscript draft for author and supervisor review. Empirical claims in this draft are restricted to executable rule conformance, source-quote provenance, classifier-index isolation, synthetic regression behavior and recorded operational tests.

## Abstract

Commercial contract review requires more than clause-category prediction. A provision can be correctly classified while creating an exposure through its wording, exceptions or interaction with another provision. We describe a reproducible contract-review system that separates clause classification from rule-first contract-risk screening. The versioned commercial playbook contains explicit questions, flag conditions, cross-clause checks and document-level checks, together with executable deterministic predicates for clear wording patterns. Those predicates are run against every extracted clause, regardless of its predicted CUAD category. LLM question answering is used only as a complementary reasoning stage over the uploaded clause and related clauses from the same uploaded contract. Every positive finding must retain an exact contiguous quote from that contract. Retrieved CUAD clause examples are not supplied to risk prompts, and risk results are not derived from an annotated risk-text-span dataset or fine-tuning. The release protocol tests rule and taxonomy integrity, exact-evidence behavior, clause-classification index isolation, regression fixtures and operational execution. These checks establish system conformance and reproducibility rather than legal-risk accuracy or enforceability.

## 1. Introduction

A clause classifier answers what type of provision a passage resembles. It does not, by itself, establish whether the clause contains a buyer-side exposure. Risk review instead depends on explicit predicates: what question should be asked, what condition makes the answer adverse, which exclusions or protections matter, and what contract text supports the decision.

This work implements a risk-review prioritization pipeline in which the uploaded agreement is the only source of contract evidence. A versioned playbook specifies review questions and explicit deterministic rules. A taxonomy assigns the resulting issues to stable domains. Contract-level checks evaluate selected interactions, such as indemnification compared with a liability cap or early termination compared with continuing payment obligations.

The principal architectural boundary is important: CUAD category retrieval serves clause classification only. A retrieved training example cannot show that the uploaded contract contains the same provision, and therefore cannot justify a risk finding. The risk stage does not receive retrieved CUAD text spans or fine-tuned parameters. Risk flags instead arise from playbook predicates matched to the uploaded clause, from playbook questions grounded in that clause and same-contract context, or from cross-clause/document questions that cite existing clauses.

## 2. System design

### 2.1 Separate classification and risk screening

The pipeline follows seven steps:

1. Extract text from an uploaded PDF or TXT file and segment the agreement into clauses with stable indices.
2. Run the clause-category classifier. Its prediction is retained as descriptive metadata and can organize category-specific questions.
3. Scan every clause with all executable deterministic playbook rules. This scan is independent of the classifier prediction.
4. Ask applicable playbook checklist questions using the current clause, related clauses from the same uploaded contract, and optional legal/practice guidance. The prompt contains no retrieved CUAD example clauses.
5. Evaluate cross-clause and document-level playbook checks against the uploaded agreement.
6. Verify each positive finding against exact uploaded-contract evidence, and preserve cited clause IDs for interaction findings.
7. Aggregate validated findings using declared risk domains and deterministic review-prioritization signals; save machine-readable artifacts and configuration fingerprints.

### 2.2 Deterministic playbook predicates

The current playbook source version is 1.2. It contains 37 clause types, 101 clause-level questions, 10 cross-clause checks, 3 document-level checks and 7 executable text predicates. The executable rules initially cover:

- express uncapped or unlimited liability wording;
- indemnification stated to be uncapped or outside the liability cap;
- liquidated damages stated to be outside the cap;
- immediate or no-notice termination;
- broad-scope intellectual-property license wording;
- full remaining-term fees or minimum commitments after early exit;
- absolute assignment prohibition wording.

Each rule has a stable identifier, domain, reviewer-facing risk type/question, compiled pattern, optional exclusion patterns, explanation and source references. The rule engine records the exact matched source quote, playbook hash, rule-engine version and rule ID. A rule match is a review trigger, not a legal conclusion.

The rules are deliberately explicit and not exhaustive. A rule that does not match does not prove there is no risk. The question stage remains available for nuanced wording and for issues that cannot be reliably expressed as a compact deterministic pattern.

### 2.3 Playbook questions and flag polarity

Each checklist item is a predicate with a question and a flag condition. An affirmative grammatical answer does not always mean the provision is risky. The engine must apply the supplied flag_if and do_not_flag_if fields. For example, a question about whether an explicit protective limit exists may be answered “yes” while the corresponding risk is “no”; the flag polarity must come from the playbook condition, not from keyword presence alone.

The playbook is policy guidance. It organizes review and determines which conditions should be checked; it does not establish a legal fact about the uploaded agreement.

### 2.4 Same-contract evidence and cross-clause analysis

The current clause and related clauses retrieved from the same uploaded contract are eligible contract evidence. Externally retrieved guidance may help explain why a question matters, but it cannot be used as proof that the relevant term occurs in the agreement. Ten cross-clause checks cover interactions including the liability cap and indemnity, cap and liquidated damages, assignment and change of control, termination and minimum commitment, IP ownership and license rights, and insurance versus residual exposure. Three document-level checks cover incorporated materials, precedence provisions, and governing-law/forum/dispute consistency.

Each positive interaction result must cite existing clause IDs and exact contiguous quotes. Missing or incomplete source material remains unresolved rather than being automatically translated into “no risk.”

## 3. Evidence policy and statuses

The engine uses four visible states:

- POTENTIAL_RISK: an explicit playbook rule triggered or a playbook question identified a condition supported by contract evidence.
- NO_RISK: the applicable question was resolved as not meeting the flag condition, with evidence supporting that answer.
- INSUFFICIENT_EVIDENCE: available text does not support a positive or negative conclusion.
- ERROR: the check failed or its structured output was unusable.

A positive LLM answer whose quote cannot be found in the uploaded clause or permitted same-contract context is rejected or downgraded to insufficient evidence. For deterministic rules, the match is captured directly from the source clause rather than generated by a model. The aggregation stage accepts only positive findings whose evidence passes the source check.

An exact quote validates provenance, not semantic sufficiency or legal correctness. A model can quote the right sentence and still characterize its commercial effect incorrectly. Therefore, source validation is necessary but not sufficient.

## 4. Risk taxonomy and triage

The taxonomy contains ten canonical domains. The domain declared by the playbook check controls routing and aggregation; keyword matches can add suggestions but must not silently override the declared domain. Rule findings expose the rule ID, domain, source quote and explanation so a reviewer can see why the clause was flagged.

Severity/triage signals are intended to prioritize review. They are not calibrated probabilities of loss, legal standards or conclusions about enforceability. If a score is not supported by the configured scoring inputs, the interface must state that it is a triage signal or leave it unavailable.

## 5. Evaluation protocol

The release acceptance criteria are deterministic and reproducible:

1. Every executable rule has a unique ID and a valid compiled regex.
2. Every rule maps to a canonical taxonomy domain and has a risk type, question and explanation.
3. Protective-control and negative test cases do not trigger protected rules when explicit exclusions apply.
4. Direct rule findings contain exact source substrings copied from the uploaded clause.
5. Risk prompts do not include retrieved CUAD training example spans.
6. Clause classification uses a training-only retrieval index and the held-out contract IDs are excluded from its payloads.
7. Cross-clause/document tests exercise explicit positive, protected-control and incomplete-context scenarios, with exact quote and clause-ID validation.
8. Backend unit tests and TXT/PDF upload-smoke checks pass.

This protocol uses the source playbook and authored regression fixtures; it does not use annotated risk-text-span data for flagging or require an annotation queue to release the implementation. The separate CUAD category retrieval benchmark measures clause-category retrieval/classification only and cannot be described as a risk metric.

The status-conformance rate on authored synthetic fixtures indicates whether a particular implementation run produced the expected status for those designed scenarios. It is not a statistical estimate of performance on real contracts. Similarly, passing the quote gate proves that a quote appears in the source, not that the interpretation is legally correct.

## 6. Reproducibility

The playbook hash and deterministic-rule engine version are stored in finding provenance. Resume logic checks both values so a changed rule set invalidates stale saved findings. Reports record source hashes and the status of release checks. The full release script runs playbook validation, classification-index isolation, domain validation, fixture audits, recorded upload-smoke audits and unit tests. Because local Qdrant uses an exclusive file lock, the backend is stopped during the index-integrity check and restarted after the release command finishes.

## 7. Limitations and intended use

This system is a contract-review prioritization tool, not legal advice and not an autonomous legal decision-maker. The current deterministic rules intentionally prioritize explicit textual patterns. Unlisted risks and sophisticated interactions may require playbook questions or reviewer analysis. No claim is made that the current seven patterns cover the full risk surface of commercial agreements.

The acceptance metrics establish software behavior, rule conformance, evidence provenance and reproducibility. They do not estimate legal-risk accuracy, recall over every possible exposure, enforceability, or realized loss. These limitations should be stated explicitly rather than assigning risk-accuracy numbers to metrics that measure a different task.

## 8. Jurisdiction-aware authority provenance

The first legal research scope is U.S. commercial contracts, aligned to the existing 37-category taxonomy. This scope is not a presumption that every source contract is governed by U.S. law. The system must first extract the governing-law and forum provisions and identify whether the transaction concerns goods, services/software, intellectual property, employment-related restrictions, or another subject matter.

A versioned authority catalog now contains 33 traceable records from the U.S. Code, New York Senate, Delaware Code, the Federal Trade Commission, California's official code site, and one Delaware Supreme Court opinion hosted on a republication site. The California statute URL is traceable, but content retrieval returned HTTP 403; it remains an unverified lead. Each record carries its citation and pinpoint, jurisdiction, source tier, retrieval date, effective-date/currentness status, and a scope limitation. The rule registry embeds this authority metadata on each base rule, and the manifest pins the authority-map and authority-catalog hashes. The 1,936 context-profile records inherit their base rule's authority metadata; they are disabled applicability candidates, not 1,936 independent validated legal rules.

The companion authority map covers all 37 clause categories. Thirty-one categories have at least one limited authority lead; six explicitly have no universal primary statute identified in this initial catalog: audit rights, insurance, post-termination services, non-disparagement, ROFR/ROFO/ROFN, and indemnification. This is a scoped research decision, not a claim that no law can ever apply. Those categories remain commercial-review triggers until the contract facts identify a relevant jurisdiction-specific statute or case.

New York and Delaware UCC references are confined to their statutory scope, particularly sales of goods. They are not generalized to every SaaS, software-licensing, employment, or services contract. The FTC's 2024 nationwide Non-Compete Clause Rule is not represented as current enforceable law following the agency's 2025 vacatur action. The Delaware non-compete opinion is marked as a pleading-stage decision and requires an official docket copy and subsequent-history check before any rule approval.

Every mapped rule remains a review trigger, with `legal_conclusion_allowed=false`. A statute link is not a legal conclusion: approval still requires verification of the precise proposition, governing law, relevant date, pinpoint, statutory exceptions, and contract facts. The authority mapping closes a structural traceability gap; it does not establish that the risk rule is correct.

## 9. Adjudicated gold protocol and publication readiness

A machine-readable gold schema and annotation guide now define the evaluation unit, exact contract evidence, reviewer decisions, adjudication, governing-law status, authority references, dataset versioning, and contract/template-disjoint train/calibration/test splits. Two reviewers must label independently, and a separate adjudicator must resolve disagreements. Evidence quotes carry source offsets and hashes; the validator can compare those offsets against the normalized contract text. Legal-proposition labels are rejected unless governing law and the relevant date are verified, each source has a recorded applicability basis and compatible jurisdiction, official text is verified, and source effective-period checks pass.

The schema-only CI gate is not a gold-set result. The repository does not yet contain a project-specific adjudicated risk-gold dataset, so no risk precision/recall, legal correctness, or calibrated confidence claim is reported. The current implementation audit reports 7 of 121 base rules with complete positive/negative/edge regression suites; 114 remain incomplete. This is a material limitation that must be resolved before an empirical Q1 submission.

A defensible empirical paper must evaluate clause presence separately from buyer-side commercial risk, evidence correctness, cross-clause conflict detection, jurisdiction resolution, abstention, and calibration. CUAD can evaluate clause detection/localization, ContractNLI can evaluate contract inference and evidence, and ACORD can evaluate retrieval relevance; none is a substitute for adjudicated legal-risk labels. Report contract-clustered confidence intervals, per-clause metrics, false-positive rates on negative controls, evidence-span correctness, and calibration metrics only where sample size supports them. Do not describe software-test pass rates as legal-risk accuracy.

## References

- CUAD: The Atticus Project. Contract Understanding Atticus Dataset. https://www.atticusprojectai.org/cuad/
- Koreeda, Y. and Manning, C. D. (2021). ContractNLI: A Dataset for Document-Level Natural Language Inference for Contracts. https://aclanthology.org/2021.findings-emnlp.164/
- Liu et al. (2025). ContractEval: Evaluating Large Language Models for Contract-Level Risk Identification and Analysis. https://aclanthology.org/2025.nllp-1.19/
- Wang et al. (2025). ACORD: An Expert-Annotated Retrieval Dataset for Legal Contract Drafting. https://aclanthology.org/2025.acl-long.1206/
