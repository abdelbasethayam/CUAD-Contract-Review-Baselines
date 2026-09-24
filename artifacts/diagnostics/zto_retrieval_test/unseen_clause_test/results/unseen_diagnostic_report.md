# ZTO Unseen-Clause Retrieval Diagnostic

Status: **INCOMPLETE**

## 1. Environment

The retrieval environment was not reached. The experiment stopped during the required segmentation-source step.

- Target parser: `docling`
- Target contract: `ZtoExpressCaymanInc_20160930_F-1_EX-10.10_9752871_EX-10.10_Transportation Agreement`
- Cohere embedding model: not queried
- Qdrant collection: not queried
- Final Top-K: not evaluated

## 2. Clause Selection

No clauses were evaluated. The latest persisted Docling-based ZTO segmentation artifact was not available in the repository. The isolated diagnostic attempted to invoke the existing `segment_document()` implementation with `CONTRACT_PARSER=docling`.

## 3. Leakage Control

Leakage filtering was not reached because no new segmented query clauses were produced.

## 4. Per-Clause Retrieval Results

No results. The experiment stopped before generating query embeddings or querying Qdrant.

## 5. Aggregate Results

- Evaluated clauses: `0`
- Unmapped clauses: `0`
- Excluded from evaluation: `0`
- Retrieval failures: `0`
- Diagnostic status: `INCOMPLETE`

## 6. Category-Level Results

Liquidated Damages and Insurance were not evaluated because their newly segmented query text was unavailable.

## 7. Diagnosis

The existing Docling parser could not initialize its layout pipeline:

```text
ModuleNotFoundError: No module named 'torch'
```

The old Cooley segmentation output and the fallback parser were intentionally not used because they would not represent the required latest Docling-based segmentation.

## 8. Final Conclusion

1. Retrieval generalization from newly segmented ZTO clauses: **not determined**.
2. Correct CUAD category after excluding ZTO: **not determined**.
3. Ranking ambiguity: **not determined**.
4. Reliably retrieved categories: **none evaluated**.
5. Proceed to Ollama classification diagnostic: **no**, not from this incomplete experiment.
6. Evidence to modify embeddings/retrieval: **none**; retrieval was not executed.

## Safety Check

- Only files under `diagnostics/zto_retrieval_test/unseen_clause_test/` were created or modified for this experiment.
- No production source code changed.
- No `.env` changed.
- No Qdrant collection or point changed.
- No embedding artifact changed or regenerated.
- No segmentation code changed.
- No Cohere retrieval query was made.
- No Ollama call was made.
- No Git commit was created.
