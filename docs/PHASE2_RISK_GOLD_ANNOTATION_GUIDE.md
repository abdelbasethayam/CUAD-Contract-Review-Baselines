# Risk-gold annotation guide

**Version:** 1.0.0  
**Status:** Annotation protocol; no gold records have been approved yet.

## Unit of annotation

One record represents one rule/issue decision for one contract and the stated buyer/customer (or other declared) perspective. A single contract may have many records, but all records from that contract and near-duplicate template family must remain in the same evaluation split.

## What reviewers label

- `CLAUSE_PRESENCE`: whether the relevant clause concept occurs in the contract.
- `COMMERCIAL_REVIEW_TRIGGER`: whether the exact text creates a plausible commercial concern under the stated perspective. This is not a legal conclusion.
- `CROSS_CLAUSE_CONFLICT`: whether two or more cited clauses create an interaction requiring review.
- `LEGAL_PROPOSITION`: a proposition about legal effect, validity, enforceability, or a legal obligation. Use this only when governing law and the relevant date are verified and the authority pinpoint is reviewed.

The final decision must be one of `POTENTIAL_RISK`, `NO_RISK`, `INSUFFICIENT_EVIDENCE`, or `NOT_APPLICABLE`. Do not use a severity label as a substitute for the decision.

## Evidence rules

1. Every positive risk decision must include at least one exact, contiguous quote from the normalized text of the uploaded contract, with clause ID, zero-based start offset, exclusive end offset, quote SHA-256, and page if available.
2. The quote must support the stated finding; a citation to an external law or a paraphrase is not contract evidence.
3. `NO_RISK` can be supported by a quoted protective control or by a documented full-document scan showing absence. Do not turn missing evidence into `NO_RISK`.
4. Use `INSUFFICIENT_EVIDENCE` when text, context, governing law, relevant dates, or exceptions are unresolved.
5. Use `NOT_APPLICABLE` only with a specific rationale.
6. A legal-proposition record must include verified governing law, a relevant date, and authority pinpoints whose jurisdiction and effective-date status have been reviewed for that period. An authority marked as a URL-only lead, currentness-review-required, or republication-host-only cannot support a final legal-proposition label until those gaps are cleared.

## Independent review and adjudication

- Reviewer 1 and Reviewer 2 must label independently and include a rationale and timestamp.
- A separate adjudicator resolves disagreement and records the final decision, rationale, timestamp, and adjudication reference.
- Reviewer IDs must be distinct. The adjudicator must not be either reviewer.
- Do not copy the model's prediction into the human label. Annotators should not see model confidence before recording their independent decisions.
- Preserve disagreement; do not silently overwrite the original labels.

## Dataset split and leakage control

- Deduplicate exact documents and group related templates, amendments, affiliates, and near-duplicates before splitting.
- A contract ID and its near-duplicate group may appear in only one of TRAIN, CALIBRATION, or TEST.
- Freeze the test set and do not tune rules, prompts, thresholds, or calibration on it.
- Record dataset version, annotation-guide version, source-document SHA-256, and normalized-text SHA-256.
- Store contract text in a controlled dataset location; do not commit confidential contract text or personally identifying content to the repository.

## Status and publication rule

The schema and synthetic unit tests validate record structure only. Synthetic examples are test fixtures, not gold data. A project-specific gold set does not exist until the records have been collected from permitted contracts, independently reviewed, adjudicated, de-identified where required, split by contract/template, and frozen. Do not report risk accuracy, calibrated confidence, or legal correctness before that stage.
