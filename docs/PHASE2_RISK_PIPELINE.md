# Phase 2 — Scientific hardening for evidence-grounded contract risk analysis

Phase 2 is a **review-prioritization and risk issue-spotting system**, not a legal advice engine. The model proposes structured findings; deterministic validators, a versioned playbook, source policy, and a fixed scoring rubric decide what is accepted.

## Architecture

```text
upload
  -> content-addressed run
  -> extraction / segmentation
  -> CUAD clause classification
  -> structured clause context
  -> clause risk checks
       -> playbook
       -> deterministic indicators
       -> same-contract context
       -> approved legal/practice guidance
       -> local SLM
       -> exact-evidence validation
       -> self-consistency
       -> deterministic 0-20 triage score
  -> deterministic hidden-risk signals
  -> cross-clause / document checks
  -> contract aggregation
  -> calibrated probability/severity when gold calibration exists
  -> GUI + JSON/JSONL/CSV audit artifacts
```

## Four source tiers

The risk system keeps source roles non-interchangeable:

- **Tier A — primary/official:** potentially applicable statutes, regulations, official court/treaty materials, or official guidance. Tier A alone can support a legal-conclusion claim, and only when its authority status is binding/court/statute/regulation/treaty and the jurisdiction is compatible.
- **Tier B — professional practice:** bar materials, law-firm checklists, licensed treatises/practice guidance. Use for drafting/review recommendations, not as law.
- **Tier C — research/methodology:** papers, benchmark documentation, dataset cards, evaluation methods. Useful for experiments, not legal validity.
- **Tier D — internal policy:** the organization's versioned risk playbook. It defines what to check; it is not external law or gold truth.

Every retrieved source is normalized with tier, authority status, jurisdiction, effective date, contract type, source URL/title, retrieval timestamp, license/access status, and transferability.

## Playbook versus ground truth

The commercial risk checklist is a **policy playbook**. It is not a gold dataset.

Current imported baseline:

- 24 clause types
- 63 clause-level checks
- 10 cross-clause checks
- 3 document-level checks
- 7 cited source records

A playbook-derived production finding is marked `PLAYBOOK_DERIVED`.

Gold labels require independent human annotation and adjudication.

## Clause-risk schema

For each clause, the pipeline preserves or derives:

- section/page/offset information where the parser provides it
- defined-term candidates and linked section references
- party/role placeholders
- direction of obligation
- transaction-role hints
- scope markers and duration
- rights/duties sentences
- exception/carve-out sentences
- dependencies and unresolved references
- economic-effect placeholders
- risk findings and exact evidence

Fields that cannot be reliably derived remain null/empty and are marked partial/heuristic rather than hallucinated.

## Finding states

Risk status remains backward-compatible:

- `POTENTIAL_RISK`
- `NO_RISK`
- `INSUFFICIENT_EVIDENCE`
- `ERROR`

The finer evidence state is:

- `PRESENT`
- `NOT_FOUND`
- `NOT_APPLICABLE`
- `UNCERTAIN`
- `CONFLICT`

A missing model response is never silently converted to `NO_RISK`.

## Deterministic score and severity

Each potential finding receives four rubric dimensions, each 0–5:

| Dimension | Meaning |
|---|---|
| exposure_magnitude | financial/IP/data/service impact |
| likelihood_uncertainty | support, trigger status, factual/legal uncertainty |
| scope_duration | breadth, territory, users, products, duration |
| control_weakness | cap, cure, approval, audit, insurance, escrow, measurement, remedy |

```text
base_score = sum(four dimensions)  # 0–20
```

Recorded modifiers:

- +2 independently validated cross-clause conflict
- +2 jurisdiction/competition-sensitive issue
- +1 material clause with extraction confidence < 0.75
- +1 unresolved definition/incorporated-document dependency
- -2 where a verified cap and effective remedy bound the same exposure

Default triage bands:

```text
0–3   INFORMATIONAL
4–7   LOW
8–11  MEDIUM
12–15 HIGH
16–20 CRITICAL
```

These are **internal triage thresholds**, not legal standards and not probabilities.

Critical/high overrides are explicit and narrow. For example, a word such as "perpetual" does not automatically make every finding Critical; the override must match a defined high-impact condition or be supported by an explicit model flag.

## Confidence

The model's self-consistency agreement and deterministic indicator matches are stored as diagnostics.

The calibrated risk probability uses **only the deterministic 0–20 final score** as its calibration input.

Calibration is fitted from an adjudicated gold calibration partition with isotonic regression and is version-gated. A legacy calibration artifact that was fitted to a different score is rejected.

Severity calibration uses ordinal one-vs-threshold probabilities for:

- (P(S \ge Low))
- (P(S \ge Medium))
- (P(S \ge High))
- (P(S = Critical))

No calibrated result is shown until a compatible calibration artifact exists.

## Human review and escalation

Every production finding has a `human_review_status`/review escalation state and remains `NOT_REVIEWED` until a human acts.

