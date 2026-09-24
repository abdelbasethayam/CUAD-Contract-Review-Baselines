# Data Integrity Audit

**Status: COMPLETE (read-only audit)**

## Executive summary

The live dataset artifacts show a correct 410/100 contract-level split with zero train/test document overlap and zero test documents in the persisted training embedding metadata. The actual train long-format count is 10,545, not 11,015; 10,545 -> 7,004 is fully reconciled because metadata rows are retained in the long-format file but intentionally excluded before embedding; no substantive rows are lost by empty-text filtering.

The main data-quality concerns are reproducibility/documentation drift, not evidence of leakage: the current split/embedding scripts reference an older `data/dataset/...` layout while the live artifacts are under `data/raw` and `data/splits`, and `data/metadata/embedding_verification.md` records an older 5,449-vector run. The fixed 10-row benchmark is deliberately category-stratified and therefore not representative of the overall test distribution.

## Repository paths inspected

- `raw_master_csv`: `data/raw/cuad/CUAD_v1/master_clauses.csv`
- `raw_cuad_json`: `data/raw/cuad/CUAD_v1/CUAD_v1.json`
- `train_wide`: `data/splits/train/master_clauses_train_wide.csv`
- `test_wide`: `data/splits/test/master_clauses_test_wide.csv`
- `train_long`: `data/splits/train/master_clauses_train.csv`
- `test_long`: `data/splits/test/master_clauses_test.csv`
- `train_embeddings`: `data/embeddings/train_embeddings.json`
- `train_metadata`: `data/embeddings/train_metadata.jsonl`
- `fixed_selection`: `diagnostics/fixed_10_classification_baseline/selected_10_rows.json`
- `split_script`: `data/scripts/dataset/split_cuad.py`
- `embedding_script`: `data/scripts/embedding/embed_train.py`

## Original dataset audit

- `master_clauses.csv`: `510` rows and `510` unique contract identifiers.
- `CUAD_v1.json`: `510` data items and `510` unique titles.
- Wide schema: `83` columns = `41` clause/metadata text columns plus `41` answer columns and `Filename`.
- Substantive categories: `36`; metadata categories: `Agreement Date, Document Name, Effective Date, Expiration Date, Parties`.
- Answer-column pairing: unmatched answer columns `0`; text columns without answer columns `0`.

## Train/test split audit

- Train wide contracts: `410`; test wide contracts: `100`.
- Train/test document intersection: `0`.
- The split script calls `train_test_split` on the wide contract table before `wide_to_long`, with train size 410, test size 100, and random state 42.
- **Invariant: PASS.** `TRAIN_DOCUMENT_IDS ∩ TEST_DOCUMENT_IDS = ∅` in the actual wide artifacts.
- Reproducibility note: the checked-in script currently resolves `data/dataset/raw/...`, but the live repository artifacts are under `data/raw/...`; the existing files therefore cannot be regenerated from that script path without correcting the path layout. This is a minor reproducibility issue, not evidence that the stored split overlaps.

## Row-count reconciliation

| Stage | Train | Test | Notes |
|---|---:|---:|---|
| Original CUAD master contracts | 510 | - | Wide source rows |
| Wide contract rows | 410 | 100 | One row per contract |
| Long-format rows | 10545 | 2556 | One row per extracted span |
| Metadata rows | 3541 | 877 | Retained, flagged, then excluded from embeddings |
| Non-metadata rows | 7004 | 1679 | Substantive clause rows |
| Empty/invalid clause text rows | 0 | 0 | After long-format export |
| Persisted embedding records | 7004 | - | Training metadata JSONL |

## Investigation: 11,015 -> 7,004

| Filtering step | Rows removed | Rows remaining |
|---|---:|---:|
| Train long-format input | 0 | 10545 |
| Metadata exclusion (`is_metadata=True`) | 3541 | 7004 |
| Empty/invalid text cleaning | 0 | 7004 |
| Embedding persistence | 0 | 7004 |

The count reconciles exactly: `10545 - 3541 - 0 = 7004`. The reduction is intentional metadata filtering, not a failed embedding batch or category loss.

## Category coverage

See `category_coverage.csv` for all categories. Every substantive category present in the train/test artifacts has embedded training support; retention is calculated against the substantive train rows.

| Category | Train clauses | Test clauses | Embedded train | Retention | Fixed rows |
|---|---:|---:|---:|---:|---:|
| `Affiliate License-Licensor` | 39 | 8 | 39 | 100.00% | 1 |
| `Audit Rights` | 485 | 128 | 485 | 100.00% | 1 |
| `Competitive Restriction Exception` | 92 | 22 | 92 | 100.00% | 1 |
| `Joint Ip Ownership` | 83 | 17 | 83 | 100.00% | 1 |
| `Non-Compete` | 189 | 37 | 189 | 100.00% | 1 |
| `Price Restrictions` | 25 | 1 | 25 | 100.00% | 1 |
| `Revenue/Profit Sharing` | 304 | 91 | 304 | 100.00% | 1 |
| `Rofr/Rofo/Rofn` | 283 | 67 | 283 | 100.00% | 1 |
| `Termination For Convenience` | 186 | 37 | 186 | 100.00% | 1 |
| `Warranty Duration` | 143 | 21 | 143 | 100.00% | 1 |

The ten fixed categories all exist in training and have 100% retention into embeddings. Support size varies materially, so the audit does not claim that every category has enough examples for reliable retrieval; rare-category rows remain a plausible retrieval difficulty even without preprocessing loss.

