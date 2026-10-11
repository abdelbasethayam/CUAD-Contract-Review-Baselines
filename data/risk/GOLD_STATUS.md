# Phase 2 Gold / Evaluation Status

## Human gold — pending annotation

- Queue: `data/risk/gold/gold_annotations.csv`
- Tasks: 300 total — 150 locked-test, 75 calibration, 75 development.
- Queue source: training contracts only.
- Current annotation state: **0/300 tasks have human risk labels or evidence filled in**.
- Required next step: independent expert annotation, disagreement adjudication, then fit/use calibration only on the calibration partition. Do not tune against locked test.

## Machine-adjudicated silver — complete

- Final CSV: `data/risk/silver/silver_annotations_final_v5_qwen3_gemma3_20261007.csv`
- Final JSONL: `data/risk/silver/silver_annotations_final_v5_qwen3_gemma3_20261007.jsonl`
- Summary: `data/risk/silver/silver_annotations_final_v5_summary.json`
- 300 tasks, 72 documents, 95 unique checks.
- Partitions: locked_test=150, calibration=75, development=75.
- Machine statuses: disagreement=165, agreed=108, agreed-uncertain=22, agreed-but-evidence-invalid=5.
- Final decision counts: UNCERTAIN=192, NO=95, YES=13.
- Positive labels with empty evidence: 0.
- CSV SHA-256: `12c618b4617225b9462616edaa553af23c7ac6b2a2e9527e6c0840e9b7d9230f`.

This is a diagnostic silver set, **not human gold**, not expert-adjudicated accuracy, and not evidence that the custom risk predicates are legally correct. The locked partition was excluded from tuning.

## External expert benchmark

- `data/risk/external/cuad_expert_test.jsonl`: 3,420 contract/category tasks, 95 mapped held-out contracts, 36 CUAD substantive categories.
- `data/risk/external/cuad_test_presence_gold.csv`: secondary clause-presence artifact.
- These support CUAD clause/evidence validation only. They are not ground truth for the custom buyer-side risk predicates or severity.

## Integrity

- Train split: 410 contracts / 10,545 clause rows.
- Test split: 100 contracts / 2,556 clause rows.
- Train/test contract overlap: 0.
- All 12 checks in `data/risk/EVALUATION_INTEGRITY_REPORT.json` pass.
- Playbook source version: 1.1. All 101 clause checks, 10 cross-clause checks, and 3 document-level checks map to one of the canonical 10 risk domains.
- No risk-specific fine-tuning has been performed.

## Evaluation limitation

Without qualified human adjudication for the custom 37-target risk taxonomy, the project cannot honestly report human-gold accuracy for that taxonomy. Model disagreement rate is a workflow diagnostic, not accuracy.


## Cross-clause/document model diagnostic (2026-10-09)

- Scenario matrix: 39 authored synthetic cases; 10 cross-clause checks + 3 document-level checks, each with positive, protected-control, and incomplete-context stimuli.
- Fixture audit: PASS (10/10 invariants).
- One-shot baseline: 11/39 (28.2%) expected-status matches; positive/control fixture responses failed to parse and abstained.
- Batched model run (four checks per JSON response): 27/39 (69.2%) expected-status matches on the same scenario IDs, a +16 case change.
- By scenario type: positive 10/13; protected control 7/13; incomplete context 10/13.
- All returned positive evidence quotes passed exact substring validation.
- Artifacts: `data/risk/results/cross_document_model_scenarios_summary.json`, `cross_document_model_scenario_comparison.json/.md`, and `cross_document_model_scenarios_summary.md`.

**Interpretation caveat:** all expected labels are authored synthetic expectations. The improvement measures conformance on these fixtures only, not accuracy, generalization, or legal correctness. The protected-control over-flagging and incomplete-case ambiguity remain explicit errors to study.
