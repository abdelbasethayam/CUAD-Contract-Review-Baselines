# Phase 2 — Evidence-Grounded Contract Risk Screening

## Scope

This is a buyer/customer-side commercial-contract **review-prioritization** system. It is not legal advice and does not decide enforceability. Phase 1 classifies clause types; Phase 2 applies explicit risk predicates to the actual contract text, validates quoted evidence, detects cross-clause/document-level interactions, and produces an explainable review profile.

## End-to-end flow

    Upload PDF/TXT
      -> content-addressed analysis run
      -> document extraction + clause segmentation
      -> fragment validation (local Ollama; GPU placement inherited from server)
      -> clause embeddings
      -> Phase 1 CUAD classification using training-only Qdrant retrieval
      -> clause-level risk checks
           -> playbook QUESTION + FLAG IF
           -> deterministic indicators
           -> target clause + top-5 same-contract context
           -> separately retrieved legal/practice guidance
           -> local LLM reasoning and repeated passes
           -> exact quote validation against contract text
      -> deterministic cross-clause signals
      -> LLM cross-clause checks (10 playbook checks)
      -> LLM document-level checks (3 playbook checks)
      -> canonical domain assignment from the playbook
      -> contract-level risk aggregation and severity triage
      -> result JSON + clauses/risk CSV/JSONL + trace + manifest

The main risk prompt does **not** place an entire long contract into each model call. It uses the target clause plus up to five semantically related clauses from the same uploaded contract. Separate whole-contract checks inspect the extracted clause set for pre-defined clause-pair/document interactions. The complete uploaded document is persisted and can be re-read/reprocessed by the run system.

## Three different knowledge sources

1. **CUAD train-only retrieval:** examples used to help classify a clause. Retrieved examples are not evidence that a fact exists in the uploaded agreement.
2. **Risk playbook and risk taxonomy:** explicit policy/checklist guidance used to decide which questions to ask and how to group findings. They are neither ground truth nor contract evidence.
3. **Legal/practice guidance retrieval:** contextual reference material with source-tier and provenance metadata. This is supporting knowledge only; a retrieved passage cannot substitute for a quote from the uploaded contract. In the current deployment, clause/query embeddings are generated through the Cohere API, so the pipeline is not fully offline even though LLM inference is served locally. Contract confidentiality requirements must be checked before upload.

## Risk playbook (current source of truth)

Source: data/risk/commercial_clause_risk_playbook.json, source version 1.1.

- 37 clause types (36 CUAD substantive categories plus supplemental Indemnification).
- 101 clause-level checks.
- 10 cross-clause checks.
- 3 document-level checks.
- Buyer/customer perspective.
- 10 canonical broad taxonomy domains.

Playbook checks explicitly include question, flag_if, do_not_flag_if, required evidence, evidence location, dependencies, jurisdiction scope, sources and rationale where applicable. The risk label is determined from the **risk condition in QUESTION + FLAG IF**, not merely the grammatical answer to the question. For instance, when FLAG IF = No, absence of a feature can itself be the risk. Mutual/reciprocal wording must not be described as one-sided unless the contract actually differentiates the parties.

### Canonical domain routing

Version 1.1 assigns every check to one of the ten domains in backend/data/legal_knowledge/risk_taxonomy.json. The check's declared playbook domain is authoritative for aggregation/routing. More specific legacy labels are preserved as risk_subdomain; keyword/indicator matches are supplementary taxonomy_suggested_domains and must not silently overwrite a declared domain.

## Evidence contract

A positive finding requires an exact contiguous quote from the uploaded agreement. The evidence validator checks the quote against the current clause and/or supplied same-contract context. Cross-clause findings retain clause IDs and are valid only when their quotes occur in those cited clauses. Legal guidance, the playbook, CUAD training examples and taxonomy indicators cannot count as contract evidence.

Status meanings:
- POTENTIAL_RISK: risk condition is supported by exact contract evidence.
- NO_RISK: the supplied text supports that this check's flag condition is not met.
- INSUFFICIENT_EVIDENCE: needed text is absent, not visible, contradictory, or the model/evidence gate cannot resolve the check.
- ERROR: pipeline/runtime failure, not a no-risk decision.

