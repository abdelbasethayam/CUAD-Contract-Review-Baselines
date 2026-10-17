# Team Export — Commercial Contract Risk Playbook

Source-of-truth playbook version: 1.2.

## Contents

- risk_clause_checks.csv — 101 clause-level playbook questions.
- risk_cross_clause_checks.csv — 10 cross-clause questions.
- risk_document_checks.csv — 3 document-level questions.
- risk_deterministic_rules.csv — 7 executable textual review predicates, patterns, and exclusions.
- risk_playbook_exact.json — the source playbook, including executable rules.
- risk_taxonomy.json — canonical risk domains and contextual guidance.
- source_registry.json — legal/practice source metadata.
- export_manifest.json — source hashes and validation counts.

## Risk-domain policy

Every question and deterministic rule maps to one of the ten canonical domains in risk_taxonomy.json. The explicit playbook domain controls routing and aggregation. Taxonomy keywords do not override a declared domain.

## Evidence and evaluation boundary

A playbook rule or taxonomy description is not contract evidence. Positive findings must cite exact text from the uploaded agreement. Deterministic rules are applied to each extracted clause independently of its predicted CUAD category. CUAD retrieval remains confined to the separate clause-category classifier; retrieved training examples do not enter the risk prompt or serve as risk evidence.

Release acceptance validates rule definitions, taxonomy mapping, quote provenance, classifier-index isolation, authored regression fixtures, smoke tests and unit tests. These are rule/system-conformance checks, not measurements of legal-risk accuracy or enforceability.
