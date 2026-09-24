# Hybrid Retrieval: BM25 + Vector Search + RRF

Status: **COMPLETE**

## 1. Experiment Objective

Test whether combining semantic Vector Top-20 retrieval with lexical BM25 Top-20 retrieval and Reciprocal Rank Fusion improves retrieval coverage on the fixed 10-row benchmark.

## 2. Research Hypothesis

Hybrid retrieval may recover CUAD categories missed by vector-only search, especially where lexical clause terms are informative.

## 3. Controlled Variables

The fixed rows, training corpus, Cohere query embeddings, Qdrant collection, distance metric, Ollama model, classification-fix, prompt, UNKNOWN handling, and Top-5 evaluation target remained fixed.

## 4. Baseline

The comparison baseline is the completed `fixed_10_classification_experiment` run over the same official 10-row selection.
- Recall@1: `0.5000`; Recall@3: `0.6000`; Recall@5: `0.6000`.
- MRR: `0.5500`; classification accuracy: `0.4000`.
- Retrieval misses: `4`; classification errors: `1`; invalid/out-of-candidate responses: `1`; UNKNOWN abstentions: `0`; pipeline errors: `0`.

## 5. Independent Variable

Only retrieval changed: Vector Top-20 plus BM25 Top-20 fused with RRF, followed by final Top-5 selection.

## 6. Architecture

Before: query text -> Cohere search_query embedding -> Qdrant Vector Top-5 -> existing candidate-constrained classifier.

After: query text -> Cohere search_query embedding -> Qdrant Vector Top-20 + BM25 Top-20 over training clauses -> RRF (k=60) -> final Top-5 -> unchanged candidate-constrained classifier.

## 7. BM25 and RRF Configuration

- Corpus: `data/splits/train/master_clauses_train.csv`; `7004` substantive training records.
- Tokenizer: `lowercase ASCII alphanumeric tokens via [a-z0-9]+`.
- BM25 parameters: `k1=1.5`, `b=0.75`.
- Vector depth: `20`; BM25 depth: `20`.
- RRF formula: `RRF(d) = sum(1 / (60 + rank(d)))`, with 1-based ranks.
- Final fused output: Top-`5`.
- Record identity: the existing UUID5 Qdrant point identity derived from document ID, clause type, and training source row index; duplicate records are merged only when this identity matches.

## 8. Leakage Verification

- BM25 source is training data only: `True`.
- Fixed test identities in BM25 corpus: `0`.
- Fixed test texts in BM25 corpus: `0`.
- Test rows ingested into Qdrant: `False`.

## 9. Fixed Benchmark

Exactly the ten rows in `diagnostics/fixed_10_classification_baseline/selected_10_rows.json` were used; no resampling occurred.

## 10. Per-Row Results

| Row | Ground Truth | Vector GT Rank | BM25 GT Rank | Hybrid GT Rank | Vector Top-5 | BM25 Top-5 | Hybrid Top-5 | Prediction | Status | Correct |
|---|---|---:|---:|---:|---|---|---|---|---|---|
| `fixed-10-01` | `Warranty Duration` | 1 | 1 | 1 | Yes | Yes | Yes | `Warranty Duration` | `VALID_CANDIDATE` | Yes |
| `fixed-10-02` | `Price Restrictions` | 15 | - | 29 | No | No | No | `Termination For Convenience` | `VALID_CANDIDATE` | No |
| `fixed-10-03` | `Non-Compete` | 1 | 2 | 1 | Yes | Yes | Yes | `Non-Compete` | `VALID_CANDIDATE` | Yes |
| `fixed-10-04` | `Rofr/Rofo/Rofn` | - | - | - | No | No | No | `License Grant` | `VALID_CANDIDATE` | No |
| `fixed-10-05` | `Competitive Restriction Exception` | - | - | - | No | No | No | `License Grant` | `VALID_CANDIDATE` | No |
| `fixed-10-06` | `Joint Ip Ownership` | 2 | 12 | 2 | Yes | No | Yes | `Joint Ip Ownership` | `VALID_CANDIDATE` | Yes |
| `fixed-10-07` | `Revenue/Profit Sharing` | 1 | 1 | 1 | Yes | Yes | Yes | `Revenue/Profit Sharing` | `VALID_CANDIDATE` | Yes |
| `fixed-10-08` | `Termination For Convenience` | 1 | 1 | 1 | Yes | Yes | Yes | `Termination For Convenience` | `VALID_CANDIDATE` | Yes |
| `fixed-10-09` | `Audit Rights` | 1 | 1 | 1 | Yes | Yes | Yes | `UNKNOWN` | `OUT_OF_CANDIDATE` | No |
| `fixed-10-10` | `Affiliate License-Licensor` | - | 17 | 18 | No | No | No | `License Grant` | `VALID_CANDIDATE` | No |

