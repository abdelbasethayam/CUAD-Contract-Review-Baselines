# Fixed 10-Row Candidate-Constrained Classification Experiment

Status: **COMPLETE**

## 1. Objective

Test whether constraining Ollama to unique valid categories present in the unchanged Qdrant Top-5, with explicit UNKNOWN abstention, reduces classification-layer errors and out-of-candidate predictions.

## 2. Baseline Configuration

- Baseline commit: `969bd75`
- Test source: `data/splits/test/master_clauses_test.csv`
- Fixed seed: `20260910`
- Embedding model/dimension: `embed-english-v3.0` / `1024`
- Qdrant collection/distance: `cuad_train` / `Cosine`
- Retrieval Top-K: `5`
- Ollama model: `llama3.2:3b`

## 3. Exact Benchmark Dataset

The experiment reuses the baseline `selected_10_rows.json` without resampling.

| Row | Original Row | Ground Truth | Document ID |
|---|---:|---|---|
| `fixed-10-01` | 1906 | `Warranty Duration` | `LiquidmetalTechnologiesInc_20200205_8-K_EX-10.1_11968198_EX-10.1_Development Agreement.pdf` |
| `fixed-10-02` | 669 | `Price Restrictions` | `ENTERPRISEPRODUCTSPARTNERSLP_07_08_1998-EX-10.3-TRANSPORTATION CONTRACT.PDF` |
| `fixed-10-03` | 1086 | `Non-Compete` | `HYPERIONSOFTWARECORP_09_28_1994-EX-10.47-EXCLUSIVE DISTRIBUTOR AGREEMENT.PDF` |
| `fixed-10-04` | 147 | `Rofr/Rofo/Rofn` | `ANIXABIOSCIENCESINC_06_09_2020-EX-10.1-COLLABORATION AGREEMENT.PDF` |
| `fixed-10-05` | 432 | `Competitive Restriction Exception` | `RandWorldwideInc_20010402_8-KA_EX-10.2_2102464_EX-10.2_Co-Branding Agreement.pdf` |
| `fixed-10-06` | 1883 | `Joint Ip Ownership` | `LiquidmetalTechnologiesInc_20200205_8-K_EX-10.1_11968198_EX-10.1_Development Agreement.pdf` |
| `fixed-10-07` | 2096 | `Revenue/Profit Sharing` | `CYBERIANOUTPOSTINC_07_09_1998-EX-10.13-PROMOTION AGREEMENT.PDF` |
| `fixed-10-08` | 1238 | `Termination For Convenience` | `THERAVANCEBIOPHARMA,INC_05_08_2020-EX-10.2-SERVICE AGREEMENT.PDF` |
| `fixed-10-09` | 2157 | `Audit Rights` | `PHREESIA,INC_05_28_2019-EX-10.18-STRATEGIC ALLIANCE AGREEMENT.PDF` |
| `fixed-10-10` | 2246 | `Affiliate License-Licensor` | `ArmstrongFlooringInc_20190107_8-K_EX-10.2_11471795_EX-10.2_Intellectual Property Agreement.pdf` |

## 4. Classification Change

The classification layer now derives unique valid candidate labels from the unchanged retrieved Top-5. The prompt exposes only those candidates and allows UNKNOWN when none is appropriate. The parser accepts only JSON labels in the candidate set, records explicit UNKNOWN, and records malformed or out-of-candidate responses instead of silently accepting them.

## 5. Intentionally Unchanged

Retrieval scoring, query embeddings, Qdrant data, Top-K, segmentation, risk analysis, Ollama model/configuration, and the fixed benchmark rows were not changed.

## 6. Per-Row Comparison

| Row | Ground Truth | Baseline Prediction | New Prediction | GT Rank | GT in Top-5 | Baseline Correct | New Correct | Result |
|---|---|---|---|---:|---|---|---|---|
| `fixed-10-01` | `Warranty Duration` | `Warranty Duration` | `Warranty Duration` | 1 | Yes | Yes | Yes | `UNCHANGED_CORRECT` |
| `fixed-10-02` | `Price Restrictions` | `Volume Restriction` | `Volume Restriction` | - | No | No | No | `UNCHANGED_INCORRECT` |
| `fixed-10-03` | `Non-Compete` | `Non-Compete` | `Non-Compete` | 1 | Yes | Yes | Yes | `UNCHANGED_CORRECT` |
| `fixed-10-04` | `Rofr/Rofo/Rofn` | `Non-Transferable License` | `Non-Transferable License` | - | No | No | No | `UNCHANGED_INCORRECT` |
| `fixed-10-05` | `Competitive Restriction Exception` | `License Grant` | `License Grant` | - | No | No | No | `UNCHANGED_INCORRECT` |
| `fixed-10-06` | `Joint Ip Ownership` | `Ip Ownership Assignment` | `Joint Ip Ownership` | 2 | Yes | No | Yes | `IMPROVED` |
| `fixed-10-07` | `Revenue/Profit Sharing` | `License Grant` | `Minimum Commitment` | 1 | Yes | No | No | `UNCHANGED_INCORRECT` |
| `fixed-10-08` | `Termination For Convenience` | `Termination For Convenience` | `Termination For Convenience` | 1 | Yes | Yes | Yes | `UNCHANGED_CORRECT` |
| `fixed-10-09` | `Audit Rights` | `Audit Rights` | `UNKNOWN` | 1 | Yes | Yes | No | `REGRESSED` |
| `fixed-10-10` | `Affiliate License-Licensor` | `License Grant` | `License Grant` | - | No | No | No | `UNCHANGED_INCORRECT` |

### Retrieved Top-5 Categories

