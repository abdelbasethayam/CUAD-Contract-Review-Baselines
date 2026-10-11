# Held-out machine-adjudicated silver set

**Status: completed; diagnostic only, not human gold.**

## Final production outputs

- CSV: `silver_annotations_final_v5_qwen3_gemma3_20261007.csv`
- JSONL: `silver_annotations_final_v5_qwen3_gemma3_20261007.jsonl`
- Summary: `silver_annotations_final_v5_summary.json`
- Protocol: `silver_v5_blind_parallel`
- Models: Qwen3 judge and Gemma3 skeptical verifier; independent/blind verifier; deterministic JSON/evidence checks.
- CSV SHA-256: `12c618b4617225b9462616edaa553af23c7ac6b2a2e9527e6c0840e9b7d9230f`.

## Coverage and partitions

- 300 tasks; 72 documents; 95 unique risk checks.
- Locked test: 150 tasks.
- Calibration: 75 tasks.
- Development: 75 tasks.

## Results

| Machine result | Count |
|---|---:|
| Machine disagreement | 165 |
| Machine agreed | 108 |
| Machine agreed uncertain | 22 |
| Agreement but invalid evidence | 5 |
| Final UNCERTAIN | 192 |
| Final NO | 95 |
| Final YES | 13 |

No positive decision had empty evidence. This does not mean the positive evidence is human-verified, nor does it establish accuracy.

## Construction and scientific use

The source is the held-out CUAD test split (`data/splits/test/master_clauses_test.csv`). The unit is `(contract_id, clause_index, check_id)`. Positive decisions require exact contiguous contract evidence. Disagreements and unresolved decisions are retained as uncertainty.

Use this set for qualitative error analysis, debugging, and sensitivity diagnostics only. Never call it expert-annotated or human-adjudicated gold, and do not derive custom-risk accuracy claims from it.

The human annotation queue is separate: `data/risk/gold/gold_annotations.csv`; its 300 human labels/evidence fields remain blank.
