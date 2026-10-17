# Phase 2 Contract Risk Review — Rule-First Logical Model

## Purpose

The risk service answers a different question from the clause classifier. It looks for buyer-side contract provisions that satisfy explicit review rules and asks the playbook questions that need more nuanced interpretation. Its evidence source is the contract the user uploaded.

There is no fine-tuning step in this risk pipeline. Retrieved CUAD clause examples are not inserted into risk prompts, are not evidence for risks, and do not create risk flags. CUAD retrieval remains a separate clause-category classification component only.

## End-to-end flow

1. Accept and extract the uploaded PDF/TXT contract.
2. Segment the document into clauses while preserving clause IDs and source text.
3. Run the separate clause-category classifier. Its label can organize the interface and route category-specific checklist questions, but it cannot gate the deterministic rule scan.
4. Run every executable deterministic rule in the versioned playbook against every extracted clause, independently of the predicted clause category.
5. Run applicable playbook questions for nuanced clause risks. For these questions, the LLM sees the current clause, related clauses from the same uploaded contract, the relevant question, the playbook's flag conditions, and optional legal-practice guidance. It does not see retrieved CUAD training text spans.
6. Run the ten cross-clause checks and three document-level checks against the uploaded document's clauses and explicit playbook questions.
7. Verify that each positive finding's cited text is an exact contiguous quote from the uploaded contract, and identify the source clause.
8. Aggregate the surviving findings by declared playbook domain, apply deterministic review-triage scoring, write the report/artifacts, and preserve configuration and playbook fingerprints.

## Root-cause fix

The previous architecture allowed two sources to be confused with contract evidence: retrieved CUAD examples in the legacy risk prompt, and the predicted CUAD label as the gate to risk indicators. The current design removes both connections.

- The legacy risk prompt no longer accepts or renders CUAD examples or candidate labels.
- The text-indicator scanner checks all rule families for every clause, regardless of the classifier label.
- The active Phase 2 risk engine runs the playbook's deterministic predicates independently of the LLM's answer to checklist questions. A matching rule is preserved as a separate review finding.
- Every deterministic finding records its rule ID, pattern, playbook hash, rule-engine version, risk domain and exact quote.
- Resume logic checks both the rule-engine version and normalized playbook hash, so changing a playbook rule invalidates stale findings and triggers re-analysis.

## Playbook and taxonomy

Source of truth: data/risk/commercial_clause_risk_playbook.json, version 1.2.

The playbook includes:
- 37 clause-category question checklists with 101 clause-level questions;
- 7 initial executable text predicates for explicit wording patterns;
- 10 cross-clause questions;
- 3 document-level questions;
- cited source records and declared flag conditions.

The taxonomy in backend/data/legal_knowledge/risk_taxonomy.json provides ten canonical domains and mitigation guidance. A taxonomy term or a question definition can organize a review but is not evidence that the uploaded contract contains a risk.

The seven deterministic rules currently cover explicit uncapped-liability wording, indemnification outside a cap, liquidated damages outside a cap, immediate/no-notice termination, broad IP-license wording, early-exit remaining-term fees, and absolute assignment prohibition. This is a deliberately explicit starter rule set, not an exhaustive list of every possible adverse clause. Rule matches are review triggers, not legal conclusions.

## Status semantics

- POTENTIAL_RISK: an executable rule matched or a playbook question returned a positive result with valid uploaded-contract evidence.
- NO_RISK: the applicable playbook question was answered as not meeting its flag condition, with evidence supporting that answer.
- INSUFFICIENT_EVIDENCE: the text needed to decide the question is absent, ambiguous, or not supported by exact contract evidence.
- ERROR: execution or output validation failed.

No deterministic pattern match does not imply NO_RISK. It only means no rule in the current explicit set matched that text. Nuanced risks continue to be handled by playbook questions, and unresolved checks remain visible.

## Evaluation contract

The release is assessed against reproducible system invariants, not against a risk-span dataset:
- deterministic rule IDs are unique and regexes compile;
- every rule maps to a canonical taxonomy domain;
- deterministic positives carry exact quotes from the uploaded contract;
- prompts do not inject retrieved CUAD example spans;
- playbook question output obeys the source-evidence boundary;
- cross-clause/document checks cite existing clause IDs and exact quotes;
- the separate CUAD category index has zero train/test contract overlap;
- the synthetic playbook-question regression suite and backend unit tests pass.

These measurements establish implementation and rule conformance, not legal correctness or real-world recall. The system does not report risk accuracy, precision, recall, F1, calibrated probability, or enforceability. These are not release gates and no annotation queue is required to operate or release the risk engine.

## Commands

From the repository root, with the backend stopped before accessing embedded Qdrant:

    .venv/bin/python scripts/risk/validate_playbook_rules.py
    .venv/bin/python scripts/risk/validate_evaluation_integrity.py
    .venv/bin/python scripts/risk/normalize_playbook_domains.py
    .venv/bin/python scripts/risk/audit_cross_document_scenario_suite.py
    PYTHONPATH="$PWD:$PWD/backend:$PWD/.venv/lib/python3.12/site-packages" .venv/bin/python -m pytest -q backend/tests
    .venv/bin/python scripts/risk/report_phase2_experiment.py

Then run scripts/risk/run_release_checks.py and verify that every check reports PASS. Embedded/local Qdrant uses an exclusive file lock, so the API service must be stopped during the index-isolation check and restarted afterward.

## Operational boundary

This is an AI-assisted commercial contract review-prioritization tool, not a legal decision-maker. Every displayed positive finding must show the source clause and exact quote. Severity is a deterministic triage signal, not a probability of loss. Legal/practice guidance remains explanatory context and never substitutes for the text of the uploaded agreement.
