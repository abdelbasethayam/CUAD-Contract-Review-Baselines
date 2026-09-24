# Data Transformation Audit

## CUAD indexing path

```text
CUAD v1 master_clauses.csv (wide, 510 contracts)
  -> split_cuad.py: contract-level 410/100 split, random_state=42
  -> wide train/test CSVs
  -> wide_to_long(): parse stringified span lists, explode multi-span rows,
     retain answers, flag five metadata fields
  -> train/test long CSVs
  -> embed_train.py: remove is_metadata rows, reject empty clause text,
     create deterministic UUID5 IDs
  -> Cohere search_document embeddings
  -> train_embeddings.json + train_metadata.jsonl
  -> build_qdrant.py: payload + vector upsert in batches of 256
  -> local Qdrant collection cuad_train
```

Verified counts:

| Stage | Train | Test |
|---|---:|---:|
| contracts after split | 410 | 100 |
| long rows | 10,545 | 2,556 |
| metadata rows | 3,541 | 877 |
| substantive rows | 7,004 | 1,679 |
| indexed/embedded rows | 7,004 | not indexed |

The embedding input is `clause_text` only. The `answer` field is retained in
metadata/payload but is not concatenated into the embedding text.

## Uploaded-contract path

```text
PDF/TXT upload
  -> temporary file in documents.py
  -> hybrid_parser.parse_document()
  -> Docling ordered blocks, or pdfplumber fallback
  -> clause_segmenter.segment_document()
  -> ClauseNode tree with page, marker, parent, definition, and signature metadata
  -> validator.is_real_clause() for candidate fragments
  -> Cohere search_query embeddings for validated clause texts
  -> Qdrant cuad_train Top-K search
  -> candidate-label-constrained Ollama CUAD classification
  -> legal category mapping and legal_knowledge Qdrant search
  -> regex indicators + constrained Ollama risk assessment
  -> ClauseResult API model
  -> JSON or SSE response
  -> React frontend
```

The runtime path does not write uploaded text, embeddings, or results to the
CUAD collection.

