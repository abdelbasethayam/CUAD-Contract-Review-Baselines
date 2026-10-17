# Risk finding adjudication dataset

This folder contains a schema/template, not pre-filled ground truth. Do not populate labels by copying model outputs or synthetic scenarios.

## Workflow
1. Freeze the playbook, model, prompt, support-score version, and contract-disjoint train/calibration/test split.
2. Two qualified reviewers independently label each prediction against the contract and the declared review policy.
3. An adjudicator resolves disagreements; only rows with `adjudication_status=ADJUDICATED` are used.
4. Keep every contract entirely within one split. Do not move test contracts into calibration after inspecting test results.
5. Populate `risk_finding_adjudication_template.csv` with adjudicated rows, preserving contract and playbook IDs.
6. Copy the completed file to `risk_finding_adjudication.csv`, then run `python scripts/risk/fit_calibration.py`.

## Confidence definition
The calibrated probability estimates whether the system's predicted YES/NO decision matches the adjudicated reviewer label. It is not risk severity, probability of loss, or legal correctness in any jurisdiction.

The fitter refuses to create an artifact unless calibration and locked-test partitions meet the minimum sample, class-balance, and contract-disjoint gates and the calibrated Brier score beats a constant-prevalence baseline with ECE <= 0.15. These are conservative operational gates, not a guarantee of external validity.
