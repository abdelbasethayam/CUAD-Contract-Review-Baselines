# Human gold protocol

The purpose of this set is to estimate how well the playbook/model identifies contract risk for the project customer/buyer review perspective.

## Unit of annotation

Annotate one (contract_id, clause_index, check_id) at a time.

Each annotator independently records annotator_1_* or annotator_2_*: risk (YES/NO), risk type, severity (INFORMATIONAL/LOW/MEDIUM/HIGH/CRITICAL where applicable), exact evidence, and notes. The adjudicated_* fields are reserved for the final adjudicator decision.

## Blindness

Annotators must not see the model probability/confidence or prediction before independent labeling.

For rigorous evaluation, partition the annotation sample into calibration, development/ablation, and locked gold test subsets. The locked gold test subset must not tune prompts, retrieval, thresholds, or calibration.

## Agreement

Use Cohen kappa for two annotators. For more than two, use Krippendorff alpha (nominal for binary risk; ordinal for severity). Preserve raw labels and the adjudicated result.

## Evidence rule

An evidence quote is valid only when it is an exact contiguous substring of supplied contract text. Paraphrases belong in notes.

## Calibration

The calibration script requires at least 30 adjudicated examples as a minimum guardrail. A larger stratified sample is recommended for reliable calibration, especially across rare risk types and severity levels.

## Perspective

The current playbook is customer_buyer. Do not mix perspectives in one calibration curve.