Escalate to legal review for:

- any Critical finding
- two or more High findings in the same domain
- three or more High findings overall
- a five-Medium named interaction stack
- High/Critical plus missing core contract metadata

Business-owner review is separately tracked for spend/revenue/capacity/exit matters. Privacy/security review is separately tracked for data/security/confidentiality/AI-use matters.

The score never auto-approves, auto-rejects, or auto-redlines.

## Hidden-risk checks

Deterministic interaction candidates cover:

- scope conflicts
- economic stacks
- exit failure
- remedy mismatch
- control mismatch
- IP continuity gaps
- evidence gaps
- precedence gaps

The model then validates evidence against the actual contract. Candidate signals are never treated as legal conclusions by themselves.

## Absence and missing-protection evaluation

`NOT_FOUND_BY_SEARCH` means only that the automated coverage search did not find a clause family.

The separate absence queue asks a human to inspect the **full contract** and label:

- PRESENT
- NOT_FOUND
- NOT_APPLICABLE
- UNCERTAIN

The search-miss rate is measured separately from risk classification recall. This prevents "not detected" from becoming false "absent" ground truth.

## Gold data protocol

Build the clause/check queue:

```bash
python scripts/risk/build_gold_queue.py --n 300
```

Build the absence queue:

```bash
python scripts/risk/build_absence_gold_queue.py --n 200
```

Partitions are assigned by **contract ID**, not individual sample ID, so one contract cannot leak into calibration/development/locked-test partitions through multiple clauses/checks.

Two annotators independently label risk/type/severity/evidence. Preserve raw labels. An adjudicator creates the gold result.

The locked test partition is never used to tune prompts, thresholds, scoring, retrieval, or calibration.

## Evaluation

`scripts/risk/evaluate.py` supports:

### Binary risk

Accuracy, balanced accuracy, precision, recall, specificity, F1, macro-F1, MCC, AUROC, PR-AUC, Brier score, ECE.

### Severity

Macro-F1, ordinal MAE, quadratic weighted kappa, Spearman correlation.

### Evidence

Exact-match, token F1, normalized evidence overlap.

### Uncertainty

Abstention rate and coverage.

### Agreement

Cohen's kappa for two annotators. Use Krippendorff's alpha when more than two annotators are used.

### Uncertainty intervals

Bootstrap confidence intervals are clustered by contract because clauses within one contract are correlated.

## Ablation statistics

Run the risk component ablations from:

```bash
python scripts/risk/run_ablation_matrix.py --source /path/to/contract.pdf
```

For multiple model/ablation outputs, use:

```bash
python scripts/risk/compare_ablations.py --manifest comparisons.json --baseline baseline
```

Pairwise comparisons use a contract-clustered paired sign-flip permutation test and contract-level bootstrap intervals. Holm correction is applied across the family of ablation comparisons.

Exact McNemar remains available as a secondary paired diagnostic; it should not be the only significance test when clauses are clustered within contracts.

## Retrieval evaluation

The legal-knowledge retriever is hybrid:

```text
dense semantic retrieval
       +
TF-IDF lexical retrieval
       ↓
RRF merge
       ↓
metadata/source-tier/jurisdiction filtering
       ↓
evidence to model
```

Contract-text retrieval and legal-guidance retrieval remain separate logical corpora.

Measure retrieval separately from risk classification:

- Recall@k for required evidence/source
- checklist completeness
- unsupported-citation rate
- source support rate
- metadata-filter correctness
- transferability violations
- stale-version / duplicate retrieval failures

Do not report retrieval Recall@k without a retrieval gold set.

## Reproducibility and resumability

Each run is stored at:

```text
data/runs/<analysis_id>/
```

Important artifacts:

- `manifest.json`
- `source.<ext>`
- `segments.json`
- `validated.json`
- `embeddings.npy`
- `classification.jsonl`
- `risk_findings.jsonl`
- `contract_coverage.json`
- `deterministic_cross_checks.json`
- `contract_checks.json`
- `contract_risk.json`
- `clauses.csv`
- `risk_findings.csv`
- `result.json`
- `trace.jsonl`
- `status.json`

The manifest records source hash, model/configuration, playbook hash, prompt version, legal-corpus version, calibration hash, parser/environment information, and run status.

Resume:

```bash
python scripts/run_pipeline.py resume <analysis_id>
```

Explicit resume refuses to mix artifacts if the playbook/model/calibration configuration changed.

## Production boundaries not claimed in this research phase

The repository does not yet implement a full multi-tenant security/retention platform, immutable reviewer identity service, legal-hold orchestration, or fully automated lawyer adjudication workflow.

Those are deployment controls, not evidence that should be faked into a research result.

## Final scientific rule

Do not claim "ground truth risk" from the playbook.

The defensible chain is:

```text
source material
   -> policy/playbook
   -> model finding
   -> exact contract evidence
   -> independent human annotation
   -> adjudication
   -> locked evaluation
   -> calibration
   -> statistical comparison
```
