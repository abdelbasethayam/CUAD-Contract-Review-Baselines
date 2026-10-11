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
- Scenario manifest SHA-256: ca5cfbc510c7ef7fbd65664de69ac2a788a69d89f2dbcb13c8932f1ea18593cb
- JSONL SHA-256: 32e530d1c9de04aa3811fdd17129e957d2fa31e07840da500b2085d4e9f8582c
- CSV SHA-256: 963e784aefd56295154ebbf9a58d8a1b0d3e154c65dbd74e99449f52fae00dfe
- CSV artifact: data/risk/results/cross_document_model_scenarios.csv
