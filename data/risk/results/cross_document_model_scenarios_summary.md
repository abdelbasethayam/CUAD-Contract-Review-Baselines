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
- Scenario manifest SHA-256: 56a2696d439b96a70430ad101413d088f6f57ca5346e8af3763a16dfd9183769
- JSONL SHA-256: b35d724e595b6b6b9ef5d8bdb97bad0c014796a38a51dc635963087146130ead
- CSV SHA-256: c335d81c215698a32185ffe755408b41b15c7ad9b4565d0c3851295826844f59
- CSV artifact: data/risk/results/cross_document_model_scenarios.csv