### Top-5 Category Details

- `fixed-10-01` Vector: 1:Warranty Duration, 2:Warranty Duration, 3:Warranty Duration, 4:Warranty Duration, 5:Warranty Duration
  BM25: 1:Warranty Duration, 2:Warranty Duration, 3:Warranty Duration, 4:Post-Termination Services, 5:Warranty Duration
  Hybrid/RRF: 1:Warranty Duration, 2:Warranty Duration, 3:Warranty Duration, 4:Warranty Duration, 5:Warranty Duration
- `fixed-10-02` Vector: 1:Revenue/Profit Sharing, 2:Notice Period To Terminate Renewal, 3:Renewal Term, 4:Minimum Commitment, 5:Volume Restriction
  BM25: 1:Renewal Term, 2:Termination For Convenience, 3:Warranty Duration, 4:Warranty Duration, 5:Post-Termination Services
  Hybrid/RRF: 1:Post-Termination Services, 2:Revenue/Profit Sharing, 3:Renewal Term, 4:Notice Period To Terminate Renewal, 5:Termination For Convenience
- `fixed-10-03` Vector: 1:Non-Compete, 2:Non-Compete, 3:Covenant Not To Sue, 4:No-Solicit Of Customers, 5:Non-Compete
  BM25: 1:Insurance, 2:Non-Compete, 3:No-Solicit Of Customers, 4:No-Solicit Of Employees, 5:Non-Compete
  Hybrid/RRF: 1:Non-Compete, 2:Non-Compete, 3:Insurance, 4:Non-Compete, 5:Non-Compete
- `fixed-10-04` Vector: 1:Non-Transferable License, 2:Non-Transferable License, 3:Non-Transferable License, 4:License Grant, 5:License Grant
  BM25: 1:Exclusivity, 2:License Grant, 3:Irrevocable Or Perpetual License, 4:License Grant, 5:License Grant
  Hybrid/RRF: 1:Irrevocable Or Perpetual License, 2:License Grant, 3:Exclusivity, 4:Non-Transferable License, 5:License Grant
- `fixed-10-05` Vector: 1:Ip Ownership Assignment, 2:License Grant, 3:Affiliate License-Licensor, 4:License Grant, 5:Exclusivity
  BM25: 1:Non-Transferable License, 2:License Grant, 3:Non-Compete, 4:Non-Compete, 5:Non-Compete
  Hybrid/RRF: 1:License Grant, 2:Non-Transferable License, 3:Ip Ownership Assignment, 4:License Grant, 5:License Grant
- `fixed-10-06` Vector: 1:Ip Ownership Assignment, 2:Joint Ip Ownership, 3:Ip Ownership Assignment, 4:Joint Ip Ownership, 5:Joint Ip Ownership
  BM25: 1:Ip Ownership Assignment, 2:Ip Ownership Assignment, 3:Ip Ownership Assignment, 4:Ip Ownership Assignment, 5:Ip Ownership Assignment
  Hybrid/RRF: 1:Ip Ownership Assignment, 2:Joint Ip Ownership, 3:Joint Ip Ownership, 4:Ip Ownership Assignment, 5:Ip Ownership Assignment
- `fixed-10-07` Vector: 1:Revenue/Profit Sharing, 2:Revenue/Profit Sharing, 3:Revenue/Profit Sharing, 4:Revenue/Profit Sharing, 5:Minimum Commitment
  BM25: 1:Revenue/Profit Sharing, 2:Minimum Commitment, 3:Revenue/Profit Sharing, 4:Minimum Commitment, 5:Minimum Commitment
  Hybrid/RRF: 1:Revenue/Profit Sharing, 2:Minimum Commitment, 3:Revenue/Profit Sharing, 4:Revenue/Profit Sharing, 5:Revenue/Profit Sharing
- `fixed-10-08` Vector: 1:Termination For Convenience, 2:No-Solicit Of Employees, 3:Termination For Convenience, 4:Termination For Convenience, 5:Termination For Convenience
  BM25: 1:Termination For Convenience, 2:Termination For Convenience, 3:Change Of Control, 4:Termination For Convenience, 5:Termination For Convenience
  Hybrid/RRF: 1:Termination For Convenience, 2:Termination For Convenience, 3:Termination For Convenience, 4:Change Of Control, 5:No-Solicit Of Employees
- `fixed-10-09` Vector: 1:Audit Rights, 2:Audit Rights, 3:Audit Rights, 4:Audit Rights, 5:Audit Rights
  BM25: 1:Audit Rights, 2:Audit Rights, 3:Audit Rights, 4:Audit Rights, 5:Audit Rights
  Hybrid/RRF: 1:Audit Rights, 2:Audit Rights, 3:Audit Rights, 4:Audit Rights, 5:Audit Rights
