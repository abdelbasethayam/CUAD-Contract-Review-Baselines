# Cross-Clause / Document-Level Model Scenario Results

Status: COMPLETED

- Cases: 39 / 39
- Synthetic status matches: 27 / 39 (69.2%)
- Exact-positive-evidence gate: True
- Check batch size: 4
- Model batches per scenario/pass: 4

Interpretation: these are authored synthetic regression cases, not human gold. Status matching measures implementation behavior on these fixtures only; it is not accuracy, precision/recall on real contracts, or legal correctness.

## Results by scenario type

| Scenario | Cases | Matches | Rate | POTENTIAL_RISK | NO_RISK | INSUFFICIENT_EVIDENCE | MISSING |
|---|---:|---:|---:|---:|---:|---:|---:|
| positive | 13 | 10 | 76.9% | 10 | 3 | 0 | 0 |
| control | 13 | 7 | 53.8% | 2 | 7 | 4 | 0 |
| incomplete | 13 | 10 | 76.9% | 4 | 0 | 9 | 0 |

## Results by check

| Check | Scope | Domain | Matches | Cases | Rate | Expected statuses | Observed statuses |
|---|---|---|---:|---:|---:|---|---|
| DOC-1 | document | Commercial Risk | 3 | 3 | 100.0% | POTENTIAL_RISK, NO_RISK, POTENTIAL_RISK | POTENTIAL_RISK, NO_RISK, POTENTIAL_RISK |
| DOC-2 | document | Dispute Resolution Risk | 2 | 3 | 66.7% | POTENTIAL_RISK, NO_RISK, INSUFFICIENT_EVIDENCE | POTENTIAL_RISK, INSUFFICIENT_EVIDENCE, INSUFFICIENT_EVIDENCE |
| DOC-3 | document | Dispute Resolution Risk | 2 | 3 | 66.7% | POTENTIAL_RISK, NO_RISK, INSUFFICIENT_EVIDENCE | POTENTIAL_RISK, NO_RISK, POTENTIAL_RISK |
| X-1 | cross_clause | Liability Risk | 2 | 3 | 66.7% | POTENTIAL_RISK, NO_RISK, INSUFFICIENT_EVIDENCE | POTENTIAL_RISK, INSUFFICIENT_EVIDENCE, INSUFFICIENT_EVIDENCE |
| X-10 | cross_clause | Liability Risk | 2 | 3 | 66.7% | POTENTIAL_RISK, NO_RISK, INSUFFICIENT_EVIDENCE | POTENTIAL_RISK, NO_RISK, POTENTIAL_RISK |
| X-2 | cross_clause | Financial Risk | 1 | 3 | 33.3% | POTENTIAL_RISK, NO_RISK, INSUFFICIENT_EVIDENCE | NO_RISK, POTENTIAL_RISK, INSUFFICIENT_EVIDENCE |
| X-3 | cross_clause | Termination Risk | 1 | 3 | 33.3% | POTENTIAL_RISK, NO_RISK, INSUFFICIENT_EVIDENCE | NO_RISK, INSUFFICIENT_EVIDENCE, INSUFFICIENT_EVIDENCE |
| X-4 | cross_clause | Commercial Risk | 2 | 3 | 66.7% | POTENTIAL_RISK, NO_RISK, INSUFFICIENT_EVIDENCE | POTENTIAL_RISK, INSUFFICIENT_EVIDENCE, INSUFFICIENT_EVIDENCE |
| X-5 | cross_clause | Assignment / Control Risk | 3 | 3 | 100.0% | POTENTIAL_RISK, NO_RISK, INSUFFICIENT_EVIDENCE | POTENTIAL_RISK, NO_RISK, INSUFFICIENT_EVIDENCE |
| X-6 | cross_clause | Intellectual Property Risk | 2 | 3 | 66.7% | POTENTIAL_RISK, NO_RISK, INSUFFICIENT_EVIDENCE | NO_RISK, NO_RISK, INSUFFICIENT_EVIDENCE |
| X-7 | cross_clause | Intellectual Property Risk | 3 | 3 | 100.0% | POTENTIAL_RISK, NO_RISK, INSUFFICIENT_EVIDENCE | POTENTIAL_RISK, NO_RISK, INSUFFICIENT_EVIDENCE |
| X-8 | cross_clause | Operational Risk | 2 | 3 | 66.7% | POTENTIAL_RISK, NO_RISK, INSUFFICIENT_EVIDENCE | POTENTIAL_RISK, NO_RISK, POTENTIAL_RISK |
| X-9 | cross_clause | Insurance Risk | 2 | 3 | 66.7% | POTENTIAL_RISK, NO_RISK, INSUFFICIENT_EVIDENCE | POTENTIAL_RISK, POTENTIAL_RISK, INSUFFICIENT_EVIDENCE |

## Traceability

- Playbook SHA-256: e677e1d1e88deb1f9c2cb30c0cd994b1b6835cda593804c807941a11c5e04440
- Analyzer code SHA-256: 860fb72c34c0bf9d8eecdc7247fe13d85b050821039f517346b820b17494a7a9
- Runner code SHA-256: f85e87cf625a268ba421a70f630887851a36d4c1be5a3de30de581b9ebe7f4ad
- Scenario manifest SHA-256: 64b99ca4dfd3c99e08f943391a5550cefec3a0e5b51f8e265b5ade6ab8a15737
- JSONL SHA-256: fd4bba65bec0f12367bf97f1c5d7c32a2de541e6bda6e4b347e52a1e403c968f
- CSV SHA-256: 02cd18acd70d7a85dfb31d87d16811460c36d745cfee86640b4039b4c5b06200
- CSV artifact: data/risk/results/cross_document_model_scenarios.csv

[executed on device: jupyter-group-digi2026-g6 (a8417900-e68e-4ee2-bbe7-fc3493ade5e1)]