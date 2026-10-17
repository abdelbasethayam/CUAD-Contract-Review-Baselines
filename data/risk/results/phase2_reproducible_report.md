# Phase 2 Playbook-Rule Conformance Report

**Status: NOT RUN**

This is a placeholder after changing the evaluation protocol. It deliberately does not reuse older annotation-based metrics.

Run scripts/risk/run_release_checks.py with the backend stopped so the local Qdrant index validator can acquire its file lock. The command runs the playbook rule validator, the classification-index isolation validator, regression fixtures, upload smoke checks, category-classification baseline and backend tests, then rebuilds this report.

Configured scope:
- 37 clause-category question checklists with 101 clause-level questions
- 10 cross-clause checks and 3 document-level checks
- 7 initial deterministic playbook predicates
- 10 taxonomy domains
- exact source-quote integrity and classifier train/test index isolation

No custom risk-span annotation dataset is read or required. Release metrics are implementation/rule conformance checks, not legal-risk accuracy.
