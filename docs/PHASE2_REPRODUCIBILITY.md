# Phase 2 Reproducibility and Operator Guide — Rule-First Edition

This guide defines the current supported risk-screening path. The release/report scripts validate the playbook rules, evidence constraints, taxonomy mapping, classifier-index isolation and regression tests. They do not require or read a custom-risk span-label dataset.

## Environment

- Python 3.12 and the repository virtual environment.
- Node/npm if using the React frontend.
- Ollama with the model configured by the server, when the playbook question stage is enabled.
- A supported embedding profile for the separate classifier and optional same-contract context retrieval. The local hashing profile supports network-independent lexical retrieval; it is not a pretrained semantic embedding model.
- The source playbook is data/risk/commercial_clause_risk_playbook.json. Its current executable deterministic rules are under deterministic_rules.

The CUAD clause-category classifier remains a separate component. It may retrieve training-only category examples to help label clauses, but those example spans are never sent to the risk prompt or accepted as evidence for a risk.

## Risk analysis path

For every extracted clause:
1. Preserve exact source text and clause index.
2. Apply all deterministic playbook rules independently of the predicted clause label.
3. Store every matching rule as a separate POTENTIAL_RISK review trigger with rule ID, exact contract quote, taxonomy domain, playbook hash and rule-engine version.
4. Ask the relevant playbook checklist questions, following flag_if and do_not_flag_if. These questions may use current-clause text, related clauses from the same uploaded contract and optional legal-practice guidance.
5. Require exact contiguous uploaded-contract evidence for each model-positive answer. If validation fails, abstain instead of presenting the finding as a supported positive.
6. Run cross-clause/document playbook questions, validate cited clause IDs and exact quotes, and keep unresolved checks explicit.
7. Aggregate only validated findings and generate a structured risk register, evidence trail, and run manifest.

A rule match is a review trigger, not a legal conclusion. Absence of a deterministic match is not evidence of no risk; the question stage and unresolved statuses remain important.

## Run the release checks

Run from the repository root. Because the embedded local Qdrant profile enforces an exclusive file lock, stop the backend before invoking the full checks. Restart the backend after the command completes.

    .venv/bin/python scripts/risk/run_release_checks.py

The release suite runs:
- Python compile checks;
- playbook-rule validation (unique IDs, valid regex, required rule fields, canonical taxonomy mapping and no example-span injection);
- classifier train/test split and Qdrant payload isolation checks;
- playbook-domain validation and the team export;
- cross-clause/document synthetic regression fixture audit and model regression run;
- recorded TXT/PDF upload-smoke audits;
- the separate CUAD category retrieval baseline;
- the Phase 2 playbook-rule conformance report;
- the full backend unit tests.

It writes data/risk/results/release_validation.json and .md. The report should contain no annotation-queue checks. It intentionally describes rule/pipeline conformance, not legal-risk accuracy.

For focused checks:

    .venv/bin/python scripts/risk/validate_playbook_rules.py
    .venv/bin/python scripts/risk/validate_evaluation_integrity.py
    .venv/bin/python scripts/risk/normalize_playbook_domains.py
    .venv/bin/python scripts/risk/audit_cross_document_scenario_suite.py
    PYTHONPATH="$PWD:$PWD/backend:$PWD/.venv/lib/python3.12/site-packages" .venv/bin/python -m pytest -q backend/tests

## How the report is measured

The saved Phase 2 report summarizes:
- deterministic rule count and regex integrity;
- unique playbook rule IDs and presence of explicit questions/explanations;
- taxonomy-domain coverage;
- playbook question coverage: clause-level, cross-clause and document-level;
- training/test contract isolation for the independent clause-category retrieval index;
- exact quote checks, synthetic question regression fixtures and backend test outcomes.

The report deliberately does not compute risk precision, recall, F1, calibration, probability of loss, enforceability, or legal correctness. The acceptance criteria are implementation invariants and rule/question conformance. The report and the operational risk path work without external or local risk-span annotation datasets.

## Playbook maintenance

To add a rule, edit the deterministic_rules array in data/risk/commercial_clause_risk_playbook.json. Each rule must have:
- a stable unique ID;
- a canonical risk_domain from backend/data/legal_knowledge/risk_taxonomy.json;
- a short risk_type and reviewer-facing question;
- a regex pattern and, where needed, exclusion patterns;
- an explanation stating what should be reviewed;
- source IDs from the playbook's source registry where relevant.

Then run the rule validator, add positive and protected-control test cases, run the backend suite and full release checks. Reviewers should inspect each new rule's exact match strings and false-trigger cases. Do not add retrieved clause examples or training-span snippets to the rule definition or risk prompt.

If a rule or question changes, the normalized playbook hash changes. Resume logic detects the mismatch and re-analyzes the affected clause results rather than silently retaining stale findings.

## Privacy and legal boundary

The LLM generation stage runs through local Ollama. The active embedding profile determines whether embedding requests use a local hashing vectorizer or an external service; verify the actual runtime configuration before uploading confidential contracts. The application is a review-prioritization aid, not legal advice. Each finding should show the contract quote and reviewer-facing rationale; severity signals must not be represented as calibrated probability.
