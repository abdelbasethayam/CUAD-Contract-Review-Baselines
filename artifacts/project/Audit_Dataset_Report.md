# Dataset Audit

## CUAD source

The local source is CUAD v1 under `data/raw/cuad/CUAD_v1`. Its included README
describes 510 commercial contracts and 41 categories. Local counts verified from
the files are:

| Representation | Documents/contracts | Rows/records | Categories |
|---|---:|---:|---:|
| `master_clauses.csv` wide | 510 | 510 data rows | 41 category columns, 83 columns including answers |
| `CUAD_v1.json` | 510 articles | 510 top-level articles | SQuAD-style annotations |
| train wide CSV | 410 | 410 | 41 |
| test wide CSV | 100 | 100 | 41 |
| train long CSV | 410 unique documents | 10,545 rows | 41 including five metadata fields |
| test long CSV | 100 unique documents | 2,556 rows | 41 including five metadata fields |

The split is contract-level with `random_state=42` in
`data/scripts/dataset/split_cuad.py`. Verified train/test document overlap is
`0`.

## Classification data

The five metadata categories (`Document Name`, `Parties`, `Agreement Date`,
`Effective Date`, `Expiration Date`) are retained in long CSVs but marked with
`is_metadata=True`. Substantive training rows are `7,004` and substantive test
rows are `1,679`. The runtime label loader excludes metadata and resolves `36`
CUAD labels from the train CSV.

## Indexed and embedded data

`data/embeddings/train_embeddings.json` reports model `embed-english-v3.0`,
`7,004` vectors, and dimension `1,024`. `train_metadata.jsonl` has `7,004`
records, `383` distinct source documents, and no metadata rows. The current
`cuad_train` Qdrant collection also contains `7,004` points from `383` documents
and `36` labels. Test rows are not indexed in the inspected current payloads.

## Legal Knowledge Base data

The Legal Knowledge Base is not a CUAD split and does not use CUAD QA pairs.
It is sourced from `17` curated Markdown files under
`backend/data/legal_knowledge`, excluding three documentation-only files.
The current source chunker calculates `19` chunks from those files, while the
stored `legal_knowledge` collection contains `30` points. This is a persisted
collection discrepancy and was not corrected during this audit.

## Runtime and evaluation data

An uploaded PDF or TXT is runtime input; it is not added to the CUAD index.
Existing diagnostics under `artifacts/diagnostics` are evaluation records, not
active training data. The older `data/metadata/rag_pipeline_results.json`
reports a historical `5,449`-point collection and is stale relative to the
current `7,004`-point store; current service code does not import it.

