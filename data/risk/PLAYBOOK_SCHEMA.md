# Risk playbook schema

Use the imported team checklist as the baseline. For a research-grade playbook, each check should evolve toward this structure:

| Field | Purpose |
|---|---|
| id | Stable immutable check identifier |
| risk_domain | Liability, termination, IP, etc. |
| risk_type | Concrete exposure being tested |
| perspective | customer_buyer / supplier / other |
| applies_when | Clause types, terms, or prerequisites |
| question | Atomic yes/no/unknown question |
| flag_if | Exact condition that produces a potential risk |
| do_not_flag_if | Protective or normal patterns that should not trigger |
| required_evidence | Evidence elements that must be present before a YES |
| evidence_location | clause / same-contract / document-package |
| severity_factors | Which structured dimensions matter |
| dependencies | Checks that should be evaluated jointly |
| source_ids | Legal/practice references |
| jurisdiction_scope | Jurisdictions for which guidance is intended |
| positive_examples | Curated examples if licensed |
| negative_examples | Curated non-risk examples if licensed |
| rationale | Short maintainer explanation |
| version | Versioned policy semantics |

## Ground-truth policy

Playbook checks define what to ask; they do not define truth by themselves. A production finding must remain PLAYBOOK_DERIVED or MODEL_ASSERTED until an independent gold annotation set exists.

## Evidence policy

A positive finding must carry an exact contiguous quote from the contract. Legal sources explain why the check matters but are never contract evidence.

## Severity policy

Use explicit 0–3 factors such as impact, scope, asymmetry, duration, and reversibility. Convert the resulting raw signal to LOW/MEDIUM/HIGH only after fitting an ordinal calibration model on adjudicated gold.

## Confidence policy

Never display the model's self-reported confidence as a probability. Store raw support and self-consistency separately; expose calibrated probability only from a persisted calibration curve whose version/hash is recorded in the run manifest.
