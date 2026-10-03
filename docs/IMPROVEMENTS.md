# Improvements for Qwen CUAD Classification (>66%)

## Changes on this repo (your fork main)

- Default `OLLAMA_MODEL = qwen2.5:7b`
- Default `TOP_K = 10`
- Candidate-constrained prompt with `NO_APPLICABLE_LABEL`
- `text_preprocessor.py`
- Evaluation harness under `backend/eval/`

## How to run

```bash
export OLLAMA_MODEL=qwen2.5:7b
export TOP_K=10
python -m backend.eval.run_classification_eval --fixed-json data/eval/fixed_5_rows.json --dry-run
```

Wire `preprocess_clause()` in `classify_clause` before embed/prompt (see `backend/app/core/rag/generator_notes.md`).
