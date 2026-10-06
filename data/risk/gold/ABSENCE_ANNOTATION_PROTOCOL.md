# Absence and missing-protection gold protocol

This queue evaluates false negatives separately from clause-level risk classification.
NOT_FOUND_BY_SEARCH is a candidate state, never proof that a protection is legally absent.

## Annotation unit

`(contract_id, clause_type, check_id)` where the classifier/search did not locate a clause-family candidate.
Annotators inspect the full supplied contract and label:

- `adjudicated_presence`: PRESENT / NOT_FOUND / NOT_APPLICABLE / UNCERTAIN
- `adjudicated_risk`: YES / NO / UNCERTAIN, only when the check is applicable
- `adjudicated_risk_type`: concrete missing protection or exposure
- `adjudicated_evidence`: exact contract quote when a positive finding has positive textual evidence; for true absence, record the search basis instead
- `notes`: factual/jurisdictional assumptions

## Gold isolation

Use the same deterministic calibration/development/locked_test partitions as the main gold set.
The locked test partition must not tune search keywords, classifier thresholds, prompts, or calibration.

## Scientific use

Report clause-family recall and missing-protection detection separately. Never count NOT_FOUND_BY_SEARCH as a true negative without human review.