A document referenced by URL, order form or schedule but not included in the supplied review package must be treated as unread/unavailable, not assumed to be absent.

## Risk scoring and aggregation

Each positive clause finding has four 0–5 raw dimensions:
- exposure magnitude;
- likelihood/uncertainty;
- scope/duration;
- control weakness.

The unadjusted total is a deterministic 0–20 triage score. The current severity bands are Informational (0–3), Low (4–7), Medium (8–11), High (12–15) and Critical (16–20), subject to explicit overrides. It is **not** a probability of loss, a legal standard, or calibrated severity unless the corresponding human-gold calibration artifact exists and was fitted from adjudicated labels.

The aggregator considers high-severity findings, risk-domain clusters, missing core metadata and selected interaction-stack rules. It preserves the finding-level evidence and provenance in the result artifact.

## Cross-clause and document-level layer

The 10 playbook checks include, among others:
- liability cap + uncapped liability;
- liability cap + liquidated damages;
- renewal term + notice to terminate renewal;
- termination for convenience + minimum commitment;
- anti-assignment + change of control;
- perpetual license + termination;
- IP ownership + license grant;
- license grant + source-code escrow;
- liability cap + insurance;
- liability cap + indemnification.

Three document-level checks inspect missing incorporated materials, order-of-precedence reversals, and inconsistent/missing governing-law/forum/dispute mechanics.

The engine also emits deterministic *candidate signals* for interaction patterns (economic stack, exit failure, remedy mismatch, control mismatch, IP continuity, evidence gap and precedence gap). These are review signals, not automatic legal conclusions. Regression tests use synthetic clauses to verify exact-quote gating and abstention for invalid/missing evidence; synthetic tests must not be reported as real-world risk accuracy.

## Machine-silver evaluation

The completed 300-case set was produced by an independent Qwen3 judge and Gemma3 verifier using a blind parallel protocol. It is diagnostic **machine-silver**, not human gold:
- 150 locked-test / 75 calibration / 75 development tasks;
- 165 machine disagreements;
- 108 direct machine agreements;
- 22 agreed-uncertain cases;
- 5 agreements rejected by the evidence gate;
- final labels: 13 YES / 95 NO / 192 UNCERTAIN.

These counts describe consensus and abstention only. They are not accuracy, precision, recall or legal correctness. The human queue remains 0/300 annotated. External CUAD expert labels evaluate clause-category presence/evidence behavior only; they do not validate the custom risk predicates or severity.

## Files created per contract upload

Each run is stored in data/runs/<analysis_id>/:

| File | Purpose |
|---|---|
| manifest.json | source hash, model/config, playbook/calibration hashes, code fingerprint, environment and state |
| source.<pdf|txt> | persistent original input used by the run |
| segments.json | extracted sections/clauses and locations |
| validated.json | clause-validation decisions |
| embeddings.npy | input-clause embeddings checkpoint |
| classification.jsonl | clause-type classification and retrieval metadata |
| contract_coverage.json | clause-family coverage candidates and search traces |
| risk_findings.jsonl | clause/check risk outcomes and evidence |
| contract_checks.json | cross-clause/document checks |
| contract_risk.json | aggregate profile and triage score |
| result.json | user-facing response snapshot |
| clauses.csv, risk_findings.csv | portable analysis tables |
| trace.jsonl, status.json | progress events and current stage |

Analysis IDs are content/config-specific. A changed code fingerprint, model/config, playbook or calibration should start a distinct experiment instead of mixing checkpoints.

## Current evidence status

- Split integrity: 10/10 configured checks pass.
- Human gold: absent (0/300 annotations).
- Accuracy for the custom risk taxonomy: **not available**.
- Model confidence/severity calibration: **not considered scientifically calibrated without adjudicated human labels**.

See PHASE2_REPRODUCIBILITY.md, PHASE2_PAPER_DRAFT.md, data/risk/GOLD_STATUS.md, and data/risk/results/phase2_reproducible_report.md.
