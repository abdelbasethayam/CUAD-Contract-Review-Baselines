# Phase 2 risk data

## Risk playbook

The committed Phase 2 playbook is the runnable default at:
`data/risk/commercial_clause_risk_playbook.json`.

It covers **37 clause-risk targets**: all 36 substantive CUAD v1 categories after excluding the five metadata fields, plus the supplemental `Indemnification` risk category. The current artifact contains 101 clause-specific checks. The playbook is policy/guidance, not ground-truth labels.

If you later replace the playbook, keep the same path or set `RISK_PLAYBOOK_PATH` to the replacement.

## Legal guidance knowledge base

The local legal-knowledge files are stored under `backend/data/legal_knowledge/` and are ingested into a separate Qdrant collection so guidance is not mixed with CUAD examples.

Run from the repository root:

```bash
python -m backend.app.core.legal_knowledge.ingest
```

This requires a configured `COHERE_API_KEY`. Existing `data/qdrant_local` contains a prebuilt `legal_knowledge` collection, so ingestion is only needed when that collection is absent, stale, or intentionally replaced.

## Ground truth

A model finding is **not gold ground truth** merely because it matches the playbook.

The committed `data/risk/gold/gold_annotations.csv` is a 300-task human-annotation template. Two annotators should independently fill `annotator_1` and `annotator_2`; an adjudicator then fills the `adjudicated_*` columns. Keep the locked test partition untouched.

Fit calibration only from adjudicated calibration rows:

```bash
python scripts/risk/fit_calibration.py --csv data/risk/gold/gold_annotations.csv
```

Do not report calibrated confidence or severity until human adjudication has populated sufficient calibration rows.

## External benchmarks

**ContractEval** is the closest existing published benchmark for clause-level legal-risk identification in commercial contracts. It reuses CUAD and evaluates whether models can extract relevant risk-related spans. It is a useful methodological reference and external comparison, but it is **not** a direct gold standard for your buyer-side risk taxonomy because its task/output protocol differs from this repository.

**ContractNLI** is useful for a complementary document-level evidence/NLI check, particularly for hypotheses about contractual obligations and evidence spans. It should not be relabeled as risk ground truth.

Synthetic risk datasets can be used for robustness/prompt development, but they should not replace the human-adjudicated gold set.
