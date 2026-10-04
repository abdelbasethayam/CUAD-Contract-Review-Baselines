# Round 3 improvements

## New modules

| Module | Purpose |
|--------|--------|
| `confusion_pairs.py` | Deterministic tie-break for frequent CUAD confusions (cap vs uncapped, non-compete vs exclusivity, …) |
| `embed_cache.py` | LRU cache for query embeddings (fewer Cohere calls) |
| `self_consistency.py` | Majority vote across multiple model samples |
| `prompt_contrastive.py` helpers in notes | Optional hard-negative labels in the prompt |

## Wire examples

### Confusion resolve (after model/rule decision)

```python
from backend.app.core.rag.confusion_pairs import resolve_confusion

label, reason = resolve_confusion(clause_text, predicted_label, candidates=allowed_labels)
if reason:
    predicted_label = label
```

### Embedding cache

```python
from backend.app.core.rag.embed_cache import get_or_embed
from backend.app.core.rag.embed_preprocess import text_for_embedding

text = text_for_embedding(raw)
vec = get_or_embed(text, model=COHERE_MODEL, embed_fn=lambda t: embed_one(t))
```

### Self-consistency (optional, slower)

```python
from backend.app.core.rag.self_consistency import sample_labels, majority_vote

samples = sample_labels(lambda: parse_one_call(), n=3)
label, counts = majority_vote(samples, allowed=set(allowed_labels))
```

## Eval

See updated `backend/eval/run_classification_eval.py` for per-label counts and JSON report export.
