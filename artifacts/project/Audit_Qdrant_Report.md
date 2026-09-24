# Qdrant Audit

## Collections

Both collections are local persistent Qdrant stores under
`data/qdrant_local`. Read-only Qdrant inspection reported:

| Collection | Vectors | Dimension | Distance | Documents/categories |
|---|---:|---:|---|---|
| `cuad_train` | 7,004 | 1,024 | Cosine | 383 documents, 36 labels |
| `legal_knowledge` | 30 | 1,024 | Cosine | 11 categories, 6 source organizations |

The local store is selected because `QDRANT_URL` is not configured in the
current backend environment. The application reuses one local client and the
ingesters upsert in batches of 256. The build script can delete/recreate a
collection interactively, but that operation was not run during this audit.

## CUAD payload schema

```text
Embedding (1,024 floats)
        |
        v
cuad_train / cosine
        |
        v
document_id, clause_type, clause_text, answer, is_metadata
```

All inspected current CUAD points have `is_metadata=False`. There are no
payload fields for risk labels, confidence, or legal guidance.

## Legal payload schema

```text
Embedding (1,024 floats)
        |
        v
legal_knowledge / cosine
        |
        v
retrieved_text, source_name, source_url, title,
clause_category, document_filename, chunk_id
```

The Qdrant collection metadata does not expose an additional payload index
configuration in the inspected local metadata. HNSW/optimizer details are
NOT VERIFIED beyond the stored `meta.json` representation.

## Discrepancy

The current Qdrant collections contain 7,004 and 30 points, while older
verification artifacts refer to 5,449 CUAD points. The older count is not the
current local store count.

