# Generator integration notes

1. Call `preprocess_clause()` before embedding and prompting:

```python
from .text_preprocessor import preprocess_clause
clause_text = preprocess_clause(raw_clause_text)
```

2. Use improved `build_prompt` (same signature).
3. Defaults: `TOP_K=10`, `OLLAMA_MODEL=qwen2.5:7b` (env overrides).
4. Prefer importing `MIN_RETRIEVAL_CONFIDENCE` from config instead of hardcoding 0.35.