- `fixed-10-01`: 1. Warranty Duration (0.530836), 2. Warranty Duration (0.528245), 3. Warranty Duration (0.514186), 4. Warranty Duration (0.514101), 5. Warranty Duration (0.508124)
- `fixed-10-02`: 1. Revenue/Profit Sharing (0.469577), 2. Notice Period To Terminate Renewal (0.469453), 3. Renewal Term (0.469453), 4. Minimum Commitment (0.448818), 5. Volume Restriction (0.441971)
- `fixed-10-03`: 1. Non-Compete (0.633410), 2. Non-Compete (0.585149), 3. Covenant Not To Sue (0.569864), 4. No-Solicit Of Customers (0.569448), 5. Non-Compete (0.555265)
- `fixed-10-04`: 1. Non-Transferable License (0.505184), 2. Non-Transferable License (0.505086), 3. Non-Transferable License (0.504936), 4. License Grant (0.476126), 5. License Grant (0.470096)
- `fixed-10-05`: 1. Ip Ownership Assignment (0.511572), 2. License Grant (0.506411), 3. Affiliate License-Licensor (0.492070), 4. License Grant (0.486942), 5. Exclusivity (0.484350)
- `fixed-10-06`: 1. Ip Ownership Assignment (0.587926), 2. Joint Ip Ownership (0.587926), 3. Ip Ownership Assignment (0.585409), 4. Joint Ip Ownership (0.585409), 5. Joint Ip Ownership (0.574050)
- `fixed-10-07`: 1. Revenue/Profit Sharing (0.509450), 2. Revenue/Profit Sharing (0.503446), 3. Revenue/Profit Sharing (0.501004), 4. Revenue/Profit Sharing (0.501004), 5. Minimum Commitment (0.469719)
- `fixed-10-08`: 1. Termination For Convenience (0.653160), 2. No-Solicit Of Employees (0.562221), 3. Termination For Convenience (0.556112), 4. Termination For Convenience (0.549439), 5. Termination For Convenience (0.544435)
- `fixed-10-09`: 1. Audit Rights (0.668368), 2. Audit Rights (0.656139), 3. Audit Rights (0.649333), 4. Audit Rights (0.632950), 5. Audit Rights (0.627342)
- `fixed-10-10`: 1. Irrevocable Or Perpetual License (0.753192), 2. License Grant (0.753192), 3. License Grant (0.724759), 4. Irrevocable Or Perpetual License (0.724759), 5. License Grant (0.712084)

## 7. Retrieval Metrics

- Recall@1: `0.5000` (baseline `0.5000`)
- Recall@3: `0.6000` (baseline `0.6000`)
- Recall@5: `0.6000` (baseline `0.6000`)
- MRR: `0.5500` (baseline `0.5500`)
- Rows with identical recorded retrieval: `10/10`

## 8. Classification Metrics

- Accuracy: `0.4000` (4/10; baseline `0.4000`)
- Retrieval misses: `4`
- Classification errors: `1`
- Invalid/out-of-candidate responses: `1`
- UNKNOWN/abstention: `0`
- Valid predictions outside Top-5: `0`
- Pipeline/runtime errors: `0`

## 9. Baseline vs Classification Fix

| Metric | Baseline | Classification Fix | Change |
|---|---:|---:|---:|
| recall_at_1 | 0.5000 | 0.5000 | +0.0000 |
| recall_at_3 | 0.6000 | 0.6000 | +0.0000 |
| recall_at_5 | 0.6000 | 0.6000 | +0.0000 |
| mrr | 0.5500 | 0.5500 | +0.0000 |
| classification_accuracy | 0.4000 | 0.4000 | +0.0000 |
| retrieval_miss_count | 4.0000 | 4.0000 | +0.0000 |
| classification_error_count | 2.0000 | 1.0000 | -1.0000 |
| ollama_selected_label_absent_from_top5_count | 1.0000 | 0.0000 | -1.0000 |
| unknown_count | 0.0000 | 0.0000 | +0.0000 |
| pipeline_error_count | 0.0000 | 0.0000 | +0.0000 |

## 10. Error Analysis

- Retrieval limitation: `4` rows lacked the ground-truth category in Top-5; a strict candidate-constrained classifier cannot reliably recover those labels.
- Classification limitation: `1` rows had the ground-truth category in Top-5 but received a different valid candidate.
- Invalid/out-of-candidate behavior: `1` responses were rejected by the validator.
- Abstention: `0` explicit UNKNOWN results occurred.

## 11. Interpretation

Retrieval metrics remained fixed, so any classification change is attributable to the classification layer. Candidate restriction prevents a valid prediction from being invented outside retrieved evidence, but it cannot repair retrieval misses. UNKNOWN is preferable to forcing a category when candidates are insufficient.

## 12. Limitations

This is a 10-row pilot benchmark and is not sufficient to claim generalization to the full CUAD test set. CUAD categories can overlap, and the fixed dataset provides one reference category per selected row for this controlled comparison.

## 13. Conclusion

The classification fix produced accuracy `0.4000` versus baseline `0.4000` while preserving retrieval (`10/10` rows identical). The result should be interpreted as a small controlled experiment, not a general performance claim.

## 14. Recommendation for Next Experiment

Evaluate the same candidate-constrained policy on a larger fixed benchmark and separately investigate the four retrieval misses; do not attribute those misses to Ollama classification.

## Safety

Only the classification-layer files and this diagnostic directory are intended for this experiment. Baseline artifacts and selected rows remain unchanged. No retrieval, embedding, segmentation, Qdrant, risk-analysis, `.env`, or Ollama model/configuration changes were made.
