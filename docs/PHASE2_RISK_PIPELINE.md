# Phase 2 — Evidence-grounded contract risk analysis

## End-to-end flow

```text
upload
  -> persistent content-addressed run
  -> document extraction / clause segmentation
  -> CUAD classification
  -> clause-level playbook checks
      -> deterministic indicators
      -> same-contract context
      -> local Qwen risk reasoning
      -> exact evidence validation
      -> self-consistency
  -> cross-clause checks
  -> document-level checks
  -> deterministic contract aggregation
  -> calibrated confidence/severity when a gold calibration file exists
  -> result.json + machine-readable audit artifacts + GUI
```

## Playbook

The team's commercial risk checklist is stored as policy. It currently contains 24 clause types, 63 clause-specific checks, 10 cross-clause checks, 3 document checks, and 7 source references.

Import the supplied JSON or RAR archive before a full run:

```bash
python scripts/risk/import_playbook.py /path/to/commercial_clause_risk_checklists.json
```

Do not call playbook-derived findings human gold. The run labels them PLAYBOOK_DERIVED and stores the playbook hash.

## Gold protocol

Build a blinded annotation queue from the 410-contract training split:

```bash
python scripts/risk/build_gold_queue.py --n 300
```

Two annotators independently label risk, type, severity and exact evidence. Adjudicate disagreements. Keep a locked evaluation subset that is not used for calibration or tuning.

Calibration:

```bash
python scripts/risk/fit_calibration.py --csv data/risk/gold/adjudicated_predictions.csv
```

The runtime then maps the raw support diagnostic into calibrated risk probability and ordinal severity probabilities using the persisted isotonic curves.

## Metrics and statistical tests

`scripts/risk/evaluate.py` reports binary classification metrics, AUROC, PR-AUC, Brier, ECE, specificity, MCC, macro-F1, contract-level metrics, ordinal severity MAE, macro-F1, quadratic weighted kappa, Spearman correlation, evidence exact-match/token-F1, and inter-annotator kappa when annotation columns are present.

Confidence intervals use contract-level bootstrap because clauses from the same contract are correlated. Paired model comparison supports exact McNemar and paired contract-cluster bootstrap of accuracy difference.

## Ablation matrix

Run and compare at minimum:

| ID | Configuration |
|---|---|
| A | deterministic playbook/indicator rules only |
| B | LLM risk reasoning without playbook checklist |
| C | LLM + playbook |
| D | C + same-contract semantic context |
| E | D + retrieved legal guidance |
| F | E + self-consistency |
| G | F + calibrated confidence/severity |
| H | cross-clause checks enabled vs disabled |
| I | document-level checks enabled vs disabled |

Do not choose thresholds from the locked gold test.

## Resumability

Each run is stored under `data/runs/<analysis_id>/`.

Key artifacts:

- `manifest.json` — source hash, pipeline settings, playbook hash, environment and status
- `source.<ext>` — persistent input copy
- `segments.json` — extraction/segmentation checkpoint
- `validated.json` — validation checkpoint
- `embeddings.npy` — clause embedding checkpoint
- `classification.jsonl` — one record per completed clause
- `risk_findings.jsonl` — one record per completed playbook check
- `contract_checks.json` — cross/document checks
- `contract_risk.json` — final aggregate
- `result.json` — API/GUI result snapshot
- `trace.jsonl` — live trace persisted for replay

Resume a stopped run:

```bash
python scripts/run_pipeline.py resume <analysis_id>
```

The run id is derived from the source SHA-256 and pipeline configuration fingerprint. Changing the playbook/model/config produces a new run rather than silently reusing stale results.

## Full stack

Start FastAPI with the normal project command and build the React frontend as already documented in the root README. The browser now exposes Overview, Clauses, and Risks tabs plus audit-artifact downloads.

Production uploads do not have independent ground truth. The UI therefore says so explicitly instead of displaying the model's own result as 'ground truth'. Gold labels are only attached in evaluation datasets.