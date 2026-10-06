# Risk gold annotation files

These files are committed so the Phase 2 risk workflow is runnable immediately.

- `../commercial_clause_risk_playbook.json` is the installed 37-target playbook: all 36 substantive CUAD v1 clause categories plus the supplemental `Indemnification` category.
- `gold_annotations.csv` is the canonical 300-task human-annotation template.
- `annotation_queue.csv` is the runtime-compatible copy used by `scripts/risk/run_gold_evaluation.py`.

The CSV currently contains **no completed human gold labels**. Annotators must independently fill the annotation fields and an adjudicator must populate the `adjudicated_*` fields before gold evaluation or calibration.

Do not treat playbook-derived findings as gold ground truth. The playbook is policy/guidance and remains separate from human adjudication.

To regenerate the annotation queue after replacing the playbook:

```bash
python scripts/risk/build_gold_queue.py --n 300
```

The committed templates can be replaced later with the adjudicated dataset.
