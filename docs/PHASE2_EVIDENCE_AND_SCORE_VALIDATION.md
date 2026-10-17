# Phase 2 Evidence and Score Validation Contract

## Purpose and limits

Phase 2 is a contract-review prioritization assistant. Its output is not a legal opinion, an enforceability determination, or a probability of loss. The current repository has playbook-conformance tests and synthetic regression tests, but it does not yet have a lawyer-adjudicated, contract-disjoint risk benchmark. Therefore, real-world precision, recall, severity agreement, and calibration are **not established**.

## Evidence requirements

Every positive clause-level finding must cite an exact contiguous quote from either the target clause or a related clause in the same uploaded contract. The output must retain the source clause identity. A quote that occurs in multiple related clauses is ambiguous and must not be presented as verified evidence for one clause.

For cross-clause and document-level findings:

- Each evidence record must identify an existing clause ID and an exact quote from that clause.
- The set of evidence clause IDs must equal the finding's declared affected clause IDs. If any declared clause lacks evidence, or any evidence clause is not declared, the finding must abstain as `INSUFFICIENT_EVIDENCE`.
- A duplicate check ID in one model response is ambiguous and is not an extra vote.
- Missing, invalid, or failed model passes count as abstentions. They must never be silently converted into `NO_RISK`.
- Playbook citations support the review rationale; they are not evidence that the uploaded contract contains the quoted wording.

## Score semantics

The current 0–20 score is a **heuristic review-triage score**, based on four model-supplied 0–5 dimensions and explicit modifiers. The dimensions are not statistically estimated probabilities and have not been calibrated to legal outcomes. The model-supplied components must be marked as unvalidated.

- `confidence` remains null and `confidence_status` remains `UNCALIBRATED` until a separate calibration study is completed.
- A normalized severity signal such as score divided by 20 is not a probability.
- If any positive finding lacks a complete scoring basis, the contract-level severity and aggregate score must be withheld; use `overall_risk=UNSCORED` and `severity_status=INCOMPLETE`, while retaining the individual evidence-supported findings.
- Deterministic playbook matches without an adjudicated severity weight are review triggers. They must not be assigned a fabricated numeric severity.

## Risk-check retrieval and resumability

The predicted CUAD label remains a retrieval signal, not a hard gate. Phase 2 also selects additional checklist families when explicit, risk-specific playbook keywords occur in the clause text. This reduces dependence on one possibly incorrect classifier label; it is still a heuristic retrieval method, not proof of complete risk coverage. Contract-wide candidate checks likewise combine predicted labels with direct clause wording.

A saved checkpoint is reusable only when its playbook hash, rule-engine version, expected check IDs, and model-pass completeness are current. Missing or invalid model passes are recorded as incomplete and retried on resume. They are not treated as negative answers. Run identity also includes the code fingerprint and material generation/retrieval settings.

## Scientific evaluation required before accuracy claims

Build a frozen, contract-disjoint evaluation set. Each case should be independently reviewed by qualified contract reviewers against a versioned review policy, with disagreements adjudicated. Keep the held-out test contracts separate from prompt/rule tuning.

Report at minimum:

1. Finding-level precision, recall, and F1 for each risk domain/check family, with denominators and sample sizes.
2. Evidence quote exact-match rate and evidence-source clause-ID accuracy.
3. Cross-clause finding precision/recall and complete-source-evidence rate.
4. Abstention/unresolved rate and the rate of unsupported positive findings.
5. Severity coverage and ordinal agreement (for example, weighted kappa) against adjudicated severity labels.
6. Calibration metrics only if the system eventually emits probabilities and the dataset is large enough for a meaningful calibration study.

Publish the dataset version, adjudication protocol, test split, model identifier, prompt/playbook hash, code fingerprint, and score version with each report. Do not report synthetic rule-conformance results as legal-risk accuracy.

## Release gate

A Phase 2 release requires passing backend and frontend CI, exact-evidence regression tests, duplicate-response and model-failure tests, and a reproducible run manifest. Accuracy or calibration claims additionally require a completed adjudicated benchmark. Human review remains required for material, ambiguous, unresolved, or jurisdiction-sensitive findings.
