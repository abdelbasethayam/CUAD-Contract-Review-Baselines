# Embedding Audit

## Runtime contract embeddings

`backend/app/core/rag/embedder.py` uses Cohere `ClientV2.embed` with the
resolved model `embed-english-v3.0`. Validated uploaded clause text is sent as
`input_type="search_query"`. Batching is configured at `96` texts and the
backend retry limit is `8` attempts for Cohere 429 responses, with exponential
backoff beginning at five seconds.

## Stored CUAD embeddings

`data/embeddings/train_embeddings.json` records:

| Property | Value | Evidence |
|---|---|---|
| provider | Cohere | source code and artifact |
| model | `embed-english-v3.0` | embedding artifact |
| dimension | `1,024` | embedding artifact and Qdrant |
| vectors | `7,004` | embedding artifact |
| input | substantive `clause_text` | `embed_train.py` |
| input type | `search_document` | `embed_train.py`/embedder |
| batch size | `96` | resolved configuration |
| normalization | NOT VERIFIED / not configured | source inspection |
| truncation/max input length | NOT VERIFIED / not configured | source inspection |

The parallel metadata JSONL has one record per stored vector. It includes the
deterministic UUID5 ID, document ID, CUAD label, clause text, answer, and
metadata flag. Answers are not included in embedding input.

## Legal Knowledge Base embeddings

Legal chunks use the same resolved Cohere model and `search_document` input
type. Runtime legal queries use `search_query`. The persisted collection has
dimension `1,024`. Embedding cost, server-side truncation, and normalization
are NOT VERIFIED.

The data-script README and the current scripts contain stale `dataset/...`
paths and a fallback mention of `embed-v4.0`; those paths are not the active
backend runtime paths, and the stored artifact identifies `embed-english-v3.0`.

