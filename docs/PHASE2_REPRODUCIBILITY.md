# Phase 2 Reproducibility and Operator Guide

This guide describes the runnable upload-to-report path and exactly what can currently be reproduced and claimed.

## A. Environment and prerequisites

- Python 3.12 is the current verified server runtime.
- Node/npm are required for the React/Vite frontend.
- Ollama must be running with the configured local models. The deployed profile used Qwen3:8B for production risk reasoning and separate Qwen3/Llama3.1/Gemma3 model servers for the silver experiment. Model names and URL settings must be recorded for each new run.
- Two embedding backends are supported. `cohere` uses Cohere Embed v3 and requires `COHERE_API_KEY`; `local_hashing` uses a deterministic scikit-learn HashingVectorizer without a network embedding call. Their Qdrant collections are incompatible and must never be interchanged.
- **Privacy:** the current server profile is configured for `EMBEDDING_BACKEND=local_hashing`, `QDRANT_COLLECTION=cuad_train_hashing`, and `LEGAL_KNOWLEDGE_COLLECTION=legal_knowledge_hashing`. LLM generation uses local Ollama and Qdrant is local, so the upload path can run without Cohere network access. The local hashing backend is a lexical-vector baseline, not a pretrained semantic embedding model; compare its results only as a separate configuration. The Cohere mode still sends clause/query text to Cohere.
- Local Qdrant data under data/qdrant_local must be built from the training split only. The separate train-only hashing index is created by `scripts/risk/build_local_hashing_index.py`.
- The legal-guidance collection is separate and must be indexed from the curated Markdown source files before upload analysis. The current source set builds 19 curated chunks under backend/data/legal_knowledge.
- Do not commit .env files or API keys.

The backend/.env.example is a template, not the source of truth for a live server. Check the actual environment and Ollama model tags before running. The code fingerprint, active configuration, playbook hash and calibration hash are written to each analysis manifest.

## B. Start the application

From the repository root:

    # Start Ollama model servers using your configured deployment/service manager.
    # Ensure the primary API is available at the OLLAMA_URL setting.

    bash scripts/start_all.sh
    curl -fsS http://127.0.0.1:8000/health
    curl -I http://127.0.0.1:5173/

Separate foreground commands for development are available:

    bash scripts/start_backend.sh
    bash scripts/start_frontend.sh

The frontend is usually at http://127.0.0.1:5173/; the API is usually at http://127.0.0.1:8000/. Use the actual externally forwarded URL supplied by the compute environment when working in a hosted notebook.

## C. Upload a contract and collect output

The frontend supports PDF/TXT upload. The API accepts the same:

    curl -sS -X POST \
      -F 'file=@data/risk/demo_contract_for_reproduction.txt;type=text/plain' \
      http://127.0.0.1:8000/documents/classify \
      -o data/risk/results/demo_contract_api_response.json

Expected response fields include analysis_id, extracted clause count, classification for each clause, finding evidence, contract-level risk assessment and download links.

Inspect:
- GET /health
- GET /documents/runs/{analysis_id}
- GET /documents/runs/{analysis_id}/artifact/result.json
- GET /documents/runs/{analysis_id}/artifact/manifest.json
- GET /documents/runs/{analysis_id}/artifact/trace.jsonl

The API also exposes a streaming endpoint at /documents/classify/stream. The full run directory is available locally under data/runs/<analysis_id>/.

The demo agreement in data/risk/demo_contract_for_reproduction.txt is synthetic, invented for a reproducibility smoke test, and not a real agreement. Its expected patterns are test stimuli rather than legal conclusions.

## D. Replay / resumability

A run is checkpointed after extraction, validation, embedding, each clause classification, clause risk, cross/document checks and aggregation. If a process stops, query the run status first. Use the supported resume API/implementation only when the original input and configuration fingerprint match. Do not manually combine outputs from different analysis IDs, model versions or playbook hashes.

## E. Verify source and data integrity

    .venv/bin/python scripts/risk/validate_evaluation_integrity.py
    .venv/bin/python scripts/risk/normalize_playbook_domains.py
    .venv/bin/python scripts/risk/export_team_pack.py
    .venv/bin/python scripts/risk/build_cross_document_scenario_suite.py
    .venv/bin/python scripts/risk/audit_cross_document_scenario_suite.py
    .venv/bin/python scripts/risk/report_phase2_experiment.py

Expected report-generator checks:
- final silver CSV and JSONL have 300 rows and matching sample IDs;
- silver partitions are exactly 150 locked-test, 75 calibration and 75 development;
- every machine YES includes an exact contiguous quote from its stored clause;
- all 114 checks map to one of the canonical 10 domains;
- all current split/embedding/index integrity checks pass;
- human-gold risk/evidence fields remain empty until independent annotation.

