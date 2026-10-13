# Phase 2 Risk Evaluation Protocol — Rule-First

The current target is explicit playbook-rule and question conformance over uploaded contract text. The playbook provides the review predicates; the contract supplies the evidence. This is a review-prioritization system, not a legal determination.

## Release acceptance
- deterministic rule IDs are unique and every configured regex compiles;
- rules provide a risk domain, question/risk type and reviewer-facing explanation;
- every rule domain exists in the canonical taxonomy;
- direct rule positives return an exact quote from the uploaded clause;
- the risk prompt path contains no retrieved CUAD training example spans;
- question-based positives are checked against exact current-contract evidence;
- cross-clause/document outputs cite existing clause IDs and quote exact text from those clauses;
- the separate CUAD classification index contains training contracts only and has no train/test overlap;
- synthetic playbook-question regressions, API smoke tests and backend tests pass.

## Interpretation
The report uses implementation invariants, deterministic rule tests, synthetic fixture conformance and evidence-provenance checks. These metrics are not a legal-risk accuracy estimate and should not be described as precision, recall, F1, legal correctness, enforceability or calibrated loss probability. A rule miss is not a statement that a contract is safe.

## Reproduction
From the repository root, stop the API backend before checking the embedded Qdrant index and run:

    .venv/bin/python scripts/risk/run_release_checks.py

The script writes data/risk/results/release_validation.json and .md and the playbook-rule report under data/risk/results/. Restart the API afterward.
