# Hybrid retrieval + Qwen letter-logprob path (integrated)

## Why

Dense-only top-5 candidate sets only contain the gold label ~83.6% of the time
(leave-one-document-out on train). That **caps** any candidate-constrained LLM.

Hybrid dense + TF-IDF (RRF) shortlist of 8 from top-30 hits measured:

| Retrieval | kNN top-1 | Gold in shortlist |
|-----------|-----------|-------------------|
| Dense top-5 labels | 63.5% | 83.6% |
| Hybrid RRF k=30 → 8 | 71.7% | **96.8%** |

## Files

| Path | Role |
|------|------|
| `backend/app/core/rag/hybrid_retrieval.py` | Dense + TF-IDF RRF index |
| `backend/app/core/rag/qwen_classifier.py` | MCQ letters, logprobs, fusion |
| `backend/app/core/rag/hybrid_path.py` | API bridge `classify_with_hybrid_qwen` |
| `scripts/06_run_qwen_improved.py` | Eval runner |

Existing `classify_clause()` (preprocess, rules, thinking client) is **unchanged**.
Use the hybrid path when you want the measured shortlist + fusion approach.

## Config

```env
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_NUM_CTX=8192
HYBRID_COLLECTION=cuad_train          # or cuad_train_mpnet if that is your collection
HYBRID_INDEX_CACHE=./output/cache/hybrid_train_index.npz
HYBRID_K=30
HYBRID_SHORTLIST=8
QDRANT_PATH=./data/qdrant_local
```

Prefer **Instruct** 7B for letter logprobs; thinking models are weaker for single-token MCQ.

## Run

```bash
ollama pull qwen2.5:7b

# Hybrid kNN only (no LLM) — strong free baseline
python scripts/06_run_qwen_improved.py run --split test --no-llm

# Full hybrid + Qwen + fusion (needs val then test)
python scripts/06_run_qwen_improved.py run --split val
python scripts/06_run_qwen_improved.py run --split test
python scripts/06_run_qwen_improved.py fuse

# Average two option orders (cancels position bias; 2x cost)
python scripts/06_run_qwen_improved.py run --split test --perms 2
```

## API usage

```python
from backend.app.core.rag.hybrid_path import classify_with_hybrid_qwen
from backend.app.core.rag.prompt import load_label_definitions
from backend.app.core.config import load_labels

labels = load_labels()
defs = load_label_definitions(labels)
result = classify_with_hybrid_qwen(clause_text, query_vector, definitions=defs)
print(result["predicted_label"], result["classification_source"])
```

## Note on paths

The runner expects embeddings/metadata under `output/` when using the original
eval_1495 layout. If your paths differ, edit constants at the top of
`scripts/06_run_qwen_improved.py` or call `HybridIndex.from_qdrant` + `classify_clause_hybrid` directly.
