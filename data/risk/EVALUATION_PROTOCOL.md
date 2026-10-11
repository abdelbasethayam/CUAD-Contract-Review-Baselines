# Phase 2 Risk Evaluation Protocol

## Ground-truth hierarchy
1. **Human/expert benchmark ground truth:** public expert-annotated datasets whose task definitions match the evaluated capability (for example ContractEval for clause-level risk/evidence behavior; ACORD for retrieval; ContractNLI for contract evidence/NLI). These support external validity.
2. **Project machine-adjudicated silver:** held-out CUAD clauses labeled by an independent judge model plus skeptical verification. Use for diagnostics and model/playbook analysis only.
3. **Playbook-derived outputs:** policy/rule outputs from `commercial_clause_risk_playbook.json`. Never use as ground truth.

## Closed-test rule
The project's locked test subset must not be used to tune prompts, playbook wording, retrieval parameters, thresholds, calibration, or model selection.

## Reporting
Report risk detection, abstention/uncertainty, evidence validity, severity, and contract-cluster uncertainty separately. Do not convert deterministic severity scores into probabilities. Do not claim legal correctness or legal advice.

## Limitation
Without qualified human adjudicators for the project's custom 37-target risk taxonomy, the project cannot honestly claim a human-gold accuracy estimate for that taxonomy. Any internal number derived from the silver set must be labeled machine-adjudicated/silver and interpreted accordingly.


## Risk-domain assignment policy (playbook v1.1)

Every clause-level, cross-clause, and document-level check has one canonical `risk_domain` selected from the ten domains in `backend/data/legal_knowledge/risk_taxonomy.json`. The check's declared playbook domain is the primary aggregation/routing label. A more specific legacy label is retained as `risk_subdomain`. Keyword-based taxonomy matches are recorded as `taxonomy_suggested_domains` for review and can be a fallback only when a check has no declared domain; they must not silently override an explicit playbook domain. Neither a taxonomy match nor a playbook rule constitutes contract evidence.
