# Retrieval Audit

## CUAD retrieval

The active classifier path is dense vector retrieval through
`backend/app/core/rag/retriever.py`:

1. Cohere embeds the uploaded clause as a `search_query`.
2. Qdrant queries `cuad_train` with `limit=top_k`.
3. A `must_not is_metadata=True` filter excludes metadata points.
4. The returned points retain score, CUAD label, and clause text.

The resolved CUAD `TOP_K` is `5`. No score threshold is configured.

## Legal retrieval

Legal retrieval constructs a query from the mapped legal category terms and the
clause text, embeds it with Cohere, filters Qdrant by exact `clause_category`,
and requests `LEGAL_KNOWLEDGE_TOP_K=3`.

## Absent retrieval features

The inspected active path does not implement BM25, keyword retrieval, hybrid
retrieval, Reciprocal Rank Fusion, reranking, a cross-encoder, or a similarity
threshold. The word `hybrid` in the application refers to Docling/pdfplumber
parsing, not hybrid retrieval.

| Parameter | Value |
|---|---|
| CUAD Top-K | 5 |
| Legal Knowledge Top-K | 3 |
| CUAD threshold | NOT CONFIGURED |
| BM25-K | NOT IMPLEMENTED |
| RRF-K | NOT IMPLEMENTED |
| reranker Top-N | NOT IMPLEMENTED |

## Leakage/evaluation note

Existing ZTO diagnostic artifacts report exact/self-document retrieval and
explicitly mark the result leakage-affected. They are not a clean unseen-test
estimate of current retrieval generalization.

