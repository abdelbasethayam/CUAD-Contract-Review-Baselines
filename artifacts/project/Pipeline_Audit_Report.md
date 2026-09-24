# Pipeline Audit Report

## 1. Executive Summary

The repository implements a CUAD clause-classification pipeline with a separate
curated legal-knowledge and risk-analysis layer. CUAD train clauses are embedded
with Cohere `embed-english-v3.0` and stored in local Qdrant. Uploaded contract
clauses are embedded as queries, retrieved against Top-5 CUAD examples, and
classified by candidate-constrained Ollama. Risk analysis maps the CUAD label to
a legal category, retrieves Top-3 legal guidance, applies regex indicators, and
asks Ollama for a strictly validated typed risk result.

The current local stores contain 7,004 CUAD vectors and 30 legal-knowledge
vectors. Several older reports use stale 5,449-vector counts and should not be
treated as current measurements.

## 2. Audit Scope

Inspected source, configuration, local datasets, embeddings, Qdrant storage,
legal Markdown, API, frontend, tests, existing diagnostics, and read-only
runtime behavior. No implementation, data, model configuration, or vector
store was modified.

## 3. Repository Architecture

The active modules and responsibilities are listed in
`Audit_Repository_Inventory.md`. The runtime path is:

```text
upload -> parse -> segment -> validate -> embed -> CUAD retrieve
-> CUAD classify -> legal retrieve -> indicators -> risk Ollama
-> strict validation -> API -> frontend
```

## 4. Dataset Inventory

CUAD v1 is locally represented as raw wide CSV/JSON, 410/100 contract-level
train/test splits, long clause CSVs, embedding artifacts, and Qdrant points.
There are 510 raw contracts, 41 categories, and 36 substantive runtime labels.
The full dataset distinction is documented in `Audit_Dataset_Report.md`.

## 5. Legal Knowledge Base

The Legal Knowledge Base is curated Markdown, not CUAD. Seventeen current source
files produce 19 chunks according to the current ingester, while the stored
collection contains 30 points. It is category-filtered and separate from
`cuad_train`.

## 6. Data Lifecycle

The exact CUAD and uploaded-contract transformations are documented in
`Audit_Data_Transformation.md`. CUAD answers remain metadata and are not
embedded. Uploaded documents are not persisted into the index.

## 7. Parsing

PDF parsing is Docling-first in `hybrid` mode with pdfplumber fallback. TXT is
read directly. Docling was not available in the current host audit environment.

## 8. Segmentation

The service uses the page-aware structured `ClauseNode` segmenter. A read-only
regex-fallback execution on the ZTO PDF produced 4 blocks and 16 top-level
nodes. The complete segmentation audit is in `Audit_Segmentation_Report.md`.

## 9. Chunking

Runtime contract processing is structural clause segmentation and has no sliding
window overlap. Legal KB chunking is 1,200 characters with 150-character
overlap. The legacy flat segmenter has a 40-character minimum and 3,000-character
fallback threshold.

## 10. Metadata

CUAD payload metadata: `document_id`, `clause_type`, `clause_text`, `answer`,
`is_metadata`. Legal payload metadata: source/title/category/document/chunk
fields. Runtime clause metadata includes page and structural fields before API
serialization.

## 11. Embeddings

Cohere `embed-english-v3.0`, 1,024 dimensions, batch size 96. Stored documents
use `search_document`; runtime queries use `search_query`. Normalization,
truncation, and embedding cost are NOT VERIFIED.

## 12. Qdrant

Local persistent Qdrant contains `cuad_train` (7,004 vectors) and
`legal_knowledge` (30 vectors), both dimension 1,024 and cosine distance.

## 13. Retrieval

CUAD retrieval is dense Qdrant Top-5 with an `is_metadata != true` filter.
Legal retrieval is category-filtered Top-3. BM25, hybrid retrieval, RRF,
reranking, and thresholds are not implemented in the active path.

## 14. CUAD Classification

Retrieved CUAD examples become candidate labels. Ollama receives only unique
valid retrieved candidates and may return one candidate or UNKNOWN. Malformed
and out-of-candidate responses are explicitly distinguished internally and are
normalized to an UNKNOWN prediction with a status.

## 15. Risk Analysis

Risk combines clause text, CUAD category routing, curated legal guidance, regex
indicators, and Ollama. It is not a CUAD risk label. Strict validation requires
JSON boolean risk and exact clause evidence. No calibrated score or severity
assignment is implemented.

## 16. Contract-Level Aggregation

NOT IMPLEMENTED / NOT VERIFIED. The service returns per-clause results only.

## 17. API

Active classification endpoints are `/documents/classify` and
`/documents/classify/stream`. `/health`, `/docs`, and `/openapi.json` are also
active. The `/query` stub is not included. See `Audit_API.md`.

## 18. Frontend

React uploads to the SSE endpoint and displays clause labels, retrieval scores,
risk statuses, reasons, evidence, sources, and legal guidance. See
`Audit_Frontend.md`.

## 19. End-to-End Trace

The ZTO parser trace and its verification limits are in
`Audit_End_to_End_Trace.md`. Live Cohere/Ollama outputs were not generated by
this audit.

## 20. Numerical Statistics

The consolidated source-tagged table is in `Audit_Numerical_Statistics.md`.

## 21. Models and Configuration

Resolved runtime values: Cohere `embed-english-v3.0`; Qdrant local path and
collections `cuad_train`/`legal_knowledge`; CUAD Top-K 5; legal Top-K 3; Ollama
`llama3.2:3b`; timeout 60 seconds; retries 3. The checked-in `.env.example`
matches most values, while source defaults mention `qwen2.5:1.5b`. The actual
loaded backend `.env` resolves to `llama3.2:3b`.

## 22. Tests and Validation

Compilation passed. The focused legal/risk suite passed 17 tests. The full
backend suite from its package directory produced 44 passes and one failure in
an existing segmentation test for compact numbered clauses. Docling, Docker,
live Cohere, live Ollama, and current frontend build are NOT VERIFIED in this
environment.

## 23. Architecture Diagram

See `Pipeline_Architecture.mmd`.

## 24. Known Limitations

- Legal Qdrant count (30) does not match a fresh current-source calculation (19).
- Older verification notes report a stale 5,449 CUAD count versus 7,004 current points.
- Data scripts use `dataset/...` paths while the current repository stores data under `data/...`.
- The current host lacked Docling and Node runtime components.
- Risk has no calibrated score/severity or contract aggregate.
- Existing ZTO retrieval diagnostics are leakage-affected.

## 25. Unverified Components

Live external Cohere requests, live Ollama responses, Docling-based current
segmentation, Docker execution, frontend build, production latency, embedding
normalization/truncation, Qdrant HNSW details, and contract-level aggregation
are NOT VERIFIED.

## 26. Final Audit Status

**PARTIAL — implementation and local persisted artifacts were audited, but live
external/model execution and Docling/frontend runtime verification were not
available.**

