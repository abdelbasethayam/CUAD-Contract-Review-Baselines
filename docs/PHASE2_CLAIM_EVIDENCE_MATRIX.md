# Phase 2 Paper — Claim-to-Evidence Matrix

This matrix is intended for a supervisor/reviewer to verify each empirical or architectural statement in `docs/PHASE2_PAPER_DRAFT.md`. It is not a substitute for expert legal evaluation.

| Paper claim | Evidence artifact | Reproduction/check | Permitted interpretation | Not supported |
|---|---|---|---|---|
| CUAD split is 410 train / 100 test contracts | `data/splits/train/master_clauses_train.csv`, `data/splits/test/master_clauses_test.csv` | `python scripts/risk/validate_evaluation_integrity.py` | Project-specific contract-disjoint split | It is not claimed to be the official CUAD split |
| Index/train-test isolation | `data/risk/EVALUATION_INTEGRITY_REPORT.json` | Integrity validator; 12 assertions | Those configured boundaries show zero overlap across three checked Qdrant collections | It does not prove no leakage through any untracked/external process |
| 37 clause targets / 101 clause checks / 10 cross-checks / 3 document checks | `data/risk/commercial_clause_risk_playbook.json` | `python scripts/risk/normalize_playbook_domains.py` | Playbook coverage/configuration | Not 37 empirically validated risk classes |
| One canonical domain per check | Playbook + `backend/data/legal_knowledge/risk_taxonomy.json` | `python scripts/risk/normalize_playbook_domains.py`; export script | Deterministic routing/aggregation metadata | Not evidence that the flagged risk is true |
| 300 machine-silver diagnostic tasks | `data/risk/silver/silver_queue.csv`, final CSV/JSONL/summary | `python scripts/risk/report_phase2_experiment.py` | Machine agreement, disagreement, abstention and evidence-gate diagnostics | Not human gold or custom-risk accuracy |
| 13/13 machine YES rows have exact evidence | Final silver CSV/JSONL | Phase 2 report generation | Stored positive quotes are exact substrings of task clause text | Does not verify semantic sufficiency or risk interpretation correctness |
| Cross-clause/document evidence validation | `backend/tests/test_contract_checks_evaluation.py`, `backend/tests/test_deterministic_cross_checks.py`, `backend/tests/test_contract_checks_batching.py` | Run backend tests; `scripts/risk/audit_cross_document_scenario_suite.py`; `scripts/risk/run_cross_document_model_scenarios.py` | Synthetic invariant enforcement plus 39 model-run regression cases across all 10 X checks and 3 DOC checks; analyzer/runner hashes recorded | Not human gold, real-contract sensitivity/recall, or legal correctness |
| Upload-to-artifact path works | `data/risk/results/smoke_upload_api_post_batching_20261009.json`, `data/risk/results/smoke_test_audit_post_batching.json`, and associated completed run artifacts | `python scripts/risk/smoke_upload_api.py`; then `python scripts/risk/audit_smoke_run.py` | Operational behavior on invented fixture | Not legal quality, field usability, or real-contract performance |
| Prior Phase 1 classification metrics | Prior Phase 1 experiment artifacts / accepted paper | See the corresponding Phase 1 results under the repository; reproduce using its frozen classification config | CUAD category classification performance | Not Phase 2 buyer-side risk accuracy |
| Custom risk accuracy unavailable | `data/risk/gold/gold_annotations.csv`, `data/risk/GOLD_STATUS.md` | `python scripts/risk/report_phase2_experiment.py` | Queue has 300 rows and zero human risk/evidence annotations | No precision/recall/F1/calibration/legal-correctness claim |
| Run reproducibility/provenance | `data/runs/<analysis_id>/manifest.json`, `trace.jsonl`, configuration hashes | Inspect each complete run; check listed artifact SHA-256 | Configuration, source and trace are recorded | LLM outputs are not guaranteed bit-identical across model/runtime/hardware versions |

## Claims to avoid in the submission

- "The system achieves X% risk accuracy" — unavailable without independent labels for the custom predicates.
- "Two-model agreement establishes correctness" — it only establishes agreement.
- "Exact quote means correct legal reasoning" — exactness validates provenance, not interpretation.
- "Fully offline/private" — current deployment calls the Cohere embedding API.
- "Detects all whole-contract risks" — the defined cross-clause/document checks and context retrieval are not an exhaustive legal review.
- "First" or "novel" without a documented survey-of-surveys comparison and a defensible baseline study.

## Minimum pre-submission checklist

1. Confirm author list, affiliations, acknowledgments, and the intended venue's format.
2. Freeze the repository snapshot and record the commit hash; keep generated model/database files out of source commits unless required as declared artifacts.
3. Regenerate the report, team export and release validation from the frozen snapshot.
4. Include the completed end-to-end smoke audit output and list any degraded provider behavior.
5. Ensure all references have verified bibliographic metadata and venue links.
6. State plainly that the contribution is an auditable system/protocol report and that custom-risk accuracy remains unmeasured.