Generated reports/manifests:
- `data/risk/results/phase2_reproducible_report.json` and `.md` — experiment counts, allowed claims, source hashes, CUAD comparison table, and local retrieval-profile provenance.
- `data/risk/results/local_hashing_cuad_index_manifest.json` — source hashes, split counts and the 7,004-point train-only index build.
- `data/risk/results/local_hashing_index_manifest.json` — validation counts and payload metadata checks for both local Qdrant collections.
- `data/risk/results/legal_knowledge_retrieval_validation.json` — three representative legal-guidance retrieval fixtures.
- `data/risk/EVALUATION_INTEGRITY_REPORT.json` — 12 split/index isolation checks.

To rebuild the local retrieval profile from scratch, stop the backend and run `bash scripts/risk/build_local_retrieval_profile.sh`. It checks the backend is down before using embedded Qdrant, rebuilds both indexes, validates the source split and retrieval fixtures, then runs report/release checks. Restart the app afterward using `bash scripts/start_all.sh`.

The scripts must exit non-zero if a required invariant fails. Preserve outputs, hashes, environment configuration (without secrets), model tags and software version with the result.

## F. Run the test suite

Install project requirements first. For development, also install pytest:

    python -m pip install -r requirements.txt
    python -m pip install -r requirements-dev.txt
    PYTHONPATH="$PWD:$PWD/backend" python -m pytest -q backend/tests

Tests include the risk aggregation architecture, exact contract-evidence gating, playbook-domain authority, cross-clause/document check evidence validation, clause-validator GPU configuration, retrieval compression, CUAD classification, legal-knowledge retrieval and the API schema.

Re-run `PYTHONPATH="$PWD:$PWD/backend:$PWD/.venv/lib/python3.12/site-packages" .venv/bin/python -m pytest -q backend/tests` after any code modification, and update the stored release report. Unit tests are implementation checks, not model-accuracy measurements. The latest full release run passed 102 tests with three deprecation warnings. Re-run the full suite after any later code modification; this is an implementation test count, not a risk-accuracy measure.

## G. What the 300-case silver experiment reproduces

Queue:
data/risk/silver/silver_queue.csv

Final results:
- data/risk/silver/silver_annotations_final_v5_qwen3_gemma3_20261007.csv
- data/risk/silver/silver_annotations_final_v5_qwen3_gemma3_20261007.jsonl
- data/risk/silver/silver_annotations_final_v5_summary.json

Protocol:
- Qwen3:8B judge and Gemma3:12B blind verifier;
- independent concurrent calls; temperature 0; capped output tokens; JSON retries;
- explicit QUESTION + FLAG IF semantics;
- exact contiguous evidence gate;
- machine disagreements and uncertain cases retained as UNCERTAIN;
- 300 tasks total and no positive label allowed to pass with empty/invalid evidence.

The output CSV/JSONL is the authoritative recorded result. To conduct a new experiment rather than replay the existing outputs:

    python scripts/risk/run_silver_adjudication.py \
      --queue data/risk/silver/silver_queue.csv \
      --out data/risk/silver/new_silver_run.csv \
      --judge-model qwen3:8b \
      --verifier-model gemma3:12b \
      --judge-url http://127.0.0.1:11434 \
      --verifier-url http://127.0.0.1:11436

Use only a new output path, record the model digests/server URLs and the queue hash, and do not modify the locked partition or tune against its labels. LLM output may differ by model build, prompt/library version and hardware despite temperature 0; this is rerun capability, not a guarantee of bit-identical generative output.

## H. Metrics: what may and may not be reported

Report:
- counts and rates for machine agreement, disagreement, uncertainty and evidence-gate rejection;
- exact-evidence validity rate on positive silver outputs;
- split/integrity checks;
- latency and throughput measured from the completed upload run;
- deterministic cross-clause/document evaluation fixture pass rate;
- external CUAD category/evidence results only under their correct task definition;
- prior Phase 1 classification metrics only as a separate benchmark.

Do **not** report model consensus as accuracy. Do not compute precision/recall/F1 for custom risks until gold_risk is populated by independent expert annotation and adjudication. The available CUAD expert annotations concern clause category/evidence, not the custom buyer-side risk predicates, risk severity, or enforceability.

## I. Human-gold alternative

The project is runnable without human gold, but the claims must change accordingly. Without gold, the valid deliverable is:
1. a functioning decision-support system;
2. contract-evidence and configuration integrity tests;
3. reproducible machine-silver diagnostics;
4. synthetic regression tests for cross-clause/document checks;
5. external clause-category evidence validation;
6. a technical/system paper with an explicit evaluation limitation.

It is not valid to claim a validated risk classifier or measured custom-risk accuracy. The 300-row queue is kept for future human annotation; do not populate it with model outputs under a gold_* column.

## J. Release checklist

