# Phase 2 risk data

## Risk playbook

The team commercial risk checklist is treated as a **versioned policy/playbook**, not ground-truth labels.

The supplied source contains 24 clause types, 63 clause-specific checks, 10 cross-clause checks, 3 document-level checks, and 7 cited sources.

Import it:

```bash
python scripts/risk/import_playbook.py /path/to/commercial_clause_risk_checklists.json
```

The importer preserves check IDs, questions, flag conditions, source IDs, and source metadata, then writes a deterministic `playbook_hash`.

The source archive can also be supplied directly when a compatible RAR extractor is installed:

```bash
python scripts/risk/import_playbook.py /path/to/risk-materials.rar
```

## Ground truth

A model finding is **not gold ground truth** merely because it matches the playbook.

Create a human annotation queue from the training split:

```bash
python scripts/risk/build_gold_queue.py --n 300
```

Two annotators should independently fill `annotator_1` and `annotator_2`; an adjudicator then fills the `adjudicated_*` columns. Keep these contracts outside the final held-out test set.

Recommended gold fields are binary risk, risk type, severity, exact evidence, and adjudication notes.

Fit calibration only from adjudicated rows:

```bash
python scripts/risk/fit_calibration.py --csv data/risk/gold/adjudicated_predictions.csv
```

Only after calibration exists should the runtime expose calibrated confidence or severity.

## External benchmarks

External risk corpora are benchmark references, not silent additions to CUAD.

The litigation-derived `ye-sylvette-sun/contract-risk` corpus has a different target: positives are clauses construed by a U.S. federal court. It must not be relabeled as customer/buyer ground truth.

Synthetic risk corpora are useful for robustness and prompt development, but they should not replace manually adjudicated gold.