- `fixed-10-10` Vector: 1:Irrevocable Or Perpetual License, 2:License Grant, 3:License Grant, 4:Irrevocable Or Perpetual License, 5:License Grant
  BM25: 1:Irrevocable Or Perpetual License, 2:License Grant, 3:License Grant, 4:Irrevocable Or Perpetual License, 5:Irrevocable Or Perpetual License
  Hybrid/RRF: 1:Irrevocable Or Perpetual License, 2:Irrevocable Or Perpetual License, 3:License Grant, 4:License Grant, 5:Irrevocable Or Perpetual License

## 11. Retrieval Recovery Analysis

- `fixed-10-02`: `VECTOR_FOUND`; Vector Top-20 rank `15`, BM25 Top-20 rank `None`, Hybrid rank `29`.
- `fixed-10-04`: `BOTH_MISSED`; Vector Top-20 rank `None`, BM25 Top-20 rank `None`, Hybrid rank `None`.
- `fixed-10-05`: `BOTH_MISSED`; Vector Top-20 rank `None`, BM25 Top-20 rank `None`, Hybrid rank `None`.
- `fixed-10-10`: `BM25_FOUND_BUT_RRF_DID_NOT_PROMOTE`; Vector Top-20 rank `None`, BM25 Top-20 rank `17`, Hybrid rank `18`.
  BM25 retrieved useful evidence, but the RRF configuration did not promote it sufficiently into the final Top-5.

## 12. Aggregate Metrics

- Recall@1: `0.5000`
- Recall@3: `0.6000`
- Recall@5: `0.6000`
- MRR: `0.5590`
- Classification accuracy: `0.5000`
- Retrieval misses: `4`
- Classification errors: `0`
- Invalid/out-of-candidate responses: `1`
- Out-of-Top-5 predictions: `0`
- UNKNOWN count: `0`
- Pipeline errors: `0`
- Previous retrieval misses recovered by hybrid Top-5: `0`

`UNKNOWN` is counted only when production parsing reports intentional `UNKNOWN` abstention. An out-of-candidate or malformed Ollama response is rejected by production parsing and exposed as final prediction `UNKNOWN`, but is counted separately as invalid. The out-of-Top-5 metric counts only non-UNKNOWN labels that remain absent from the final candidate set.

## 13. Baseline vs Hybrid

| Metric | Classification Fix | Hybrid Retrieval | Change |
|---|---:|---:|---:|
| recall_at_1 | 0.5000 | 0.5000 | +0.0000 |
| recall_at_3 | 0.6000 | 0.6000 | +0.0000 |
| recall_at_5 | 0.6000 | 0.6000 | +0.0000 |
| mrr | 0.5500 | 0.5590 | +0.0090 |
| classification_accuracy | 0.4000 | 0.5000 | +0.1000 |
| retrieval_miss_count | 4.0000 | 4.0000 | +0.0000 |
| classification_error_count | 1.0000 | 0.0000 | -1.0000 |
| ollama_selected_label_absent_from_top5_count | 0.0000 | 0.0000 | +0.0000 |
| unknown_count | 0.0000 | 0.0000 | +0.0000 |
| pipeline_error_count | 0.0000 | 0.0000 | +0.0000 |
| retrieval_recovery_count | 0.0000 | 0.0000 | +0.0000 |

## 14. Classification Impact

The existing candidate-constrained classifier was reused without modification. Hybrid accuracy increased from 4/10 to 5/10 because `fixed-10-07` changed from the valid but incorrect candidate `Minimum Commitment` to the correct candidate `Revenue/Profit Sharing`; both runs had the same two candidate labels, so the change reflects the changed retrieved examples/order and/or Ollama run variability rather than improved retrieval coverage. `fixed-10-09` remained an out-of-candidate response: raw `Obligations` was rejected and exposed as final `UNKNOWN`. Retrieval misses remain distinct from classifier errors.

## 15. Limitations

This is a 10-row pilot and cannot establish generalization. BM25 tokenization is intentionally simple, and RRF ranking is sensitive to the chosen depth and k value. The Qdrant retriever payload does not expose source point IDs through the existing production helper, so this experiment uses the UUID5 identity available from the indexed training-record construction for fusion alignment.

## 16. Conclusion

Hybrid Recall@5 was `0.6000` versus `0.6000` for classification-fix. The hypothesis is INCONCLUSIVE ON THIS PILOT for this fixed 10-row retrieval-coverage test.

## Safety

Only hybrid retrieval experiment files are intended for this branch. Classification-fix source and baseline artifacts were not modified. No segmentation, embedding, Qdrant, Ollama, risk-analysis, or test-data writes were performed.
