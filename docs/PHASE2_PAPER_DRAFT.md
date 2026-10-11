# Evidence-Grounded Local Contract Risk Screening: Predicate-Oriented RAG, Exact-Quote Validation, and Cross-Clause Review

**Status:** technical manuscript draft for author/supervisor review; recorded TXT/PDF upload smoke tests and the full release/test suite pass. Submission readiness still depends on bibliographic verification, and confirmation of author list, affiliations, and target venue.  
**Authors:** to be confirmed.  
**Artifact repository:** https://github.com/abdelbasethayam/CUAD-Contract-Review-Baselines

## Abstract

Commercial contract review requires more than identifying clause categories: a provision may be correctly classified yet still create a material risk through its polarity, scope, interaction with other clauses, or relationship to incorporated documents. We describe a reproducible contract-review pipeline that serves LLM inference locally and supports two explicitly separated retrieval profiles: Cohere Embed v3, and a deterministic 768-dimensional local HashingVectorizer fallback for network-independent operation. The local hashing profile is a lexical-vector baseline, not a pretrained semantic embedding model. The pipeline separates clause classification from explicit risk-predicate evaluation and contract-level interaction analysis. The system combines training-only CUAD retrieval for clause classification, a versioned buyer-side risk playbook, same-contract contextual retrieval, separately sourced legal/practice guidance, exact-contiguous-quote validation, canonical risk-domain routing, cross-clause checks, document-level checks, and deterministic review-prioritization scoring. Each uploaded document is associated with a content/configuration-specific run and machine-readable artifacts that preserve segmentation, retrieved examples, clause findings, interaction checks, progress traces, and configuration hashes.

The playbook currently comprises 37 clause types, 101 clause-level checks, 10 cross-clause checks, 3 document-level checks, and 10 canonical risk domains. A held-out 300-task machine-silver diagnostic set was produced by a Qwen3:8B judge and a blind Gemma3:12B verifier. The final decisions were 13 YES, 95 NO, and 192 UNCERTAIN; the two systems directly agreed on 108 cases, agreed on uncertainty in 22, disagreed on 165, and produced five agreements rejected by the evidence gate. All 13 final YES decisions contain exact contiguous evidence in the stored clause, and all twelve configured train/test and index-integrity checks pass. These results characterize workflow behavior, evidence-gate operation, and model disagreement—not risk accuracy. A separate 39-case synthetic cross-clause/document diagnostic matched authored expected statuses in 27/39 cases after batched inference, compared with 11/39 for the one-shot JSON prompt; these are fixture-conformance rates, not accuracy. The human annotation queue remains unannotated, so no human-gold accuracy, legal correctness, or calibrated-risk claim is made. We document the reproducible artifact path and the evaluation boundary required for responsible use without custom risk gold.

**Keywords:** legal NLP; contract review; retrieval-augmented generation; evidence grounding; risk screening; long-document reasoning; abstention; reproducibility.

## 1. Introduction

Commercial contracts encode obligations, exclusions, remedies, termination rights, intellectual-property grants, and incorporated terms across a document. A clause classifier answers which kind of provision a passage resembles; it does not, by itself, establish whether the provision is adverse to a particular reviewing party. Risk can depend on the exact question being asked, the trigger condition defining a flag, the reciprocal nature of a provision, a second clause elsewhere in the agreement, or an order-of-precedence rule that overrides more protective text.

