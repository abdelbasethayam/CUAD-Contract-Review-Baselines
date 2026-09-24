# Closed-Set CUAD Classification Report

## Scope

The CUAD classification layer was changed so every validated clause must leave
the classification boundary with one canonical CUAD label. Segmentation,
Cohere embeddings, Qdrant indexing, retrieval configuration, OpenRouter model,
risk reasoning, and the API contract were otherwise preserved.

## Files and functions changed

- `backend/app/core/rag/generator.py`
  - `parse_prediction_result()` now rejects malformed, forbidden, and
    out-of-candidate responses without returning them as labels.
  - `classify_clause()` now builds deduplicated candidate labels, retries empty
    retrieval once, retries invalid model output once, and enforces the final
    label boundary.
  - `_highest_scoring_retrieved_label()` provides the retrieval-based fallback.
  - `_semantic_fallback_label()` provides a deterministic full-CUAD fallback
    only when retrieval and model output are both unavailable.
  - `_retrieve_with_retry()` records retrieval status and retry errors.
- `backend/app/core/rag/prompt.py`
  - The prompt now requires exactly one allowed candidate and explicitly
    forbids abstention labels and arbitrary labels.
- `backend/app/services/rag_service.py`
  - Every validated clause, including definitions, now calls `classify_clause()`.
  - Risk analysis receives the final valid CUAD label and remains independent.
- `backend/app/models/schemas.py`
  - Added classification source, fallback, confidence, and retrieval status
    fields to preserve diagnostics.
- `backend/tests/test_openrouter_pipeline.py`
  - Updated forbidden-abstention parser expectations.
- `backend/tests/test_contract_risk_architecture.py`
  - Updated fixtures to use valid final CUAD labels.
- `backend/tests/test_closed_set_classification.py`
  - Added closed-set, fallback, retry, low-confidence, empty-retrieval,
    multi-label, boundary, and trace tests.

## Runtime behavior

The active classification flow is:

```text
Clause -> Cohere vector -> Qdrant Top-K -> unique candidate labels
       -> OpenRouter/Nemotron forced choice
       -> validation
       -> highest-scoring Qdrant label fallback
       -> deterministic full-CUAD fallback only if retrieval is unavailable
```

The successful trace is now `Classification selected: <valid label>`. Invalid
model output produces an explicit fallback trace and never a successful
`Classification complete: UNKNOWN` event.

## Verification

- Closed-set and related focused tests: **44 passed**.
- Full backend suite: **71 passed, 1 pre-existing segmentation failure**.
- Python compile check: **passed**.
- `git diff --check`: **passed**.
- Real run against `test_contract.pdf`: one validated clause received
  `Third Party Beneficiary` through `qdrant_top_match` fallback; one rejected
  fragment remained outside the validated-clause classification path.
- The real host run used the existing pdfplumber fallback because Docling is
  not installed in the host Python environment.

## UNKNOWN audit

Remaining occurrences are intentional and non-final:

- forbidden-output detection in `generator.py`;
- explicit prohibition text in the classifier prompt;
- test fixtures that simulate an invalid model response;
- risk-layer tests that verify risk remains independent of classification.

There is no application path that returns `UNKNOWN` as the final CUAD label
for a validated clause.
