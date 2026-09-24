# CUAD RAG — Data Pipeline

This stage prepares the [CUAD v1](https://www.atticusprojectai.org/cuad) (Contract
Understanding Atticus Dataset) for retrieval-augmented generation: splitting
contracts, embedding clauses, and loading them into a Qdrant vector store.

```
raw CSV (wide)  →  split_cuad.py  →  train/test CSV (long)
                                            │
                                            ▼
                                     embed_train.py  →  embeddings.json + metadata.jsonl
                                            │
                                            ▼
                                     build_qdrant.py  →  Qdrant collection (cuad_train)
```

## 1. `split_cuad.py` — Split & reshape

Takes the raw `master_clauses.csv` (wide format: **1 row = 1 contract**, with
41 clause-type column pairs — a text column and a matching `-Answer`
column) and produces a long-format dataset (**1 row = 1 extracted clause
span**) ready for embedding.

**What it does**

1. **Splits at the contract level** (410 train / 100 test, `random_state=42`)
   *before* any reshaping, so every clause from a given contract stays on
   one side of the split — this is what prevents data leakage.
2. **Reshapes wide → long**: each clause span becomes its own row with
   `document_id | clause_type | clause_text | answer | is_metadata`.
3. **Fixes inconsistent `-Answer` column naming** in the raw file (spacing/
   casing varies, e.g. `"Non-Compete-Answer"`) using a tolerant regex
   instead of an exact-suffix match, so no Answer column is silently
   dropped or turned into a bogus 42nd clause type.
4. **Parses stringified clause-span lists** (e.g. `"['some text']"`) into
   plain strings, and **explodes multi-span rows** so each extracted span
   gets its own row.
5. **Flags contract metadata** (`Document Name`, `Parties`, `Agreement
   Date`, `Effective Date`, `Expiration Date`) with `is_metadata=True`
   instead of dropping it — filter it out later with `df[~df.is_metadata]`.
6. Verifies no duplicate contracts and no train/test overlap before writing
   output.

**Outputs**

| File | Format | Description |
|---|---|---|
| `dataset/splits/train/master_clauses_train_wide.csv` | wide | Reference copy of the train contracts |
| `dataset/splits/test/master_clauses_test_wide.csv` | wide | Reference copy of the test contracts |
| `dataset/splits/train/master_clauses_train.csv` | long | **Used downstream** — one row per clause span |
| `dataset/splits/test/master_clauses_test.csv` | long | **Used downstream** — one row per clause span |

**Run**

```bash
python scripts/dataset/split_cuad.py
```

Requires `dataset/raw/cuad/CUAD_v1/master_clauses.csv` to exist and contain
exactly 510 contracts.

---

## 2. `embed_train.py` — Embed clauses (Cohere)

Reads the long-format train split, cleans it, and embeds each clause with
Cohere's `embed-v4.0` model.

**What it does**

- Loads `master_clauses_train.csv`, validates required columns.
- **Excludes contract-metadata rows by default** (`is_metadata=True`) so
  they don't pollute clause-similarity search — set
  `INCLUDE_METADATA_CLAUSES=true` in `.env` to embed them anyway.
- Cleans clause text (drops empty/`nan`/`[]` artifacts) and normalizes
  missing `answer` values to real `null` rather than the string `"nan"`.
- Generates a **deterministic UUID** per row (`uuid5` over
  `document_id::clause_type::row_index`) so re-runs produce stable IDs.
- Embeds in batches (default 96) with **exponential backoff retry** on
  Cohere `429` rate-limit responses (5 attempts, doubling delay from 5s).
- Saves the raw vectors and the parallel metadata separately.

**Outputs**

| File | Format | Description |
|---|---|---|
| `dataset/embeddings/train_embeddings.json` | JSON | `{model, count, dimension, embeddings: [[...]]}` |
| `dataset/embeddings/train_metadata.jsonl` | JSON Lines | One record per embedding: `id, document_id, clause_type, clause_text, answer, is_metadata` |

Embeddings and metadata are stored as **parallel arrays** (same order,
same length) — `build_qdrant.py` zips them back together by index.

**Environment variables** (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `COHERE_API_KEY` | — | **Required.** Cohere API key |
| `COHERE_MODEL` | `embed-v4.0` | Embedding model |
| `COHERE_BATCH_SIZE` | `96` | Texts per embed request |
| `INCLUDE_METADATA_CLAUSES` | `false` | Embed metadata rows too |

**Run**

```bash
python scripts/embedding/embed_train.py
```

Requires `dataset/splits/train/master_clauses_train.csv` (output of step 1).

---

## 3. `build_qdrant.py` — Load into Qdrant

Reads the embeddings + metadata from step 2 and builds a searchable Qdrant
collection.

**What it does**

- Validates both input files exist.
- Creates a Qdrant client — **remote** if `QDRANT_URL` is set (with
  optional `QDRANT_API_KEY`), otherwise **local on-disk** at
  `dataset/qdrant_local`.
- Creates the collection with vector size inferred from the embeddings and
  configurable distance metric (`COSINE` / `DOT` / `EUCLID`). If the
  collection already exists, prompts before deleting/recreating it.
- Upserts points in batches of 256. Each point's payload carries
  `document_id, clause_type, clause_text, answer, is_metadata` — the
  `is_metadata` flag is preserved so it can also be used as a **query-time
  filter**, not just at embedding time.
- Prints a final summary (vector count, status) to verify the load.

**Environment variables** (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `QDRANT_URL` | — | Remote Qdrant URL (omit for local mode) |
| `QDRANT_API_KEY` | — | Remote Qdrant API key (if applicable) |
| `QDRANT_PATH` | `dataset/qdrant_local` | Local on-disk store path (used when `QDRANT_URL` is unset) |
| `QDRANT_COLLECTION` | `cuad_train` | Collection name |
| `QDRANT_DISTANCE` | `COSINE` | Vector distance metric |

**Run**

```bash
python scripts/embedding/build_qdrant.py
```

Requires the outputs of step 2 (`train_embeddings.json`,
`train_metadata.jsonl`).

---

## Running the full pipeline

```bash
python scripts/dataset/split_cuad.py
python scripts/embedding/embed_train.py
python scripts/embedding/build_qdrant.py
```

## Data schema reference

**Long-format clause row** (train/test split CSVs):

| Column | Type | Notes |
|---|---|---|
| `document_id` | str | Contract filename, links back to the source PDF/TXT |
| `clause_type` | str | e.g. `Governing Law`, `Termination For Convenience` |
| `clause_text` | str | The extracted clause span |
| `answer` | str \| null | Annotated answer value for that clause, if any |
| `is_metadata` | bool | `True` for contract metadata fields (Document Name, Parties, Agreement/Effective/Expiration Date), `False` for substantive clause types |

**Qdrant point payload**: same fields as above, plus a deterministic `id`
(UUID5) used as the point ID.

## Notes / gotchas

- The train/test split is **contract-level**, not clause-level — always
  re-run `split_cuad.py` before re-embedding if the raw dataset changes,
  rather than reusing stale split files.
- `INCLUDE_METADATA_CLAUSES` and the `is_metadata` payload filter should
  usually be kept **excluded** for clause-similarity retrieval; metadata
  fields (dates, party names) are not semantically comparable to
  substantive clause text.
- Local Qdrant mode (`QDRANT_PATH`) locks the on-disk store while in use —
  close any other process holding it open before re-running
  `build_qdrant.py`.