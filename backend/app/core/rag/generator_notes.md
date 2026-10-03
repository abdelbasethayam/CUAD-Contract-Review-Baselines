# Generator integration notes

The original `classify_clause()` orchestrator remains the single entry point. These improvements are drop-in:

1. **Preprocessing** – call `preprocess_clause()` before embedding and prompting:

   ```python
   from .text_preprocessor import preprocess_clause
   clause_text = preprocess_clause(raw_clause_text)
   ```

2. **Prompt** – use the improved `build_prompt` (same signature).

3. **Config** – `TOP_K` default 10; `OLLAMA_MODEL` default `qwen2.5:7b` (env still overrides).

4. **Candidate constraint** – prompt restricts the model to Top-K labels or `NO_APPLICABLE_LABEL`.

5. **Abstention** – keep `MIN_RETRIEVAL_CONFIDENCE` so low-evidence cases do not force a category.

After merging, re-run the fixed-10 diagnostic with `OLLAMA_MODEL=qwen2.5:7b` to measure the lift.
