# Phase 2 Risk Evaluation Protocol — Rule-First

The current target is evidence-grounded review prioritization over uploaded contract text. The playbook supplies a review predicate; the uploaded contract supplies the evidence. This is not a legal determination.

## Release acceptance

- deterministic rule IDs are unique and configured regexes compile;
- the governed rule registry reproduces exactly from the committed playbook fingerprint;
- every base rule has a structured decision/evidence contract, source references, jurisdiction status, validation status, confidence policy, and regression-case slots;
- context-specific candidates remain disabled until applicability review and approval;
- all source records expose explicit citation, pinpoint, jurisdiction, effective-date, retrieval-date, and license fields; unknown values remain null with a reason and cannot be treated as verified authority;
- no unapproved rule can produce a legal conclusion;
- direct rule positives return exact quotes from uploaded contract text;
- question-based positives are checked against exact current-contract evidence;
- cross-clause/document findings cite existing clause IDs and exact quotes from those clauses;
- no ordinal severity labels or unsupported aggregate contract confidence are emitted;
- raw support scores are labelled uncalibrated and are not presented as probabilities;
- numerical confidence is emitted only from a versioned calibrator that matches the current playbook and score versions and passes contract-disjoint calibration/locked-test gates;
- CUAD classification indexes and other external benchmark data remain task-isolated and are not treated as risk ground truth;
- synthetic regression tests, API smoke tests, backend tests, frontend build, and registry validation pass.

## External benchmark mapping

Use each dataset only for its labeled task:
- CUAD: clause-category presence and span extraction.
- ContractNLI: document-level entailment/contradiction/not-mentioned and evidence spans.
- ACORD: query-to-clause relevance/retrieval ranking.
- MAUD: M&A deal-point extraction.
- ContractEval: secondary comparison for legal-risk span identification.
- LegalBench: only individual tasks that map to an explicit rule reasoning primitive.

None is a complete gold standard for the repository's buyer-side policy. Report their results separately.

## Project-specific adjudication

The project-specific risk benchmark must be frozen and contract-disjoint. Two qualified reviewers label each finding independently; an adjudicator resolves disagreement. Report finding precision/recall/F1 by rule family, evidence quote exact-match and source-clause-ID accuracy, cross-clause precision/recall, unsupported-positive rate, unresolved rate, and calibration metrics for prediction correctness. Publish the dataset version, annotation protocol, split, jurisdiction, contract type, playbook hash, model, prompt, score version, and code fingerprint.

## Interpretation

Registry checks, deterministic conformance tests, synthetic mutation tests, and evidence-provenance tests are software/policy conformance measures. They are not legal-risk accuracy, enforceability, severity agreement, or calibrated loss probability.

## Reproduction

From the repository root, stop the API backend before checking the embedded Qdrant index and run:

```bash
.venv/bin/python scripts/risk/run_release_checks.py
```

The script writes the release-validation report under `data/risk/results/`. Restart the API afterward.
