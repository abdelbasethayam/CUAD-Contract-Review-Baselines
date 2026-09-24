# Legal Knowledge Base Audit

## Source and scope

The active Legal Knowledge Base path resolves to `backend/data/legal_knowledge`.
Ingestion reads Markdown recursively and requires front matter fields:
`source_name`, `source_url`, `title`, `clause_category`, and
`document_filename`.

The ingester excludes `risk_indicators.md`, `source_catalog.md`, and
`clause_coverage.md` from vectorization. The remaining `17` files are curated
source-derived summaries from WorldCC, ABA, IBA, WIPO, ICC, and UNCITRAL. They
contain guidance text, not CUAD annotations or contract clauses from the
510-contract dataset.

## Data flow

```text
Curated Markdown with front matter
        |
        v
parse_knowledge_document()
        |
        v
normalize whitespace; 1,200-character chunks; 150-character overlap
        |
        v
UUID5 chunk IDs + source/category metadata
        |
        v
Cohere embed_documents(input_type=search_document)
        |
        v
Qdrant collection legal_knowledge, cosine, dimension 1,024
```

## Current source counts

Calculated from the current Markdown and `backend/app/core/legal_knowledge/ingest.py`:

- included source Markdown files: `17`
- source categories: `11`
- freshly calculated chunks: `19`
- chunk length range: `302`–`1,200` characters
- calculated mean/median chunk length: `703.84` / `759` characters

The current stored collection was inspected read-only and contains `30`
vectors. Its payload keys are `retrieved_text`, `source_name`, `source_url`,
`title`, `clause_category`, `document_filename`, and `chunk_id`.

## Retrieval behavior

`map_clause_category()` maps a predicted CUAD label to a broader legal category.
`retrieve_legal_guidance()` embeds a query made from category terms plus clause
text, applies a Qdrant `clause_category` equality filter, and requests
`LEGAL_KNOWLEDGE_TOP_K=3` results. No reranker, threshold, BM25, or cross-encoder
is present.

## Exclusions and limitations

Full CUAD contracts, individual CUAD clauses, CUAD answers, positive/negative
CUAD examples, and test annotations are not ingested into this collection.
Five documented categories are intentionally not configured in the local legal
source directory: Non-Solicitation, Sub-Contracting, Suspension Rights,
Termination Assistance, and Order of Precedence. Runtime behavior for those
categories is unavailable rather than inferred.

