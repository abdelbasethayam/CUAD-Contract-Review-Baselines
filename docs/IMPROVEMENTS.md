# Improvements for Qwen CUAD Classification (>66%)

## Diagnosis of the original ~40% pilot

On the fixed 10-row diagnostic:

- Accuracy ≈ 0.40
- Retrieval miss (GT not in Top-5) was the dominant failure
- Secondary failures: classification error when GT was present, and occasional out-of-candidate labels

A 1.5B model with weak retrieval cannot reliably distinguish 40+ overlapping CUAD categories.

## Changes in this PR

### 1. Model & retrieval defaults
- Default `OLLAMA_MODEL = qwen2.5:7b` (override with env)
- Default `TOP_K = 10`
- Explicit `MIN_RETRIEVAL_CONFIDENCE` for safe abstention

### 2. Candidate-constrained prompt
Classifier may only pick labels that appear in the retrieved Top-K (or abstain with `NO_APPLICABLE_LABEL`).

### 3. Text preprocessing
- Whitespace / quote normalization
- Common legal abbreviation expansion

### 4. Evaluation harness
`backend/eval/run_classification_eval.py` reports accuracy, Recall@K, MRR, and error taxonomy.

## Expected impact

| Lever | Expected contribution |
|-------|------------------------|
| 1.5B → 7B Qwen | +15–25 points |
| Top-K 5 → 10 + cleaner candidates | +5–10 points |
| Candidate constraint + better prompt | +3–8 points |
| Preprocessing | +2–5 points |

## How to test

```bash
export OLLAMA_MODEL=qwen2.5:7b
export TOP_K=10
python -m backend.eval.run_classification_eval --fixed-json data/eval/fixed_5_rows.json
# or re-run the original fixed-10 diagnostic
```