Public legal-NLP resources provide useful adjacent benchmarks. CUAD contains expert-annotated commercial contracts and clause categories [CUAD](https://www.atticusprojectai.org/cuad/). ContractEval studies clause-level legal-risk identification using CUAD [Liu et al., 2025](https://aclanthology.org/2025.nllp-1.19/). ContractNLI evaluates document-level entailment/contradiction/not-mentioned decisions with evidence in non-disclosure agreements [Koreeda and Manning, 2021](https://aclanthology.org/2021.findings-emnlp.164/). ACORD targets expert-rated contract-clause retrieval, with 114 queries and more than 126,000 query-clause pairs [Wang et al., 2025](https://aclanthology.org/2025.acl-long.1206/). These resources address related but non-identical tasks; their labels cannot be silently reused as ground truth for an arbitrary custom buyer-side risk taxonomy.

This work focuses on the system and evaluation protocol connecting these tasks. We implement a local-first pipeline in which classification proposes clause categories, explicit playbook predicates define the issue to check, the uploaded contract supplies the evidence, cross-clause/document checks inspect relationships, and an auditable aggregation layer summarizes review priorities. The design tries to prevent four common conflations: category with risk, retrieved authority with contract evidence, machine consensus with accuracy, and a deterministic triage score with a calibrated probability.

### Contributions

1. **Predicate-oriented risk reasoning.** Every risk check supplies a question and an explicit FLAG IF condition, preventing the model from treating a grammatical answer as the risk label.
2. **Evidence-gated hierarchical analysis.** Positive findings require exact contiguous contract text; clause-level, cross-clause, and document-level findings are represented separately.
3. **Canonical domain routing and reproducibility.** Each playbook check is assigned to one of ten risk domains, while finer labels are retained as subdomains and semantic keyword matches remain advisory. Each run retains a source hash, configuration, playbook/calibration information, source artifacts, trace and results.
4. **Honest evaluation without custom human gold.** We release and characterize a reproducible machine-silver diagnostic set and executable regression tests, but deliberately do not present model agreement as risk accuracy.

### Research questions

- **RQ1 — Evidence integrity:** Can the implementation enforce traceable, exact-contract evidence and keep externally retrieved guidance separate from facts asserted about the uploaded contract?
- **RQ2 — Task decomposition:** What diagnostic behavior emerges when clause-level risk predicates are combined with explicit cross-clause and document-level checks, compared with treating the task as a single clause classifier?
- **RQ3 — Reproducibility and abstention:** Can a repeatable upload workflow preserve configuration/data provenance and explicitly surface disagreement or insufficient evidence instead of forcing binary risk labels?

These questions are scoped to implementation invariants, operational behavior, and the recorded machine-silver outputs. Without adjudicated custom-risk labels, this study cannot answer whether the resulting risk decisions are correct, whether the pipeline detects all material risks, or whether the score predicts realized loss. The questions and results should be read with that boundary.

## 2. Problem Formulation

Let a contract be segmented into clauses C = {c1, ..., cn}. Phase 1 predicts a CUAD category y-hat for each clause. Phase 2 evaluates applicable risk checks Q. A check contains at least a risk question, a FLAG IF condition, conditions that should not be flagged, contract-text locations from which evidence may be drawn, and applicable dependencies and source metadata.

For a check q, the output is a decision d in {POTENTIAL_RISK, NO_RISK, INSUFFICIENT_EVIDENCE, ERROR}, accompanied by a risk type, explanation, evidence, provenance and, when available, a rule-based severity signal. Cross-clause checks are predicates over related clause sets; document-level checks inspect package completeness or interactions involving incorporated or precedence terms.

A risk result must not be inferred from the clause category alone. For example, classifying a passage as Limitation of Liability does not determine whether the cap is reciprocal, whether indemnification sits outside it, or whether exceptions produce asymmetric exposure. Similarly, an affirmative answer to “Is governing law stated?” is not necessarily a risk: the check’s FLAG IF condition determines polarity.

## 3. System Architecture

### 3.1 Document ingestion and clause segmentation

The API accepts PDF and TXT input. An extraction/segmentation stage produces clause-like units with section indices and, where available, source-page/block metadata. A narrow validator asks whether extracted fragments constitute real contractual clauses; the validator inherits GPU placement from the configured Ollama server instead of forcing CPU-only inference. Each run keeps the source document and segmentation output so later stages can be inspected and resumed.

Segmentation errors propagate: an omitted or split provision can affect both classification and cross-clause analysis. Accordingly, segmentation and validation are tracked as distinct stages rather than being hidden inside a single LLM call.

### 3.2 CUAD classification RAG

Each validated clause is embedded and queried against a Qdrant collection intended to contain training documents only. Retrieved examples inform a candidate-constrained CUAD category prediction. The index-integrity checks validate that training and held-out contracts do not overlap in the configured data paths or indexed payloads.

Retrieved examples are classification references, not statements about the uploaded contract. The risk layer must cite the uploaded document, not copy a training example as a finding.

### 3.3 Clause-level risk checks

For an uploaded clause, the risk engine gathers the current clause text, its predicted CUAD category, applicable checks from the playbook, deterministic textual indicators, up to five semantically related clauses from the same contract, and separately retrieved legal/practice guidance if enabled.

The model is instructed to use the contract clause and same-contract context for factual support. External guidance can explain why a question matters but cannot establish that the uploaded agreement contains the relevant language. Risk analysis is not skipped solely because clause classification is unknown; an unknown category can still receive general risk review, subject to the checks actually available.

### 3.4 Evidence validation and abstention

For a positive finding, the quoted evidence must be an exact contiguous substring of the current clause or permitted same-contract context. Cross-clause/document findings additionally associate each quote with a clause ID and validate the quote against the cited clause. Invalid or absent evidence downgrades a positive conclusion to insufficient evidence rather than allowing a positive result through.

The system distinguishes “no risk identified” from “not enough evidence to decide.” A model that returns no usable response must not silently convert a check to NO_RISK. This makes abstention and failure visible in the result, though it does not guarantee that every valid positive finding is semantically correct.

### 3.5 Playbook and canonical taxonomy

The current source-of-truth playbook is source version 1.1: 37 clause types, 101 clause-level checks, 10 cross-clause checks and 3 document-level checks. The 37 targets cover 36 substantive CUAD categories plus a supplemental Indemnification target.

A prior version of the checklist used descriptive, finer-grained domain names inconsistently. The v1.1 mapping assigns every check to one of the ten canonical domains: Financial Risk, Liability Risk, Termination Risk, Operational Risk, Compliance Risk, Insurance Risk, Intellectual Property Risk, Assignment / Control Risk, Dispute Resolution Risk, and Commercial Risk.

The declared playbook domain is authoritative for routing and aggregation. Existing descriptive labels are retained as risk_subdomain; keyword-matched domains are emitted as supplementary suggestions only. Domain assignment is metadata for organizing review, not a conclusion or evidence.

### 3.6 Cross-clause and document-level checks

A single clause can appear acceptable in isolation while forming a problematic combination with another provision. Ten checks examine defined interactions, including liability cap with uncapped liability; liability cap with liquidated damages; renewal and non-renewal notice timing; convenience termination with minimum commitment; assignment restrictions with change of control; perpetual or irrevocable licenses with termination; IP ownership with the license grant; license grant with source-code escrow; liability exposure with insurance; and liability cap with indemnification.

Three document-level checks address missing incorporated materials, precedence clauses that narrow or reverse protections, and governing-law/forum/dispute inconsistencies. Deterministic interaction rules also produce candidate signals such as economic stacks, exit failure, remedy mismatch, IP continuity gaps and precedence gaps. These signals prompt review; they are not final legal findings.

### 3.7 Aggregation and risk score

Positive findings are grouped into the canonical domains and summarized in a contract-risk profile. Four raw dimensions—exposure magnitude, likelihood/uncertainty, scope/duration, and control weakness—are each represented on a 0–5 scale. Their sum gives a 0–20 deterministic triage score, with current bands of Informational 0–3, Low 4–7, Medium 8–11, High 12–15, and Critical 16–20 plus explicit overrides.

This score prioritizes review; it is not a probability of loss, a legal standard, or a calibrated severity estimate. Calibration parameters are scientifically meaningful only if fit on independent adjudicated labels. Since the custom gold queue is empty, the current project does not claim calibrated risk probabilities or calibrated severity.

## 4. Data and Experimental Protocol

### 4.1 CUAD split and leakage controls

The project's custom split contains 410 training contracts and 100 held-out test contracts, with 10,545 training clause rows and 2,556 test clause rows. This is a contract-disjoint project split; it must not be described as the official CUAD split unless directly matched to the official published partition.

The integrity validator currently checks twelve invariants, including no train/test contract overlap, no use of training-only gold documents in the test set, disjoint annotation partitions, held-out-document isolation for silver and expert-presence artifacts, and train-only payloads in the Cohere-era, MPNet and local-hashing Qdrant collections. All twelve checks passed in the recorded integrity report.

### 4.2 Machine-silver tasks

A 300-task risk queue was sampled with 150 tasks assigned to locked test, 75 to calibration and 75 to development. The unit is a contract/clause/check tuple. The queue uses held-out CUAD contract clauses as the text, while the playbook predicate is project-defined.

Two local models were used in the recorded silver run: Qwen3:8B as judge and Gemma3:12B as blind verifier. The verifier was prompted independently, was not shown the judge’s decision, and ran in parallel on a separate Ollama server. Temperature was set to zero, output was parsed as JSON with bounded retries, and positive outputs were required to pass exact contiguous evidence validation. Model disagreements were preserved as UNCERTAIN. A previous locked-test pilot was quarantined from tuning; diagnostics for protocol choices were limited to calibration/development cases.

The output is machine-silver. Both models may make correlated mistakes; agreement is not a proxy for truth.

### 4.3 Human gold and external benchmarks

The 300-row human annotation template exists, but all risk-label and evidence fields remain blank. No custom-risk accuracy metric can therefore be computed.

The repository also stores an expert-derived CUAD contract/category grid of 3,420 tasks across 95 mapped held-out contracts and 36 substantive categories, as well as a secondary clause-presence artifact. These assets can support clause-category/evidence evaluation, not the custom buyer-side risk predicates, risk-type taxonomy, severity, or enforceability.

ContractEval provides published methodology and comparative context for clause-level risk identification, but its presence does not mean its task labels validate this project's distinct custom playbook [ContractEval](https://aclanthology.org/2025.nllp-1.19/). ContractNLI and ACORD are likewise adjacent evaluation resources rather than substitute labels for our risk predicates.

### 4.4 Metrics

Given no human risk labels, this paper reports pipeline/data integrity; counts of machine agreement, disagreement, agreed uncertainty and evidence-gate rejection; rates of exact evidence among machine YES outcomes; regression tests for cross-clause/document evidence checks; and operational upload metrics only when a complete run manifest/result is available.

It does **not** report custom-risk precision, recall, F1, AUROC, calibration, severity agreement or legal correctness.

## 5. Results

### 5.1 Data and playbook integrity

| Measurement | Result |
|---|---:|
| Training contracts | 410 |
| Held-out test contracts | 100 |
| Training clause rows | 10,545 |
| Test clause rows | 2,556 |
| Integrity checks passed | 12 / 12 |
| Clause-level playbook checks | 101 |
| Cross-clause checks | 10 |
| Document-level checks | 3 |
| Canonical risk domains | 10 |
| Human risk labels present | 0 / 300 |

### 5.2 Machine-silver outcomes

| Machine status | Count | Percentage of 300 |
|---|---:|---:|
| Direct machine agreement | 108 | 36.0% |
| Agreement on uncertainty | 22 | 7.3% |
| Machine disagreement | 165 | 55.0% |
| Agreement rejected by evidence gate | 5 | 1.7% |

| Final machine decision | Count | Percentage of 300 |
|---|---:|---:|
| YES | 13 | 4.3% |
| NO | 95 | 31.7% |
| UNCERTAIN | 192 | 64.0% |

All 13 final YES decisions contain an exact contiguous quote in the stored clause. The high uncertainty rate and disagreement rate indicate that these models do not reliably collapse the custom risk task into determinate machine labels under this protocol. These are operational diagnostics only; they do not estimate accuracy.

### 5.3 Synthetic regression tests

The unit-test suite includes controlled synthetic tests that verify a cross-clause finding cites exact text from the contract clauses it names; a document-level finding retains the declared domain and cited evidence; a nonexistent quote is rejected and the decision is downgraded to insufficient evidence; omitted cross/document results are preserved as unresolved instead of being silently converted to NO_RISK; and an explicitly declared playbook domain takes precedence over keyword-matched taxonomy suggestions.

We also added a separate **39-scenario synthetic cross-clause/document diagnostic matrix** at `data/risk/evaluation/cross_document_v1/scenario_matrix.jsonl`. Each of the 10 cross-clause rules and 3 document-level rules has three constructed stimuli: (i) a risk-stressed positive, (ii) a protected-control negative, and (iii) an incomplete-context case intended to trigger abstention or an explicit unread-document review state. The associated contracts, scenario manifest, SHA-256 hashes, and fixture-integrity audit are stored with the matrix. This adds explicit coverage for every X/DOC rule instead of testing only one representative cross-clause check.

The model scenario runner (`scripts/risk/run_cross_document_model_scenarios.py`) executes the actual cross/document reasoning function once per synthetic contract, preserves the model's statuses and cited evidence, and compares those outputs with the intended synthetic behaviors. The engine evaluates four checks per model response (four batches per pass for 13 total checks) to reduce the truncation risk from requesting all 13 findings in one JSON response. If a batch still fails parsing, only its checks abstain; other successfully parsed batches are preserved. Per-finding provenance records the batch size/count, and the experiment records SHA-256 hashes of both the analyzer and runner code. The resulting status-conformance rate is **only synthetic fixture conformance**: these hand-authored examples are not independent expert labels, do not establish risk accuracy or generalization, and must not be described as human gold. Exact-quote checks validate whether a returned citation exists in the fixture, not whether the risk interpretation is legally correct.

#### Cross/document model scenario results

The direct model run on the 39-case synthetic matrix is complete. The original one-shot implementation asked for all 13 cross/document findings in one JSON response; it returned no usable model answer for the positive and protected-control fixtures, producing **11/39 (28.2%)** synthetic-status matches overall. The batched version asks for four checks per response, preserves successful batches when another batch fails, and produced **27/39 (69.2%)** exact expected-status matches on the same scenario IDs, a change of **+16/39 cases**.

| Scenario type | One-shot matches | Batched matches | Batched observed statuses |
|---|---:|---:|---|
| Risk-stressed positive | 0/13 | 10/13 (76.9%) | 10 POTENTIAL_RISK, 3 NO_RISK |
| Protected control | 0/13 | 7/13 (53.8%) | 7 NO_RISK, 2 POTENTIAL_RISK, 4 INSUFFICIENT_EVIDENCE |
| Incomplete context | 11/13 (84.6%) | 10/13 (76.9%) | 4 POTENTIAL_RISK, 9 INSUFFICIENT_EVIDENCE |
| **All scenarios** | **11/39 (28.2%)** | **27/39 (69.2%)** | **16 POTENTIAL_RISK, 10 NO_RISK, 13 INSUFFICIENT_EVIDENCE** |

The three fixtures required 235.349 s (positive), 153.008 s (control), and 189.251 s (incomplete), for about 578 s total for one configured pass. All 39 output rows were present, all 13 checks had three scenario cases, and all positive evidence strings passed the exact-substring gate. The incomplete fixture's four POTENTIAL_RISK outputs are conservative-review warnings for unavailable incorporated materials or unresolved package terms; they are not claims that the absent materials were read.

This is an implementation ablation on hand-authored synthetic cases, **not accuracy**. The improvement is primarily evidence that splitting a large structured response prevents one truncated JSON response from collapsing every check to INSUFFICIENT_EVIDENCE. The remaining 12/39 mismatches reveal important weaknesses: two false positives on protected-control cases, several abstentions on otherwise sufficient controls, and missed risks in positive cases. No conclusion about generalization, real-contract sensitivity, or legal correctness follows from these synthetic fixtures.

These tests validate implementation invariants and scenario coverage. They do not measure legal judgment quality or sensitivity on naturally occurring contracts.

### 5.4 End-to-end upload smoke tests

Five end-to-end upload smoke records passed the six-gate API/evidence/artifact audit, including a post-batching run produced by the updated analyzer, a pre-batching current-code run, a PDF fixture, and single-/three-pass TXT configurations. The separate 16.2-second repeat of the post-batching analysis reused the same analysis ID and is excluded from runtime comparisons. Each run returned HTTP 200, persisted a completed analysis, matched the input SHA-256 to its manifest, validated all positive findings' cited contract text, and produced the required JSON/CSV/trace artifacts.

| Fixture / runtime setting | Clauses returned | Clause findings | Cross-clause checks | Document checks | Risk passes | Runtime | Audit |
|---|---:|---:|---:|---:|---:|---:|---|
| Synthetic TXT contract (previous configuration) | 4 | 13 | 10 | 3 | 3 | 423.0 s | 6/6 checks passed |
| Repository PDF fixture | 2 | 0 | 10 | 3 | 3 | 83.0 s | 6/6 checks passed |
| Same synthetic TXT contract (interactive setting) | 4 | 13 | 10 | 3 | 1 | 171.1 s | 6/6 checks passed |
| Pre-batching current-code TXT upload (2026-10-09) | 11 | 28 | 10 | 3 | 1 | 367.0 s | 6/6 checks passed |
| Updated batching analyzer TXT upload (2026-10-09) | 11 | 28 | 10 | 3 | 1 | 577.2 s | 6/6 checks passed |

The two TXT runs use the same synthetic agreement but different self-consistency settings. The single-pass observation was 2.47 times faster than the three-pass observation (423.0 / 171.1), but this is one observed pair of runs on one server/model configuration, not a throughput benchmark or confidence interval. The interactive server now defaults to one risk-reasoning pass so the output is more practical to inspect; this gives up inter-pass consistency evidence. A single answer is not counted as agreement, risk confidence remains uncalibrated without human gold, and exact-contract evidence validation remains required. The saved three-pass result remains available for audit. The machine-silver experiment is unchanged and still uses its separately recorded blind Qwen3/Gemma3 protocol.

The original three-pass TXT fixture yielded three positive clause findings and three evidence-valid positive cross/document findings. The pre-batching current-code TXT smoke yielded 28 clause risk findings, with X-10 and X-4 classified as POTENTIAL_RISK and DOC-1 as POTENTIAL_RISK. The updated batching analyzer also yielded 28 clause findings; its cross-clause statuses were 4 POTENTIAL_RISK, 2 NO_RISK and 4 INSUFFICIENT_EVIDENCE, while all 3 document-level checks abstained as INSUFFICIENT_EVIDENCE. All positive cross/document evidence passed the quote audit. The PDF fixture returned no applicable CUAD labels and unresolved cross/document checks; this is an abstention/segmentation diagnostic, not evidence of classification accuracy. None of these fixtures is a representative sample and the risks are not human-validated. Audit records: `data/risk/results/smoke_test_audit.json`, `smoke_test_audit_pdf.json`, `smoke_test_audit_fast.json`, `smoke_test_audit_current.json`, and `smoke_test_audit_post_batching.json`.

### 5.5 Offline local-hashing CUAD retrieval baseline

We evaluated the local-only retrieval profile separately from the prior Cohere/retrieval-conditioned SLM configuration. Eligible clause rows exclude CUAD metadata fields. The index contains 7,004 training rows from 383 contracts; held-out evaluation contains 1,679 clauses from 92 contracts. The split is contract-disjoint with zero training/test contract overlap. The vectorizer is a deterministic, stateless 768-dimensional `HashingVectorizer` using unigrams and bigrams, `alternate_sign=False`, and L2 normalization; nearest-neighbor ranking is cosine similarity via sparse dot products. The implementation and parameter semantics follow the [scikit-learn HashingVectorizer API documentation](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.HashingVectorizer.html).

| Metric | Local-hashing result |
|---|---:|
| 1-nearest-neighbor accuracy | 47.05% |
| Macro-F1 across the 36 test-supported clause categories | 33.91% |
| Recall@1 | 47.05% |
| Recall@5 (gold category appears among five nearest training clauses) | 69.45% |
| MRR@5 | 0.5605 |
| Contract-cluster bootstrap 95% CI, accuracy | [44.02%, 50.48%] |
| Contract-cluster bootstrap 95% CI, macro-F1 | [29.54%, 37.03%] |
| Runtime for the deterministic evaluation script | 7.782 s |

Confidence intervals use 1,000 test-contract bootstrap replicates (seed 42), rather than treating clauses from the same contract as independent. The full per-category support/results, input hashes and metric definitions are in `data/risk/results/local_hashing_cuad_retrieval_baseline.json`; reproduce with `python scripts/risk/evaluate_local_hashing_baseline.py`.

This is a **lexical-vector nearest-neighbor baseline**, not an LLM classification result or a pretrained semantic embedding model. It provides a reproducible offline point of comparison for the upload configuration, but the numbers are not directly equivalent to Phase 1's Cohere embedding plus SLM metrics. It does not measure the custom risk predicates, legal correctness, severity, or end-to-end risk sensitivity.

### 5.6 Comparison with Phase 1 repository experiments

The prior Phase 1 accepted paper, “Evidence-Grounded Contract Clause Classification with Small Language Models” (NLLP at EMNLP 2026), reports a separate 1,679-clause held-out CUAD category-classification evaluation: retrieval-conditioned SLM 66.41% accuracy / 51.72% macro-F1, zero-shot 35.80% / 31.41%, and random few-shot 50.98% / 40.93%. An earlier prompt/configuration variant reported 70.35% accuracy / 56.51% macro-F1 with top-5 Recall of 87% and MRR 0.7421; those results refer to a different experiment variant and are not merged into the principal row. These are Phase 1 category-classification results, not Phase 2 custom-risk metrics.

Small repository pilots should also remain visible but be treated as exploratory: fixed-10 classifier baseline 4/10 accuracy; hybrid retrieval pilot 5/10 accuracy and Recall@5 of 0.60; pure k-NN Top-1 5/10; and k-NN majority vote 6/10. These small experiments are not statistically generalizable. None of the Phase 1 results is numerically comparable with Phase 2 machine-silver decisions because the labels and target are different.

A separate older metadata-heavy retrieval artifact reports exact-match 0.0 and is not used as a Phase 2 baseline because its task definition is different. Repository comparison and caveats are regenerated in data/risk/results/phase2_reproducible_report.md.

## 6. Reproducibility and Artifacts

Key files:
- data/risk/commercial_clause_risk_playbook.json — source version 1.1.
- backend/data/legal_knowledge/risk_taxonomy.json — canonical risk domains.
- data/risk/silver/silver_queue.csv — fixed 300-task queue.
- data/risk/silver/silver_annotations_final_v5_qwen3_gemma3_20261007.csv — final silver CSV.
- data/risk/silver/silver_annotations_final_v5_qwen3_gemma3_20261007.jsonl — raw per-task outputs with both model records.
- data/risk/silver/silver_annotations_final_v5_summary.json — outcome counts and SHA-256.
- data/risk/EVALUATION_INTEGRITY_REPORT.json — twelve leakage/index checks.
- data/risk/results/phase2_reproducible_report.json and .md — generated evaluation summary and hashes.
- data/risk/evaluation/cross_document_v1/scenario_matrix.jsonl and manifest.json — 39 authored diagnostic scenarios with expected behavior, evidence anchors, and fixture hashes.
- data/risk/results/cross_document_scenario_audit.json/.md — explicit cross/document fixture integrity and coverage validation.
- data/risk/results/cross_document_model_scenarios.jsonl/.csv and _summary.json — current model outputs for the 39 synthetic scenarios; conformance is reported as a diagnostic, not accuracy.
- data/risk/results/cross_document_model_scenario_comparison.json/.md — one-shot versus batched ablation across the same 39 scenario IDs.
- data/risk/results/smoke_upload_api_current_20261009.json and smoke_test_audit_current.json/.md — pre-batching current-code upload, with six evidence/artifact gates.
- data/risk/results/smoke_upload_api_post_batching_20261009.json and smoke_test_audit_post_batching.json/.md — updated batching-engine TXT upload, source-hash verification, clause/cross/document results, trace, and six-gate audit.
- data/risk/results/local_hashing_cuad_index_manifest.json — 7,004-point train-only offline CUAD index build record.
- data/risk/results/local_hashing_index_manifest.json — validation hashes/counts for both local Qdrant collections.
- data/risk/results/legal_knowledge_retrieval_validation.json — representative local legal-guidance retrieval validation.
- data/risk/results/smoke_upload_api_result.json, `smoke_upload_api_pdf_result.json`, and `smoke_upload_api_fast_result.json` — three TXT/PDF upload responses and source hashes.
- data/risk/results/smoke_test_audit.json/.md, `smoke_test_audit_pdf.json/.md`, and `smoke_test_audit_fast.json/.md` — six-gate evidence/artifact audits for the three recorded runs.
- data/risk/results/local_hashing_cuad_retrieval_baseline.json — held-out CUAD nearest-neighbor accuracy, macro-F1, Recall@5/MRR@5 and cluster-bootstrap intervals.
- scripts/risk/evaluate_local_hashing_baseline.py — deterministic offline retrieval-baseline reproduction script.
- data/risk/team_export — exact playbook, taxonomy, registry, CSV exports and hash manifest.
- data/risk/demo_contract_for_reproduction.txt — synthetic demo agreement.
- data/runs/<analysis_id>/ — uploaded-contract artifacts and trace.
- backend/tests/test_contract_checks_evaluation.py — synthetic cross/document evidence tests.
- backend/tests/test_contract_risk_architecture.py — domain and aggregation tests.
- scripts/risk/report_phase2_experiment.py — rebuilds the reproducible report.
- scripts/risk/normalize_playbook_domains.py — checks/applies canonical playbook domains.
- scripts/risk/export_team_pack.py — regenerates the team export from source-of-truth files.

The run manifest stores the source SHA-256, pipeline settings, normalized playbook hash, calibration hash, code fingerprint, Python/platform and repository HEAD. Re-running the model is not promised to be bit-identical across model digests, runtime/library versions or accelerator conditions; the recorded outputs and hashes are the evidence for the completed run.

## Evaluation protocol without human gold

Because no custom-risk gold labels have been adjudicated, the implementation and reporting workaround is specified in [`docs/PHASE2_NO_GOLD_EVALUATION_PROTOCOL.md`](PHASE2_NO_GOLD_EVALUATION_PROTOCOL.md). It separates deterministic invariants, synthetic fixture conformance, proposed metamorphic tests, machine-judge diagnostics, machine-silver disagreement, and aligned external clause-classification benchmarks. None is presented as a substitute measurement of custom-risk accuracy.

## 7. Limitations and Threats to Validity

1. **Offline retrieval profile has different retrieval characteristics.** The verified server configuration uses local Ollama, local Qdrant and a 768-dimensional HashingVectorizer index for both training-clause retrieval and curated legal knowledge. This avoids sending clause/query text to Cohere in this profile, but its lexical-vector similarities are not equivalent to Cohere semantic embeddings. The Cohere profile remains supported separately, and its indexes must not be mixed with local-hashing vectors. Network independence does not imply correctness or confidentiality guarantees outside the local deployment boundary.

2. **No custom-risk human gold.** Agreement and exact evidence do not prove the interpretation is correct. The model may faithfully quote text but incorrectly characterize its business or legal effect.
3. **Custom playbook is unapproved policy guidance.** Domain, predicate and severity choices express a buyer-side review policy; they are not a source of law and are not human ground truth.
4. **Silver labels may be correlated.** Two LLMs can share failure modes; the blind verifier reduces direct anchoring but does not remove correlated errors.
5. **High abstention.** 192/300 cases remain UNCERTAIN. It would be misleading to hide these cases or compute ordinary accuracy by dropping them.
6. **Limited real-world interaction evaluation.** Synthetic tests verify quote-gating and routing behavior, but no expert-adjudicated cross-clause/document test set is available.
7. **Model and retrieval drift.** Embedding index contents, model variants, prompts, Ollama configuration and local GPU behavior can change outputs and throughput.
8. **Jurisdiction and contract type.** The current default perspective is buyer/customer-side. The system does not infer applicable law, and retrieved practice guidance must not be presented as binding authority.
9. **Pilot comparison size.** The Phase 1 fixed-10 results are illustrative diagnostics, not a reliable estimate of generalization or a baseline for custom risks.

## 8. Conclusion

We document an evidence-gated contract risk screening pipeline with locally served LLM inference, configurable retrieval with a validated local hashing-vector profile, CUAD clause classification, explicit risk predicates and contract-level interaction checks. The implementation contains reproducible data-isolation checks, canonical risk-domain routing, exact-quote validation, run manifests and machine-silver diagnostics. The current empirical evidence supports claims about pipeline behavior and reproducibility, not custom-risk accuracy. The required next empirical milestone is either independent expert adjudication of the 300-task queue or a clearly defined external task whose labels match the capability under evaluation. Until then, the correct contribution is a transparent system/artifact paper with strong evaluation caveats, not a claim of validated autonomous legal risk detection.

## References

- Koreeda, Y., and Manning, C. D. (2021). ContractNLI: A Dataset for Document-level Natural Language Inference for Contracts. Findings of EMNLP 2021. https://aclanthology.org/2021.findings-emnlp.164/
- Liu, S., Li, Z., Ma, R., Zhao, H., and Du, M. (2025). ContractEval: Benchmarking LLMs for Clause-Level Legal Risk Identification in Commercial Contracts. Proceedings of the Natural Legal Language Processing Workshop 2025. https://aclanthology.org/2025.nllp-1.19/
- The Atticus Project. Contract Understanding Atticus Dataset (CUAD). https://www.atticusprojectai.org/cuad/
- Wang, S. H., Zubkov, M., Fan, K., Harrell, S., Sun, Y., Chen, W., Plesner, A., and Wattenhofer, R. (2025). ACORD: An Expert-Annotated Retrieval Dataset for Legal Contract Drafting. ACL 2025. https://aclanthology.org/2025.acl-long.1206/
- scikit-learn developers. HashingVectorizer API documentation. https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.HashingVectorizer.html