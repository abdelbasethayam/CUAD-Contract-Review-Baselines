# Risk Pipeline Update Report

## Status

Implemented in place. Existing segmentation, CUAD data, Cohere embeddings,
CUAD Qdrant retrieval, and the Legal Knowledge Base were preserved. No CUAD
collection was re-indexed and no external risk dataset was added.

The real OpenRouter runtime is currently blocked because
`OPENROUTER_API_KEY` is not configured in the environment. Therefore no
successful live CUAD classification or risk conclusion is claimed.

## Previous architecture

```text
PDF/TXT -> existing segmentation -> Cohere query embedding -> CUAD Qdrant
       -> local Ollama CUAD classification -> category-based legal retrieval
       -> regex-gated local Ollama risk decision -> API/frontend
```

The previous risk implementation could treat Legal Knowledge Base retrieval as
the main risk context and rejected model-positive findings when no regex
indicator matched.

## New architecture

```text
PDF/TXT
  -> existing segmentation
  -> Cohere query embeddings
  -> CUAD Qdrant Top-K retrieval
  -> candidate labels + CUAD evidence
  -> OpenRouter candidate-constrained CUAD classification
  -> same-contract semantic context Top-K (default 5)
  -> supporting Legal Knowledge Base retrieval
  -> deterministic indicators as supporting signals
  -> OpenRouter evidence-grounded risk reasoning
  -> exact contract-evidence validation
  -> typed clause result -> API/frontend
```

There is still one active pipeline. The risk detector was refactored in place;
no parallel old/new risk service was introduced.

## Exact files changed

- `backend/app/core/config.py`
  - Added OpenRouter model, endpoint, API-key, timeout, retry, temperature,
    max-token, and contract-context Top-K settings.
- `backend/.env.example`
  - Added the documented OpenRouter variables without adding a secret.
- `backend/app/core/rag/generator.py`
  - Added `call_openrouter()` with chat-completions handling, exponential
    retry, HTTP 429 handling, and safe content extraction.
  - Existing `call_ollama()` is retained only as a compatibility name and
    delegates to OpenRouter; classification does not call Ollama.
  - Existing `classify_clause()` still performs Cohere/Qdrant retrieval and
    candidate-constrained validation.
- `backend/app/core/rag/prompt.py`
  - Updated prompt documentation for the OpenRouter/local-validation flow.
  - Existing candidate-only label instructions remain active.
- `backend/app/core/risk/contract_context.py`
  - New, necessary separation for same-uploaded-contract semantic context
    retrieval. It ranks the already-created Cohere clause vectors locally,
    excludes the target clause, preserves exact text and stable chunk IDs, and
    returns configurable Top-K context.
- `backend/app/core/risk/risk_detector.py`
  - Replaced category-first/regex-gated decisions with contract-first,
    evidence-grounded risk reasoning.
  - Added `build_risk_prompt()`, strict response parsing, exact evidence
    validation, `INSUFFICIENT_EVIDENCE`, related-context handling, and
    supporting-indicator behavior.
- `backend/app/services/rag_service.py`
  - Passes all validated clause embeddings to same-contract context retrieval.
  - Preserves CUAD examples/candidate labels and passes them into risk
    reasoning.
- `backend/app/models/schemas.py`
  - Added candidate labels, exact retrieved CUAD examples, related contract
    context, and the `INSUFFICIENT_EVIDENCE` risk status.
- `frontend/src/App.jsx`
  - Separates CUAD Retrieval Evidence from Final CUAD Classification.
  - Displays related contract context and the new insufficient-evidence state.
  - Does not display a risk level when evidence is insufficient.
- `backend/tests/test_legal_knowledge.py`
  - Updated the invalid-evidence expectation to `INSUFFICIENT_EVIDENCE`.
- `backend/tests/test_openrouter_pipeline.py`
  - Added focused configuration, parsing, malformed-response, retry,
    candidate-constrained classification, contract-context, and evidence
    validation tests.

## OpenRouter configuration

The following variables are configurable in `.env`:

```text
OPENROUTER_API_KEY=
OPENROUTER_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_TIMEOUT_SECONDS=120
OPENROUTER_MAX_RETRY_ATTEMPTS=3
OPENROUTER_TEMPERATURE=0
OPENROUTER_MAX_TOKENS=700
CONTRACT_CONTEXT_TOP_K=5
```

The API key is read from the environment and is not hard-coded or serialized
into API results. The request enables reasoning where supported, but the
implementation returns only the assistant content and never exposes
`reasoning_details` or hidden chain-of-thought.

