# Phase 2 Reproducible Experiment Report

**Validation: PASS**  
Generated (UTC): 2026-10-11T01:02:52.781113+00:00  
Git HEAD at report time: 630350a5d9010004f1c7653ba48d48a3a09c0924

> This report is not a legal correctness evaluation. Custom-risk accuracy remains unavailable because the human gold queue has no adjudicated labels.

## Dataset and integrity

| Item | Result |
|---|---:|
| Train contracts | 410 |
| Held-out test contracts | 100 |
| Train clause rows | 10545 |
| Test clause rows | 2556 |
| Integrity checks passing | 10/10 |
| Clause-level playbook checks | 101 |
| Cross-clause checks | 10 |
| Document checks | 3 |
| Canonical taxonomy domains | 10 |
| Human-risk labels filled | 0/300 |
| Human-evidence spans filled | 0/300 |

## Machine-silver results (diagnostics only)

| Machine status | Count |
|---|---:|
| MACHINE_DISAGREEMENT | 165 |
| MACHINE_AGREED_BUT_EVIDENCE_INVALID | 5 |
| MACHINE_AGREED | 108 |
| MACHINE_AGREED_UNCERTAIN | 22 |

| Decision | Count |
|---|---:|
| UNCERTAIN | 192 |
| NO | 95 |
| YES | 13 |

Direct model agreement rate: 0.360  
Agreement including agreed-uncertain: 0.433  
Disagreement rate: 0.550  
Machine YES cases with exact contiguous evidence: 13/13

These are machine-consensus and evidence-gate diagnostics, **not accuracy, precision, recall, or human agreement**. The models can agree and still be wrong.

## Split policy and experiment controls

- Train and test are contract-disjoint (410 / 100 contracts).
- Human gold queue plan: development 75, calibration 75, locked test 150; all annotation fields are currently blank.
- The separate machine-silver set has the same partition sizes. A quarantined 30-case locked-test pilot was not used for tuning; the protocol used for parameter diagnostics was limited to calibration/development.
- No custom-risk fine-tuning was performed.
- Exact playbook/taxonomy/hash inputs are recorded in the JSON report.
- Machine-silver is reproducible by running the recorded adjudication script with the pinned model names, server URLs, queue, and protocol settings, but LLM outputs can still vary across Ollama/model/library versions. The committed raw outputs and hashes are the authoritative record of this completed run.

## Comparability with existing repository results

| Existing experiment | Reported outcome | What it measures | Comparable as custom-risk accuracy? |
|---|---:|---|---|
| Phase 1 accepted paper — retrieval-conditioned SLM | 66.41% accuracy / 51.72% macro-F1 | CUAD clause-category classification on 1,679 held-out clauses | No |
| Phase 1 zero-shot baseline | 35.80% accuracy / 31.41% macro-F1 | Same Phase 1 clause-category target | No |
| Phase 1 random few-shot baseline | 50.98% accuracy / 40.93% macro-F1 | Same Phase 1 clause-category target | No |
| Fixed-10 CUAD classifier / RAG pilot | 4/10 = 0.40 | CUAD clause category prediction, 10-row pilot | No |
| Fixed-10 hybrid retrieval pilot | 5/10 = 0.50 accuracy; Recall@5 = 0.60 | Candidate retrieval and clause classification, 10-row pilot | No |
| Fixed-10 k-NN majority pilot | 6/10 = 0.60 | CUAD label prediction, 10-row pilot | No |
| Phase 2 two-model silver | YES=13, NO=95, UNCERTAIN=192 | Custom risk-predicate outputs without human gold | No |
| External CUAD expert annotations | 3420 contract/category tasks | CUAD category/evidence benchmark | No, not custom risk gold |

The old repository artifact under data/metadata/rag_pipeline_results.json reports exact-match 0.0 on a metadata-heavy retrieval task; it is not used as a baseline for Phase 2 risk decisions. Published/custom-risk metrics are not blended across different target definitions.

## Upload smoke tests (pipeline validation only)

