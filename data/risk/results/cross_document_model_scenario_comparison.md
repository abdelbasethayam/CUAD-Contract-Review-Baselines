# Cross-Clause / Document-Level Batching Ablation

**Important:** synthetic fixture comparison only; not human gold or real-contract accuracy.

- Cases compared: 39
- Same scenario IDs in both runs: True
- One-shot conformance: 11/39 (28.2%)
- Batched conformance: 27/39 (69.2%)
- Change: +16 cases (+41.0%)
- Scenario decisions changed: 25

| Run | Positive matches | Control matches | Incomplete matches | Observed statuses |
|---|---:|---:|---:|---|
| One-shot | 0/13 | 0/13 | 11/13 | {'INSUFFICIENT_EVIDENCE': 36, 'POTENTIAL_RISK': 3} |
| Batched | 10/13 | 7/13 | 10/13 | {'POTENTIAL_RISK': 16, 'NO_RISK': 10, 'INSUFFICIENT_EVIDENCE': 13} |

## Status changes

| Scenario | Type | Expected | Before | After |
|---|---|---|---|---|
| DOC-1-CONTROL | control | NO_RISK | INSUFFICIENT_EVIDENCE | NO_RISK |
| DOC-1-POSITIVE | positive | POTENTIAL_RISK | INSUFFICIENT_EVIDENCE | POTENTIAL_RISK |
| DOC-2-POSITIVE | positive | POTENTIAL_RISK | INSUFFICIENT_EVIDENCE | POTENTIAL_RISK |
| DOC-3-CONTROL | control | NO_RISK | INSUFFICIENT_EVIDENCE | NO_RISK |
| DOC-3-INCOMPLETE | incomplete | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | POTENTIAL_RISK |
| DOC-3-POSITIVE | positive | POTENTIAL_RISK | INSUFFICIENT_EVIDENCE | POTENTIAL_RISK |
| X-1-POSITIVE | positive | POTENTIAL_RISK | INSUFFICIENT_EVIDENCE | POTENTIAL_RISK |
| X-10-CONTROL | control | NO_RISK | INSUFFICIENT_EVIDENCE | NO_RISK |
| X-10-POSITIVE | positive | POTENTIAL_RISK | INSUFFICIENT_EVIDENCE | POTENTIAL_RISK |
| X-2-CONTROL | control | NO_RISK | INSUFFICIENT_EVIDENCE | POTENTIAL_RISK |
| X-2-POSITIVE | positive | POTENTIAL_RISK | INSUFFICIENT_EVIDENCE | NO_RISK |
| X-3-POSITIVE | positive | POTENTIAL_RISK | INSUFFICIENT_EVIDENCE | NO_RISK |
| X-4-POSITIVE | positive | POTENTIAL_RISK | INSUFFICIENT_EVIDENCE | POTENTIAL_RISK |
| X-5-CONTROL | control | NO_RISK | INSUFFICIENT_EVIDENCE | NO_RISK |
| X-5-POSITIVE | positive | POTENTIAL_RISK | INSUFFICIENT_EVIDENCE | POTENTIAL_RISK |
| X-6-CONTROL | control | NO_RISK | INSUFFICIENT_EVIDENCE | NO_RISK |
| X-6-POSITIVE | positive | POTENTIAL_RISK | INSUFFICIENT_EVIDENCE | NO_RISK |
| X-7-CONTROL | control | NO_RISK | INSUFFICIENT_EVIDENCE | NO_RISK |
| X-7-POSITIVE | positive | POTENTIAL_RISK | INSUFFICIENT_EVIDENCE | POTENTIAL_RISK |
| X-8-CONTROL | control | NO_RISK | INSUFFICIENT_EVIDENCE | NO_RISK |
| X-8-INCOMPLETE | incomplete | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | POTENTIAL_RISK |
| X-8-POSITIVE | positive | POTENTIAL_RISK | INSUFFICIENT_EVIDENCE | POTENTIAL_RISK |
| X-9-CONTROL | control | NO_RISK | INSUFFICIENT_EVIDENCE | POTENTIAL_RISK |
| X-9-INCOMPLETE | incomplete | INSUFFICIENT_EVIDENCE | POTENTIAL_RISK | INSUFFICIENT_EVIDENCE |
| X-9-POSITIVE | positive | POTENTIAL_RISK | INSUFFICIENT_EVIDENCE | POTENTIAL_RISK |

## Reproducibility

- Baseline SHA-256: 722e26122c405b7e04c43dc08a09c4450b8b1b7138d5b9315e14e47196506b3d
- Batched SHA-256: fd4bba65bec0f12367bf97f1c5d7c32a2de541e6bda6e4b347e52a1e403c968f
- Analyzer code SHA-256: 860fb72c34c0bf9d8eecdc7247fe13d85b050821039f517346b820b17494a7a9
- Runner code SHA-256: f85e87cf625a268ba421a70f630887851a36d4c1be5a3de30de581b9ebe7f4ad

This is a code-path ablation on 39 hand-authored synthetic fixtures. It measures whether the batching change improves fixture-status conformance and preserves outputs under the constructed scenarios. It is not human gold, not real-contract accuracy, and not legal correctness.