Classification/risk calls use OpenRouter. The existing local Ollama code in
`validator.py` remains part of the pre-existing segmentation validation path,
which was intentionally not modified.

## CUAD retrieval and classification roles

CUAD retrieval remains responsible for Cohere query embedding, Qdrant Top-K
search, similarity scores, exact training-example text, and candidate labels.
It is not treated as the final classification decision.

The OpenRouter classifier receives the current clause, retrieved examples,
candidate labels, scores, label definitions, and extracted legal features. Its
result is locally validated. A label outside the retrieved candidate set is
rejected and normalized to `UNKNOWN`; malformed responses and explicit
`UNKNOWN` remain distinguishable through `classification_status`.

The API preserves `retrieved_examples`, `retrieved_labels`,
`retrieved_scores`, `candidate_labels`, `predicted_label`, and
`classification_status`.

## Contract-context retrieval

`retrieve_related_contract_context()` uses the actual Cohere embedding of the
current clause and compares it with embeddings of other validated clauses from
the same uploaded file. The current clause is excluded. Each result contains:

- stable `chunk_id`
- original `clause_index`
- exact `clause_text`
- similarity score

The default is five related clauses, configurable through
`CONTRACT_CONTEXT_TOP_K`. No second contract dataset or Qdrant collection is
created.

## Legal Knowledge Base role

The existing curated Legal Knowledge Base remains in use as supporting legal
guidance. It may explain why a contractual pattern matters, but it cannot by
itself establish that the uploaded contract contains a risk. Guidance failure
does not manufacture a risk and does not prevent contract-first reasoning from
continuing.

## Regex indicator role

The documented deterministic indicators are preserved with their rule IDs and
matched indicator names. They are included as supporting signals and risk-rule
metadata. A missing regex match no longer automatically produces `NO_RISK`.

## Risk schema and validation

Risk statuses are:

- `POTENTIAL_RISK`
- `NO_RISK`
- `INSUFFICIENT_EVIDENCE`
- `ERROR`

`POTENTIAL_RISK` requires a risk type, reason, and an exact contiguous evidence
substring found in the current clause or a related uploaded-contract chunk.
Only then may `HIGH`, `MEDIUM`, or `LOW` be retained. `NO_RISK` and
`INSUFFICIENT_EVIDENCE` expose no severity. Malformed model output, invalid
status, missing evidence, or paraphrased evidence cannot become a positive
risk finding.

Legal guidance is serialized separately from `evidence`; guidance text is
never accepted as contract evidence.

## API and frontend behavior

The existing `/documents/classify` and `/documents/classify/stream` routes
remain active. Response clauses now preserve both classification evidence and
risk evidence. The frontend presents:

1. CUAD Classification: final candidate-constrained label, candidate labels,
   and retrieved CUAD examples/scores.
2. Risk Analysis: typed status, risk type/level when valid, exact contract
   evidence, reason, related contract context, matched indicators, and
   supporting legal guidance.

CUAD classification is never replaced by the risk result.

## Tests

- Backend compilation: **PASS**
- Focused legal/OpenRouter suite: **25 passed**
- Full backend suite at the time of this update: **52 passed, 1 failed**
- The one failure is the pre-existing segmentation test
  `tests/test_segmenter.py::test_compact_numbered_clauses_split_after_sentence_boundaries`.
  No segmentation implementation was changed for this task.
- The existing `test_contract.pdf` segmentation executed successfully with the
  existing `pdfplumber-fallback` path and produced two segmented clauses.

## Runtime results for `test_contract.pdf`

Segmentation was verified. The real CUAD retrieval/classification and risk
stages were not claimed as successful because `OPENROUTER_API_KEY` is not
configured. The runtime therefore stops before a live OpenRouter classification
can be completed. No fabricated CUAD label, risk status, evidence, or risk
level was reported.

The PDF used the existing fallback because Docling is not installed in the
local Python environment. This is an environment limitation, not a
segmentation change.

## Limitations and remaining issues

- Configure `OPENROUTER_API_KEY` before live classification/risk execution.
- The selected free OpenRouter endpoint may rate-limit or fail; retry and
  timeout handling is implemented, but provider availability is external.
- Cohere remains required for CUAD and contract-context embeddings.
- Docling is not available in the local runtime, so PDF parsing used the
  existing pdfplumber fallback.
- The existing full-suite segmentation failure remains unresolved by design.
- Contract-level aggregation is intentionally not implemented.
- The Docker image/container running before this update was not rebuilt; a
  rebuild should be performed only after ensuring secrets are excluded from
  the build context and the OpenRouter key is supplied at runtime.