| Run | HTTP | Pipeline | Clauses | Passes | Runtime | Evidence/artifact audit |
|---|---:|---|---:|---:|---:|---|
| Synthetic TXT (3 passes) | 200 | COMPLETED | 4 | 3 | 423.0 s | PASS |
| Repository PDF fixture (3 passes) | 200 | COMPLETED | 2 | 3 | 83.0 s | PASS |
| Synthetic TXT (1 pass) | 200 | COMPLETED | 4 | 1 | 171.1 s | PASS |
| txt_current_20261009 | 200 | COMPLETED | 11 | 1 | 367.0 s | PASS |
| txt_post_batching_20261009 | 200 | COMPLETED | 11 | 1 | 577.2 s | PASS |

These repository/synthetic fixtures demonstrate the request-to-result path, source-hash preservation, evidence checks, and artifact creation. They are not representative samples and do not measure risk accuracy or legal correctness. The single-pass TXT timing is one observed run, not a throughput benchmark.

## Active server retrieval profile

- Profile: local_hashing.
- Embedding: deterministic 768-dimensional scikit-learn HashingVectorizer with unigrams/bigrams and L2 normalization. It is a lexical-vector baseline, not equivalent to Cohere Embed v3's pretrained semantic embeddings.
- CUAD index: 7004 train-only points. Index build manifest: data/risk/results/local_hashing_cuad_index_manifest.json.
- Combined local index validation: PASS; manifests at data/risk/results/local_hashing_index_manifest.json.
- Representative legal-guidance retrieval: PASS across 3 query fixtures. This validates pipeline integration, not legal correctness.

## Local hashing held-out CUAD category baseline

- Train/test contract overlap: 0.
- Indexed training clauses: 7004 from 383 contracts.
- Held-out test clauses: 1679 from 92 contracts.
- 1-NN accuracy / Recall@1: 0.4705.
- Macro-F1: 0.3391.
- Recall@5: 0.6945; MRR@5: 0.5605.
- Contract-cluster bootstrap 95% CI for accuracy: 0.4402 to 0.5048.
- Contract-cluster bootstrap 95% CI for macro-F1: 0.2954 to 0.3703.

This is a deterministic lexical-vector nearest-neighbor clause-category baseline, not custom-risk accuracy and not equivalent to the prior Cohere-plus-SLM system. Full per-category metrics are in data/risk/results/local_hashing_cuad_retrieval_baseline.json and can be regenerated with scripts/risk/evaluate_local_hashing_baseline.py.

## Reproduce

From repository root:

1. Install dependencies and configure backend/.env; do not commit credentials.
2. Build the document-disjoint split and train-only Qdrant collections as documented in the root README.
3. Start Ollama and the backend using scripts/start_all.sh (or scripts/start_backend.sh and scripts/start_frontend.sh separately).
4. Upload a PDF/TXT through the frontend or POST to /documents/classify. The run writes a source hash, configuration/playbook/calibration hashes, checkpoints, trace, clause findings, cross/document checks, and final JSON.
5. Rebuild this silver report:

   python scripts/risk/report_phase2_experiment.py

6. Stop the backend before rebuilding embedded Qdrant indexes, then run `bash scripts/risk/build_local_retrieval_profile.sh`; restart with `bash scripts/start_all.sh`.
7. Run tests from repository root:

   `PYTHONPATH="$PWD:$PWD/backend:$PWD/.venv/lib/python3.12/site-packages" .venv/bin/python -m pytest -q backend/tests`.

## SHA-256

- Silver CSV: 12c618b4617225b9462616edaa553af23c7ac6b2a2e9527e6c0840e9b7d9230f
- Silver JSONL: e81c096b0f6517b6d1f72cee08208e7f4269bb1285bf48f1853efbfd440d62ca
- Playbook: e677e1d1e88deb1f9c2cb30c0cd994b1b6835cda593804c807941a11c5e04440
- Taxonomy: ebf0dea3cfcc97bb53e488265d8ef507339ba587fc660f3f942822d50ce0d218
- Integrity report: 22c888f4febc428e4f4878314134726558984fb59271993ac28ca69fd73b464a

## Scope of claims

Supported now: implementation/reproducibility, train/test leakage checks, exact-quote gating behavior, deterministic domain routing, and machine-silver disagreement/abstention diagnostics.  
Not supported now: custom-risk accuracy, legal correctness, severity calibration validity, probability calibration validity, or cross-clause/document risk sensitivity on real expert-labeled cases.

[executed on device: jupyter-group-digi2026-g6 (a8417900-e68e-4ee2-bbe7-fc3493ade5e1)]