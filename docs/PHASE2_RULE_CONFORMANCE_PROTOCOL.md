# Phase 2 Evaluation Protocol — Playbook-Rule Conformance

## Evaluation target

The supported system claim is contract-review prioritization based on explicit playbook predicates and questions with exact uploaded-contract evidence. The evaluation contract checks implementation behavior and provenance. It does not attempt to estimate legal-risk accuracy.

## What is measured in release

1. Deterministic rule configuration: unique rule IDs, valid regex/exclusion patterns, required reviewer-facing fields, and canonical taxonomy mapping.
2. Source evidence integrity: deterministic matches are exact substrings of the uploaded clause; positive LLM/question findings quote current-contract text or an identified related clause.
3. Prompt separation: the risk prompts contain no retrieved CUAD training example spans. CUAD retrieval is confined to the separate clause-category classifier.
4. Classification data isolation: training and test contracts are disjoint, and classification index payloads contain training contracts only.
5. Playbook question behavior: authored positive, protected-control, and incomplete-context fixture scenarios exercise each cross-clause and document-level question.
6. Robustness: malformed outputs fail closed; unresolved checks remain explicit instead of silently becoming no-risk.
7. Operational reliability: TXT/PDF smoke tests, API validation and backend unit tests.

## Rule test construction

Each deterministic rule should have, where applicable:
- a positive clause that contains the configured pattern;
- a protected control that expresses the opposite condition or an explicit exception;
- a near-miss with a related keyword but no rule predicate;
- a label-independence assertion showing that a clause still triggers the rule when its predicted CUAD category is wrong or unknown;
- an assertion that the emitted quote is an exact substring of the supplied clause.

For complex checklists, the 39 authored cross-clause/document fixtures are categorized as risk-stressed positive, protected-control, and incomplete-context scenarios. Their status matches measure regression behavior only. They do not stand for a population of real contracts.

## Metrics and interpretation

Report:
- rule configuration checks passed / total;
- direct positive rule matches and exact quote integrity;
- taxonomy-domain coverage;
- classification-index isolation checks passed / total;
- synthetic scenario status matches, clearly labeled as fixture conformance;
- backend test count and upload-smoke outcomes.

Do not call these outputs legal-risk accuracy. Exact substring validation proves the quote exists, not that the risk interpretation is semantically or legally correct. A missing rule match does not establish no risk. The seven initial deterministic predicates intentionally cover specific wording patterns and are not exhaustive.

## Release command

Run from the repository root. Stop the backend first because embedded Qdrant uses an exclusive storage lock.

    .venv/bin/python scripts/risk/run_release_checks.py

The release suite invokes scripts/risk/validate_playbook_rules.py and scripts/risk/validate_evaluation_integrity.py, then playbook-domain, synthetic-fixture, upload-smoke, retrieval-classification baseline, report-generation, and backend-test checks. Restart the backend after completion and check GET /health.

No risk-span annotation queue or fine-tuning dataset is part of risk flagging or the release/report dependencies.
