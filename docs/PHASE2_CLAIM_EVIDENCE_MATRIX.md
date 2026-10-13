# Phase 2 — Claim-to-Evidence Matrix (Rule-First Release)

This matrix ties each permitted claim to a reproducible artifact. It deliberately treats this project as a playbook-driven review-prioritization system; it does not derive risk results from retrieved clause examples or report legal-risk accuracy.

| Claim | Evidence artifact | How to reproduce | Permitted interpretation | Not supported |
|---|---|---|---|---|
| Risk screening is playbook-rule first | data/risk/commercial_clause_risk_playbook.json; backend/app/core/risk/deterministic_rules.py; backend/app/core/risk/risk_engine.py | scripts/risk/validate_playbook_rules.py | Seven explicit predicates scan uploaded clause text independent of the predicted clause label | Exhaustive detection of all legal/commercial risks |
| CUAD example spans are not injected into risk prompts | backend/app/core/risk/risk_detector.py; backend/app/core/risk/risk_engine.py | rule validator; unit tests | The risk prompt uses the uploaded contract and playbook questions, not retrieved CUAD training example text | Claim that the separate classifier does not use CUAD category training data |
| Positive direct rule match has source-grounded evidence | backend/app/core/risk/deterministic_rules.py; backend/tests/test_deterministic_playbook_rules.py | backend test suite | The returned quote is an exact match from the uploaded clause | That an exact quote makes the legal interpretation correct |
| Rule definitions are reproducible and versioned | Playbook hash and rule_engine_version in each finding provenance | Run a contract, then inspect data/runs/<analysis_id>/risk_findings.jsonl | Findings record which rule version and playbook version produced the review trigger | Calibrated confidence or risk probability |
| Playbook coverage is explicit | commercial_clause_risk_playbook.json and risk_taxonomy.json | scripts/risk/validate_playbook_rules.py; scripts/risk/normalize_playbook_domains.py | Clause questions, cross-clause/document checks and deterministic predicates are declared in versioned files | Empirical validation of every question's legal meaning |
| Classifier training/test separation is preserved | data/risk/EVALUATION_INTEGRITY_REPORT.json | scripts/risk/validate_evaluation_integrity.py | Category-classification index payloads are checked for training-only contracts and no test overlap | Risk-detection accuracy |
| Cross-clause/document questions enforce exact evidence | backend/app/core/risk/contract_checks.py and synthetic scenario artifacts | scripts/risk/audit_cross_document_scenario_suite.py; backend tests | Fixture coverage, quote validation and regression behavior can be reproduced | Real-world sensitivity, legal correctness or generalization |
| Release acceptance is independent of risk-span annotation datasets | scripts/risk/run_release_checks.py; scripts/risk/report_phase2_experiment.py | scripts/risk/run_release_checks.py | Rule/schema/domain checks, classifier index isolation, regression tests and upload smoke tests determine release status | A claim that the system has achieved measured legal-risk accuracy |
| CUAD clause-category metrics remain a separate task | data/risk/results/local_hashing_cuad_retrieval_baseline.json | scripts/risk/evaluate_local_hashing_baseline.py | A lexical retrieval baseline is reported for clause-category prediction only | Risk detection, enforceability or severity performance |

## Forbidden claims

Do not say “the system has X% legal-risk accuracy,” “the score is the probability of loss,” or “the contract is legally safe.” The current release evidence establishes software/rule conformance and evidence provenance only. An absent rule match means the current predicate set did not match; it does not prove that a contract has no risk.

## Release status

The acceptance contract is automated rule validation, canonical taxonomy mapping, exact-quote source integrity, separation of the classification index from its held-out test contracts, playbook-question regression tests, backend tests and upload-smoke tests. No human risk annotation queue is part of these gates.
