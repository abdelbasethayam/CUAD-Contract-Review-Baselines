# CUAD data quality and classification policy

## Scope

This repository uses CUAD v1 master_clauses.csv as the source for clause classification. CUAD v1 contains 510 contracts, 41 annotation categories, and 13,000+ expert annotations. The original CUAD task is per-category span extraction: each category is asked independently which parts of a contract should be highlighted. The Atticus paper documents this task structure. 

The raw source is therefore treated as immutable ground truth for this project. Cleaning creates derived model-input text; it does not overwrite or relabel CUAD annotations.

## Audit results for the current source

The supplied master_clauses.csv has:

- 510 contracts and 83 columns: Filename plus 41 context columns and 41 matching -Answer columns.
- 36 substantive clause categories after separating the five contract-metadata fields: Document Name, Parties, Agreement Date, Effective Date, Expiration Date.
- 13,101 total extracted spans including metadata, of which 8,683 are substantive clause spans.
- 0 malformed span-list cells and 0 missing text/answer column pairs.
- 510 unique contract filenames and a contract-disjoint 410/100 split with seed 42, producing 7,004 train and 1,679 test substantive clause rows.

The split is contract-disjoint, so no contract identifier appears on both sides. However, repeated boilerplate text exists across different contracts: normalized exact-text hashes occur in both train and test and affect 40 test rows. This is retained for benchmark compatibility and should be reported as text-overlap rather than treated as annotation corruption.

## Critical annotation finding

The same normalized text inside one contract can carry more than one CUAD category. In this source:

- 770 same-contract/same-text groups contain multiple labels.
- 1,719 substantive rows (19.80%) are in such groups.
- A forced single-label classifier has an exact same-text theoretical ceiling of about 87.43% on the test split under the current 1-label-per-row formulation.

This is not a cleaning defect. It follows from the CUAD task structure, where categories are independently annotated. The dataset documentation also gives examples where one license clause may correspond to multiple categories.

### Modeling implication

For a faithful CUAD formulation, model each category independently or use a multi-label target representation.

For the project's existing single-label classifier, keep the "main legal function" framing, but:

1. Do not delete overlapping rows.
2. Report the conflict-aware ceiling.
3. Add an evaluation on the unambiguous subset.
4. Treat the multi-label overlap flag as an ambiguity indicator, not a corrected label.
5. Do not claim that single-label accuracy is equivalent to the original CUAD extraction benchmark.

## Two annotation QC anomalies

There are two rows where a binary supplementary answer is Yes but the corresponding context list is empty:

- GarrettMotion... / Insurance
- HALITRON... / Third Party Beneficiary

These are preserved exactly as supplied. The answer field is a supplementary contract-level annotation; it is not a replacement for the extracted clause text and must not be fed into the classifier.

## Text preprocessing policy

The model-ready derivative uses a conservative transformation:

- Unicode NFC normalization.
- Removal of invisible soft-hyphen / zero-width formatting characters.
- Curly-quote normalization.
- Whitespace normalization.
- No stemming or stop-word removal.
- No arbitrary minimum-length deletion.
- No aggressive punctuation changes.
- No abbreviation expansion in the saved ground-truth text.
- Raw text remains available in clause_text_raw.

This is intentionally less destructive than using the retrieval/LLM advanced_preprocess function as a ground-truth transformation. Evidence rendering and source-span fidelity should always use the raw clause text.

## Important existing pipeline fix

The current SFT preparation helper used to remove every clause with length <= 20, which deletes the valid Governing Law example South Dakota. The filter is removed.

The repository's legacy data helper scripts also had a path-layout mismatch (dataset/... versus the current data/... and output/... layout). The validation branch aligns those paths so rerunning preprocessing is reproducible.

## Retrieval recommendation

Do not deduplicate the supervised training annotations just because text repeats. Repeated labels are part of the CUAD signal.

For a retrieval index, however, repeated boilerplate can overweight the neighborhood. A separate retrieval-index policy can deduplicate or cap identical normalized (clause_text, clause_type) pairs and/or cap repeats from the same document, while preserving the full supervised dataset.

## Recommended evaluation

For the research result, report at least:

- overall single-label Accuracy and Macro-F1 on the existing contract-disjoint test set;
- per-label support and a low-support flag for categories with test n < 10;
- the unambiguous-subset result (rows with multi_label_overlap = False);
- normalized exact-text overlap rate between train and test;
- Recall@K of the retrieval shortlist before LLM classification.

For the next phase, preserve the classification output as evidence-linked clause records and do risk reasoning separately. Do not use the CUAD answer fields as a risk ground truth: they answer category-specific extraction questions rather than whether a clause is commercially risky. CUAD's own paper distinguishes clause extraction from the later, highly contextual risk/counseling stage.
