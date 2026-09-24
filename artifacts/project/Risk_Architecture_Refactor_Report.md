# Risk Architecture Refactor Report

## A. Previous architecture

The previous flow treated CUAD classification as the gate for risk analysis:

```text
Segmentation -> CUAD retrieval/classification -> CUAD-category legal guidance
             -> category indicators -> model risk decision -> clause result
```

An UNKNOWN or malformed CUAD result could therefore prevent a usable clause
from receiving risk analysis.

## B. Refactored architecture

The active flow is now:

```text
Segmentation
    -> validation
    -> Cohere embedding + unchanged CUAD Qdrant retrieval
    -> candidate-constrained OpenRouter/Nemotron CUAD classification
    -> independent contract-context retrieval
    -> independent Risk Knowledge Base matching
    -> evidence-grounded OpenRouter/Nemotron clause risk assessment
    -> strict exact-evidence validation
    -> contract-level evidence-constrained aggregation
```

CUAD classification status is preserved as evidence, but it is no longer a
precondition for risk analysis. Valid UNKNOWN and malformed-classification
clauses continue to risk analysis; rejected fragments and signature metadata
remain non-clause records.

## C. Files changed for this refactor

Existing files modified:

- `backend/app/core/rag/generator.py` — final CUAD generation now calls
  OpenRouter directly; stale local-Ollama classifier messaging was removed.
- `backend/app/core/risk/risk_detector.py` — risk analysis is independent of
  CUAD status, uses taxonomy guidance, calls OpenRouter, and requires exact
  uploaded-contract evidence.
- `backend/app/core/risk/__init__.py` — exports the single active risk
  detector and contract aggregator.
- `backend/app/services/rag_service.py` — runs risk analysis for valid clauses,
  including UNKNOWN and definitions, and preserves clause-level findings.
- `backend/app/api/routes/documents.py` — exposes one contract-level risk
  assessment on both synchronous and streaming responses.
- `backend/app/models/schemas.py` — adds typed risk-domain, clause-risk, and
  contract-assessment fields to the existing response models.
- `frontend/src/App.jsx` — displays contract risk first, then CUAD evidence,
  then clause-level evidence.
- `backend/app/core/rag/validator.py` — documentation only; its existing
  Ollama call remains isolated to segmentation validation.
- Existing risk/OpenRouter tests were updated to patch the actual provider
  boundary.

New files:

- `backend/app/core/risk/knowledge_base.py` — loader and matcher for the
  independent structured taxonomy.
- `backend/app/core/risk/aggregator.py` — contract-level aggregation.
- `backend/data/legal_knowledge/risk_taxonomy.json` — structured risk domains,
  indicators, severity guidance, and mitigation guidance.
- `backend/tests/test_contract_risk_architecture.py` — architecture and
  evidence-boundary tests.

The new files are necessary because taxonomy loading and contract-level
aggregation are separate responsibilities that do not belong in the existing
clause detector or HTTP route.

## D. Removed CUAD-to-risk dependency

The early return that skipped risk analysis for non-VALID CUAD classifications
was removed. `classification_status`, candidate labels, and CUAD retrieval
examples are now context passed to the risk prompt rather than risk gates.
Definitions still bypass CUAD labeling, but their actual text proceeds to risk
analysis.

## E. Risk taxonomy

The taxonomy is independent of CUAD labels and contains ten domains:

- Financial Risk
- Liability Risk
- Termination Risk
- Operational Risk
- Compliance Risk
- Insurance Risk
- Intellectual Property Risk
- Assignment / Control Risk
- Dispute Resolution Risk
- Commercial Risk

CUAD categories are optional related metadata only. Taxonomy descriptions,
legal guidance, and CUAD examples are never accepted as contract evidence.

## F. Risk Knowledge Base

`risk_taxonomy.json` is a structured local guidance resource. It is not added to
the CUAD Qdrant collection and is not treated as a contract dataset. The
existing curated Legal Knowledge Base remains available as supporting guidance
through the existing retriever.

## G. Aggregator

`aggregate_contract_risk()` accepts clause findings and emits:

- overall status and risk level;
- independent risk domains;
- key risks and affected clause IDs;
- exact supporting contract evidence;
- retained clause findings;
- supporting legal guidance;
- review recommendations.

It does not average model scores. Positive findings are eligible only when
their evidence is an exact substring of the uploaded clause or related
uploaded-contract context. A deterministic evidence-backed level is used as a
fallback; OpenRouter may synthesize the explanation and recommendations from
the already validated findings.

## H. API and frontend

Both `/documents/classify` and `/documents/classify/stream` return
`contract_risk_assessment`. The frontend presents that assessment as the
primary result, followed by CUAD retrieval/classification evidence and then
clause-level risk evidence.

## I. Verification

- Focused OpenRouter, legal-knowledge, and architecture suite: **36 passed**.
- Python `compileall`: **passed**.
- `git diff --check`: **passed**.
- Full backend suite: **63 passed, 1 failed**.
- The single failure is the existing segmentation test
  `tests/test_segmenter.py::test_compact_numbered_clauses_split_after_sentence_boundaries`.
  Segmentation was intentionally not changed for this refactor.
- Local npm is unavailable, so the frontend build was not run on the host.

## J. Limitations and operating boundary

- Ollama remains only in `backend/app/core/rag/validator.py` for the existing
  segmentation-validation step. It is not used for final CUAD classification,
  clause risk, or contract aggregation.
- The current running Docker container was not rebuilt by this refactor; it
  must be rebuilt/restarted before exercising these source changes through the
  live UI.
- No new risk dataset was added, no CUAD data was changed, no Qdrant index was
  rebuilt, and no Cohere embedding configuration was changed.
- No Git commit or push was created.