## Fixed-10 audit

- Rows: `10`; IDs are `fixed-10-01` through `fixed-10-10`.
- Source: `data/splits/test/master_clauses_test.csv`; selection matches the corresponding test CSV rows: `True`.
- Unique contracts represented: `9` (10 rows include two rows from the same Liquidmetal contract).

| ID | Category | Text length | In test | Train support | Embedded support |
|---|---|---:|---|---:|---:|
| `fixed-10-01` | `Warranty Duration` | 228 | Yes | 143 | 143 |
| `fixed-10-02` | `Price Restrictions` | 298 | Yes | 25 | 25 |
| `fixed-10-03` | `Non-Compete` | 553 | Yes | 189 | 189 |
| `fixed-10-04` | `Rofr/Rofo/Rofn` | 204 | Yes | 283 | 283 |
| `fixed-10-05` | `Competitive Restriction Exception` | 328 | Yes | 92 | 92 |
| `fixed-10-06` | `Joint Ip Ownership` | 517 | Yes | 83 | 83 |
| `fixed-10-07` | `Revenue/Profit Sharing` | 129 | Yes | 304 | 304 |
| `fixed-10-08` | `Termination For Convenience` | 319 | Yes | 186 | 186 |
| `fixed-10-09` | `Audit Rights` | 226 | Yes | 485 | 485 |
| `fixed-10-10` | `Affiliate License-Licensor` | 569 | Yes | 39 | 39 |

## Test-set representativeness

The full substantive test set contains `1679` clause rows across `100` contracts and `36` categories. The fixed pilot contains exactly one row from each of ten selected categories and therefore is **strongly stratified/skewed**, not a proportional sample of all test clauses.

It is useful for controlled category-by-category diagnostics, but its accuracy must not be interpreted as overall test accuracy. Several fixed categories have substantially fewer or more examples than others in the full test distribution; the pilot intentionally overrepresents the chosen categories and rare-category behavior.

## Duplicate and leakage audit

- Exact substantive clause-text overlap: `20` unique texts; train rows affected `29`; test rows affected `29`.
- Normalized overlap (Unicode NFKC, lowercase, whitespace normalization): `30` unique texts; train rows affected `30`; test rows affected `30`.
- These overlaps occur across distinct train/test documents, so they are not document leakage; they are repeated clause-text patterns that can make a small number of test rows easier. Fixed-10 exact matches against train: `0`; normalized matches: `0`.
- Near-duplicate check: token 3-gram Jaccard, maximum train similarity for each fixed row; threshold 0.90. Fixed rows at/above threshold: `0`.
- The fixed pilot has no exact or strong near-duplicate train matches under these checks. This is not a proof that all semantic similarity across the entire corpus is absent.

## Embedding and document leakage audit

- Persisted vectors: `7004`; metadata records: `7004`; dimensions: `[1024]`; finite values: `True`.
- Expected train records vs metadata IDs: missing `0`, unexpected `0`, field mismatches `0`.
- Unique embedding documents: `383`; intersection with test documents: `0`; test clauses represented in embedding metadata: `0`.
- Read-only local Qdrant check: collection `cuad_train`, points `7004`, vector size `1024`, distance `Cosine`, status `green`.
- **Document-level leakage: PASS.** The persisted embedding metadata contains only training documents.

## Embedding model audit

- Configured model in `data/scripts/.env`: `embed-english-v3.0`.
- Persisted model: `embed-english-v3.0`.
- Match: `True`.
- The `data/README.md` default text mentions `embed-v4.0`, but the actual environment value used by the embedding script is `embed-english-v3.0`; this is documentation drift, not an embedding-artifact mismatch.

## Relationship to current retrieval results

The split and embedding data do not show contract leakage, missing fixed categories, or unexplained embedding loss. Therefore the four hybrid retrieval misses are not plausibly explained by train/test document overlap or by the 11,015 -> 7,004 reduction.

The remaining data-related contributors are category support imbalance and clause difficulty: a category can be present and fully embedded but still have few or lexically/semantically diverse training examples. The fixed pilot is also deliberately selected rather than representative. The unchanged Recall@5 of 0.60 and zero recovery of the four previous misses point more directly to retrieval/category-evidence difficulty than to split corruption, while the accuracy change to 0.50 remains a downstream classification result on this pilot.

## Final diagnosis

### Verdict: B. DATA PIPELINE HAS MINOR ISSUES BUT IS USABLE

### Confirmed problems
- Current scripts and documentation contain path/count/model drift relative to the live artifacts.
- The fixed 10-row benchmark is not representative of the overall test distribution.

### Suspected problems
- Rare or difficult categories may have insufficiently diverse training evidence for strong retrieval, even though they are present and embedded.

### Things that are not problems
- Contract-level split integrity: PASS.
- No document-level leakage was found; limited repeated clause-text overlap exists across disjoint documents and is documented above.
- Test documents in training embeddings: none.
- 10,545 -> 7,004 reconciliation: explained exactly by metadata exclusion.
- Missing fixed-pilot categories from training: none.

### Recommended next experiment
Use a larger, fixed, contract-disjoint evaluation sample stratified across all substantive CUAD categories, report per-category retrieval recall and support counts, and separately evaluate rare categories. Do not alter the current fixed-10 benchmark; use the larger set as a new diagnostic benchmark.

## Audit safety

This audit read source files only and did not modify production source, split files, embeddings, Qdrant, environment files, experiment reports, branches, commits, or configuration.
