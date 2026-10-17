# Phase 2 confidence and review-status policy

Version: prediction-correctness-confidence-v1

## Retired severity model

The legacy 0–20 severity score and HIGH/MEDIUM/LOW/CRITICAL labels are deprecated and are not emitted by the Phase 2 risk engine, cross-clause engine, contract aggregator, or user interface. Their thresholds were design choices, not empirically validated legal-risk cutoffs. Compatibility fields remain nullable and must not be interpreted.

## What the system reports instead

- **Finding status:** `POTENTIAL_RISK`, `NO_RISK`, or `INSUFFICIENT_EVIDENCE`.
- **Raw support signal:** a diagnostic in [0, 1] derived from evidence integrity, model agreement, and indicator matching. It is deliberately independent of YES/NO direction, is versioned as `support-score-v2-evidence-agreement-indicator`, and is uncalibrated—not a probability.
- **Confidence:** a calibrated probability only when a versioned calibration artifact is fitted from adjudicated reviewer labels, tied to the exact playbook/support-score versions, and passes the contract-disjoint locked-test gate.
- **Human review:** mandatory for positive findings from the unapproved playbook, unresolved evidence, incomplete citations, or jurisdiction-sensitive checks.

## Confidence target

The probability target is **prediction correctness**: whether the system's YES/NO decision matches the adjudicated reviewer label. It is not probability of loss, clause severity, enforceability, or probability that a contract is generally risky.

A model's self-reported confidence is never accepted. The calibrator is defined in `scripts/risk/fit_calibration.py`; runtime loading is fail-closed in `backend/app/core/risk/confidence_calibration.py`. No confidence probability is available until `data/risk/calibration/confidence_calibration.json` exists with status `VALIDATED_ON_LOCKED_TEST`, the current playbook hash, and the current support-score version.

The fitter requires two distinct annotator identities and a separate adjudicator, at least 300 calibration findings across 50 contracts, at least 30 correct and 30 incorrect calibration predictions, at least 100 locked-test findings across 25 different contracts, at least 15 correct and 15 incorrect test predictions, and no contract overlap. The constant-prevalence baseline is estimated from calibration labels only. Calibration must improve locked-test Brier score, the 95% contract-cluster-bootstrap interval for Brier improvement must exclude zero on the positive side, and 10-bin ECE must be <= 0.15. Runtime rechecks the audit metadata and metric gates; a status string alone is insufficient. These are project release guardrails, not universal scientific cutoffs or a guarantee of external validity.

## Contract-level confidence

Clause confidence values must not be averaged into a contract-level probability. Contract-level confidence remains null until a separately trained and tested contract-level model exists. The contract summary reports categorical review status only.

## Governance

The active rule policy remains `UNAPPROVED` and is run in `PILOT_REVIEW_ONLY` mode. Registry records, source metadata, and disabled contract-profile candidates are maintained in:
- `data/risk/rule_registry.jsonl`
- `data/risk/rule_registry_manifest.json`
- `data/risk/source_registry.json`
- `docs/PHASE2_RULE_REGISTRY_GOVERNANCE.md`

CI passing establishes implementation invariants and reproducibility only. It does not approve a rule or establish legal-risk accuracy.
