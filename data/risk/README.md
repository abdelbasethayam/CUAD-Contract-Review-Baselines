# Phase 2 risk data

## Risk playbook and governed registry

The runnable baseline playbook is `data/risk/commercial_clause_risk_playbook.json`. It covers 37 clause-risk targets: the 36 substantive CUAD v1 categories after excluding five metadata fields, plus supplemental indemnification.

The baseline contains 101 clause checks, 10 cross-clause checks, 3 document checks, and 7 deterministic text rules (121 base rules). The governed registry contains 1,936 **disabled context-specific applicability candidates** and 2,057 total records. The 1,936 candidates are not 1,936 new approved legal rules: they are review hypotheses that inherit their base rule and must not execute until applicability, sources, exceptions, regression tests, and approval are complete.

Run from the repository root:

```bash
python scripts/risk/build_rule_registry.py --check
python scripts/risk/validate_rule_registry.py
```

To regenerate after an authorized playbook edit:

```bash
python scripts/risk/build_rule_registry.py --write
```

The registry is fingerprinted to the exact Git blob of the playbook. Runtime fails closed if the registry is missing, stale, or structurally inconsistent. The current policy remains `UNAPPROVED` and `PILOT_REVIEW_ONLY`; CI does not constitute legal approval.

## Legal guidance knowledge base

The local legal-knowledge files are stored under `backend/data/legal_knowledge/` and are ingested into a separate Qdrant collection so guidance is not mixed with CUAD examples.

```bash
python -m backend.app.core.legal_knowledge.ingest
```

This requires a configured `COHERE_API_KEY`. Existing `data/qdrant_local` may contain a prebuilt `legal_knowledge` collection; ingest only when absent, stale, or intentionally replaced.

## Independent risk adjudication

There is no prefilled project-specific risk gold set. The committed `data/risk/gold/risk_finding_adjudication_template.csv` is an empty schema template, not ground truth. Do not fill it by copying model outputs or synthetic scenarios.

1. Freeze playbook, model, prompt, score version, and contract-disjoint split.
2. Two qualified reviewers independently label each system YES/NO prediction and its evidence.
3. An adjudicator resolves disagreement and records an adjudicator identity.
4. Keep each contract wholly in either `calibration` or `test`; never tune on the locked test set.
5. Populate the template and save the completed file as `data/risk/gold/risk_finding_adjudication.csv`.
6. Run:

```bash
python scripts/risk/fit_calibration.py --csv data/risk/gold/risk_finding_adjudication.csv
```

The fitter refuses to create a confidence artifact unless sample, class-balance, split-isolation, and locked-test metric gates pass. Confidence means probability that the predicted YES/NO finding matches the adjudicated label; it is not risk severity, loss probability, or enforceability.

## External benchmarks

See `data/risk/external_benchmarks.json` for task-specific links and permitted uses. CUAD assesses clause presence/spans; ContractNLI assesses document-level entailment and evidence; ACORD assesses retrieval relevance; MAUD is M&A-specific; ContractEval is the closest published risk-span comparator; LegalBench is a collection of heterogeneous legal-reasoning tasks. None alone validates this repository's buyer-side risk policy.

The final risk-accuracy and confidence claims require a project-specific, contract-disjoint, dual-annotator and adjudicated benchmark. Synthetic fixtures are for regression and adversarial robustness only.
