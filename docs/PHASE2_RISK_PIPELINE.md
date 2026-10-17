# Phase 2 — Rule-First, Evidence-Grounded Contract Risk Screening

## Purpose

The system prioritizes commercial contract provisions for review. It does not provide legal advice or decide enforceability. The clause-category classifier and the risk screener are separate components: the classifier predicts what kind of provision a clause resembles, while Phase 2 checks explicit buyer-side conditions defined by the risk playbook.

## End-to-end path

    Upload PDF/TXT
      -> extract and segment contract
      -> separate CUAD clause-category classification
      -> deterministic playbook-rule scan over every clause, independent of classifier label
      -> playbook question + flag_if / do_not_flag_if for nuanced checks
      -> optional related-clause retrieval from the same uploaded contract
      -> optional legal/practice guidance as context only
      -> exact contract-quote validation
      -> 10 cross-clause questions + 3 document-level questions
      -> canonical risk-domain routing and deterministic review triage
      -> evidence-linked report, CSV/JSONL, trace and manifest

The risk prompt never receives retrieved CUAD training example spans. CUAD examples are used by the separate category classifier only, and never as contract evidence. No risk flag is fine-tuned from text-span examples.

## Source of truth

The source playbook is data/risk/commercial_clause_risk_playbook.json, version 1.2. It contains 37 clause targets, 101 clause-level checklist questions, 10 cross-clause checks, 3 document-level checks, and 7 initial deterministic predicates. All domains map to the ten canonical domains in backend/data/legal_knowledge/risk_taxonomy.json.

The deterministic predicates run against every uploaded clause even if clause classification is wrong or unknown. They cover explicit uncapped liability, indemnification outside the cap, liquidated damages outside the cap, immediate/no-notice termination, broad-scope IP license wording, early-exit remaining-term fees, and absolute assignment prohibitions. Positive outputs include the rule ID, exact matching contract substring, short explanation, domain, playbook hash and rule-engine version.

These predicates are an explicit starter set. They are intended to be transparent and testable, not exhaustive. A match is a review trigger. A non-match is not proof that a clause is risk-free.

## Role of the question stage

The playbook's question stage handles nuance that compact pattern rules cannot resolve. For each applicable check, the model receives the actual clause and optional related clauses from the same uploaded agreement. The question's flag condition sets the risk polarity; the model is not allowed to infer a risk from a label, a source note or an indicator alone. If there is not enough uploaded-contract evidence, the result remains unresolved.

Legal/practice source material can provide explanatory context, but it is not evidence that the agreement contains the term being discussed. The source evidence must be copied from the uploaded contract and validated against the clause text.

## Evidence contract and visible states

- POTENTIAL_RISK: a deterministic rule triggered or a playbook question met its flag condition and exact uploaded-contract evidence was retained.
- NO_RISK: available contract text supports that the applicable question's flag condition is not met.
- INSUFFICIENT_EVIDENCE: the condition cannot be resolved from the provided package or the evidence is incomplete.
- ERROR: a check failed to execute or return usable structured output.

Cross-clause/document positives require existing clause IDs plus exact quotes that appear in those cited clauses. Missing schedules or URL-incorporated terms are treated as unread/unavailable rather than assumed absent.

## Release and evaluation

Release checks validate:
1. unique rule IDs, compiling regex/exclusion patterns, required fields, and canonical taxonomy mapping;
2. no CUAD example spans injected into either risk prompt path;
3. exact-quote preservation for direct rule triggers;
4. training-only payloads for the separate CUAD classification index, with no held-out contract overlap;
5. playbook-domain normalization and team export;
6. positive/control/incomplete synthetic playbook-question regression fixtures;
7. recorded TXT/PDF smoke results and backend tests.

The corresponding report is data/risk/results/phase2_reproducible_report.md. It intentionally reports rule and system conformance, not legal-risk accuracy. There is no custom-risk annotation dataset in the operational risk or release path.

Run the full release suite from the repository root, with the backend stopped before Qdrant integrity validation:

    .venv/bin/python scripts/risk/run_release_checks.py

Then restart the app with bash scripts/start_all.sh and check http://127.0.0.1:8000/health. The API must be stopped when the embedded Qdrant index-isolation validator runs because the local storage uses an exclusive lock.

## Findings and triage

Risk severity is a deterministic review-prioritization signal, not a calibrated probability of loss or a legal standard. Every positive display should show the source clause, exact quotation, rule/check ID and concise explanation. Unmatched patterns should never be presented as proof of safety.

## Privacy

The embedding profile determines whether query/clause embeddings are local or sent to an external provider. The local hashing option is deterministic lexical retrieval, not a pretrained semantic model. Confirm the live embedding configuration before uploading confidential agreements.
