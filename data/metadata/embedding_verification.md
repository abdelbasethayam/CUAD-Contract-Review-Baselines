# Embedding and Qdrant Verification

Project root: `I:\gradation project\mvp2`

## Dataset Split Result

- Train contracts: `410`
- Test contracts: `100`
- Train/test document overlap: `0`

## Train/Test Counts

- Train wide CSV: `410` documents
- Test wide CSV: `100` documents
- Train clause records: `5449`

## Clause And Embedding Counts

- Generated embeddings: `5449`
- Embedding metadata records: `5449`
- Embedding dimension: `1024`

## Qdrant Collection

- Collection name: `cuad_train`
- Qdrant vector count: `5449`
- Qdrant document count: `410`
- Qdrant storage path: `dataset/qdrant_local`

## Leakage Check Result

- Train/test overlap: `0`
- TEST documents found in embeddings metadata: `0`
- TEST documents found in Qdrant collection: `0`
- All Qdrant vectors originate from TRAIN documents only: `yes`

## Embedding Input Used

- The embedding script uses `clause_text` as the text input sent to Cohere.
- The source long-form training file includes an `answer` column, but it is not part of the embedding text input.

## Final Pipeline

`CUAD → Train/Test Split → Train Clauses → Cohere Embeddings → Qdrant`

## Problems Found

- No data leakage or count mismatches were found.
- The only structural note is that the long-form training file retains an `answer` column for metadata, while the embedding input itself is `clause_text` only.

**VERIFICATION STATUS: PASS**
