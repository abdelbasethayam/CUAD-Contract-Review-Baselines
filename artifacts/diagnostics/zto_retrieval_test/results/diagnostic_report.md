# ZTO CUAD Retrieval Diagnostic

Status: **LEAKAGE_AFFECTED**. The ZTO document is present in the current training index.

## 1. Environment

- Embedding model: `embed-english-v3.0`
- Embedding dimension: `1024`
- Qdrant collection: `cuad_train`
- Qdrant vector dimension: `1024`
- Retrieval Top-K: `5`
- Timestamp: `2026-09-09T23:18:22.567803+00:00`
- Label mapping: Qdrant payload field `clause_type` is the CUAD label/category.

## 2. Ground Truth

The five evaluated queries are exact annotated clause records from the local CUAD-derived metadata for the ZTO document.

| Clause | Ground Truth |
|---|---|
| Liquidated damages — termination | Liquidated Damages |
| Liquidated damages — vehicle delay | Liquidated Damages |
| Vehicle/personnel insurance | Insurance |
| Third-party liability insurance | Insurance |
| Vehicle insurance requirement | Insurance |

## 3. Per-Clause Results

| Clause | Ground Truth | Top-1 | Top-1 Score | Correct in Top-3 | Correct in Top-5 | Correct Rank | Same ZTO Document? |
|---|---|---:|---:|---|---|---:|---|
| liquidated_damages_termination | Liquidated Damages | Liquidated Damages | 0.877751 | Yes | Yes | 1 | Yes |
| liquidated_damages_vehicle_delay | Liquidated Damages | Liquidated Damages | 0.874238 | Yes | Yes | 1 | Yes |
| insurance_vehicle_personnel | Insurance | Insurance | 0.888582 | Yes | Yes | 1 | Yes |
| insurance_third_party | Insurance | Insurance | 0.840671 | Yes | Yes | 1 | Yes |
| insurance_vehicle | Insurance | Insurance | 0.831823 | Yes | Yes | 1 | Yes |

## 4. Aggregate Results

- Top-1 hit rate: **100.0%**
- Top-3 hit rate: **100.0%**
- Top-5 hit rate: **100.0%**
- Any same-document result: **5/5 (100.0%)**
- Top-1 same-document result: **5/5 (100.0%)**
- Clauses with only other-document results: **0/5**

### Label-level summary

| Ground Truth Label | Tested Clauses | Top-1 Hit Rate | Top-3 Hit Rate | Top-5 Hit Rate | Main Competitors |
|---|---:|---:|---:|---:|---|
| Insurance | 3 | 100.0% | 100.0% | 100.0% | Most Favored Nation, Liquidated Damages |
| Liquidated Damages | 2 | 100.0% | 100.0% | 100.0% | None |

## 5. Diagnosis

The decision for each clause is recorded in `retrieval_results.json`. A result with the correct label absent from Top-5 is a retrieval failure; a result with the correct label below competing labels is a ranking weakness; a Top-1 correct result leaves classifier behavior unresolved. Any same-document result is leakage-affected.

## 6. Final Conclusion

1. Retrieval failure for these exact annotated queries: **No failure observed; all 5/5 returned the correct label at rank 1.**
2. Correct CUAD label usually present in Top-5: **Yes, 5/5 (100%).**
3. Ranking ambiguity: **Not observed for these queries; the correct label was rank 1 in every case.** This is not a clean generalization result because each query exactly matches an indexed ZTO record.
4. Same-document leakage: **5/5 (100%) had a same-ZTO result at rank 1.**
5. Evidence to change retrieval/embeddings now: **No.** The experiment shows successful exact self-retrieval, but it does not justify changes or prove performance on unseen segmented clauses.

## Safety Check

- Only files under `diagnostics/zto_retrieval_test/` were created or modified.
- No production source file was modified.
- No `.env` file was modified.
- The original Qdrant collection was not modified; the query used an isolated snapshot.
- No embedding artifact was modified or regenerated.
- No Ollama call was made.
- No Git commit was created.