- [ ] full backend tests pass in the documented environment;
- [ ] local hashing train-only and legal-knowledge indexes are built with manifests;
- [ ] TXT synthetic smoke upload and audit complete to COMPLETED;
- [ ] PDF upload smoke test also completes to COMPLETED;
- [ ] the smoke manifest includes input SHA-256, pipeline config, code fingerprint, playbook hash, calibration hash and model names;
- [ ] clauses, risk findings, cross-clause/document findings and download endpoints return structured artifacts;
- [ ] silver report passes all invariants;
- [ ] team export matches playbook v1.1;
- [ ] generated frontend dependencies are excluded from the scientific commit;
- [ ] commit and release tag identify the paper/code snapshot;
- [ ] paper contains no unmeasured risk-accuracy claims.

## K. Cross-clause/document-level synthetic model evaluation

The source playbook has 10 cross-clause checks (X-1…X-10) and 3 document-level checks (DOC-1…DOC-3). The reproducible scenario suite creates 39 authored synthetic cases: one positive/risk-stressed fixture, one protected-control fixture and one incomplete-context fixture for each check. This is explicitly a **synthetic diagnostic**, not human gold and not a measure of real-contract accuracy.

Build fixture matrix and audit coverage/integrity:

    .venv/bin/python scripts/risk/build_cross_document_scenario_suite.py
    .venv/bin/python scripts/risk/audit_cross_document_scenario_suite.py

Run the actual LLM cross/document analyzer on each of the three fixture contracts (one configured pass per fixture). The production analyzer now evaluates **four checks per JSON response** (four model calls per pass for 13 checks) rather than requesting all 13 findings in one large response. This change prevents one truncated/malformed JSON response from converting the entire cross/document pass to abstentions. Any failed batch only leaves its own checks unresolved; other successfully parsed batches remain available. The scenario outputs bind to both the playbook hash and the SHA-256 of the analyzer and runner code.

    .venv/bin/python scripts/risk/run_cross_document_model_scenarios.py --passes 1

Resume only from rows whose playbook and fixture hashes still match:

    .venv/bin/python scripts/risk/run_cross_document_model_scenarios.py --passes 1 --resume

Expected outputs:

- data/risk/evaluation/cross_document_v1/scenario_matrix.jsonl — expected status, rationale, and evidence anchors for every check/scenario;
- data/risk/evaluation/cross_document_v1/manifest.json — fixture and playbook hashes;
- data/risk/results/cross_document_scenario_audit.json/.md — ten fixture-integrity/coverage invariants;
- data/risk/results/cross_document_model_scenarios.jsonl/.csv — observed model status, cited clause IDs/quotes, severity, expected-status match, and provenance for all 39 cases;
- data/risk/results/cross_document_model_scenarios_summary.json — status conformance, result distribution, exact-evidence outcome, timing, and input hashes.

Interpretation: scenario-status conformance is the fraction of model outputs matching our authored synthetic expectations. It is a regression signal, not an independent label. A synthetic positive can expose a missed interaction; a control case can expose over-flagging; an incomplete case can expose inappropriate certainty. None provides an expert judgment of a real legal risk.

The run_release_checks.py pipeline rebuilds and audits the matrix, resumes/validates the direct model outputs, then regenerates phase2_reproducible_report.json/.md. It also checks the live-upload smoke audit and full backend test suite. Run release checks while the embedded/local Qdrant store is not open by the running backend, because Qdrant Local enforces an exclusive storage lock; restart the backend afterward and verify /health.

Render a human-readable per-check report and compare the archived one-shot run with the corrected batched run on the same scenario IDs:

    .venv/bin/python scripts/risk/render_cross_document_model_report.py
    .venv/bin/python scripts/risk/compare_cross_document_model_runs.py

Comparison outputs:

- data/risk/results/cross_document_model_scenario_comparison.json
- data/risk/results/cross_document_model_scenario_comparison.md

The comparison is a small engineering ablation on the same 39 authored fixtures. It can support the claim that batching reduces response-truncation-induced abstention on these fixtures if the observed outputs do so. It cannot support a claim about overall legal-risk accuracy.

## L. Package the reproducible release

After release checks pass, create a minimal ZIP containing the paper, operator guide, claim/evidence matrix, logical model, Gold Status, protocol, scenario fixtures/results, model comparison, upload smoke responses/audits, baseline metrics, code and team export:

    .venv/bin/python scripts/risk/package_phase2_release.py

The script fails if a required input is missing. It creates `data/risk/releases/phase2_reproducible_release_20261009.zip` and a sidecar manifest with per-file SHA-256/byte counts and the ZIP SHA-256. The bundle intentionally excludes `.env` secrets and the frontend `node_modules`/build cache. It records the absence of human-gold risk labels as a limitation.

Release snapshot rule: rerun `scripts/risk/run_release_checks.py` after the final source/document edits, then regenerate the ZIP so the sidecar manifest refers to the final result files. Do not treat the checked-in/stored machine-silver labels or synthetic scenario expectations as expert ground truth.