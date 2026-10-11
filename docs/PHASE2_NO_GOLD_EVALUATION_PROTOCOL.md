# Phase 2 Evaluation Without Human Gold Labels

**Status:** current no-gold evaluation protocol and reporting guardrails; the metamorphic scenario expansion below is the next evaluation extension. This is not a substitute claim of legal-risk accuracy.

## Why the missing gold set is not a reason to stop

The custom risk queue has 300 tasks but currently has zero adjudicated human labels. Do not infer custom-risk precision, recall, F1, calibration, severity accuracy, or legal correctness from model agreement. The project can still evaluate whether the implementation is reproducible, evidence-grounded, internally consistent, robust to controlled changes, and useful as a review-assistance prototype.

Use the following evidence ladder and report each layer separately. Never combine their scores into one “accuracy” number.

## Evaluation layers

### 1. Deterministic invariants (hard release gates)

- Every affirmative finding must cite an exact contiguous quote from the source contract; a missing or altered quote must be rejected or downgraded to `INSUFFICIENT_EVIDENCE`.
- Every finding must preserve source document/hash, clause or section locator, playbook rule ID/version, model/configuration identity, and retrieval provenance.
- Missing, unreadable, or unprocessed clauses must not silently become `NO_RISK`.
- `ERROR`, `INSUFFICIENT_EVIDENCE`, `NO_RISK`, and `POTENTIAL_RISK` remain distinct.
- Train/test contract isolation and index payload isolation must pass.

Report pass counts and named failure cases. These checks demonstrate implementation properties, not legal interpretation.

### 2. Controlled synthetic scenario benchmark

Use the 39-case cross-clause/document matrix in `data/risk/evaluation/cross_document_v1/scenario_matrix.jsonl` as an explicit fixture-conformance diagnostic. It covers risk-stressed positives, protected-control negatives, and incomplete-context/abstention cases for each configured cross/document rule.

The latest batched run matched 27/39 authored expected statuses (69.2%), versus 11/39 (28.2%) in the earlier one-shot output format. This is a change in conformance on constructed examples, not risk accuracy. Inspect the 12 mismatches; classify them as false-positive-like fixture failures, missed-positive-like failures, or appropriate abstention mismatches. Keep scenario IDs and expected outcomes fixed for regression comparison.

To reduce overfitting to hand-authored fixtures, future additions should be generated from rule templates and split by *scenario family*, not by near-duplicate rows: development families can guide fixes; a locked scenario-family set is reported once per release. Record fixture-generator version and hashes. Do not tune repeatedly on a locked set and then call it held out.

### 3. Metamorphic / counterfactual tests (no external gold required)

Add paired documents that differ in one controlled property and specify the expected *relationship* between outputs:

- **Evidence deletion:** remove the cited clause/phrase; the old positive must not remain evidence-valid.
- **Negation / control insertion:** change “may terminate at any time” to “may not terminate except after material breach”; the system should not preserve the same unconditional termination rationale without new evidence.
- **Scope change:** change “all claims” to “third-party claims only”; the finding must update its scope or abstain.
- **Cross-clause repair:** add an explicit carve-out, reciprocal cap, cure period, or post-termination transition obligation; the linked interaction finding should change in the direction prescribed by the rule template.
- **Missing-context test:** remove one of the clauses needed for an interaction; the system should return `INSUFFICIENT_EVIDENCE` / unresolved rather than assert a fully supported interaction.
- **Order invariance:** reorder independent clauses; findings should remain equivalent apart from locators/order-sensitive references.
- **Duplicate invariance:** duplicate an unrelated clause; it should not create a new risk finding solely because of duplication.

These are specification tests. Their expected relations must be written before the model is run and stored with the scenario. Report relation pass rate and each counterexample; do not label this legal accuracy.

### 4. Evidence-grounding and judge diagnostics

An LLM judge may assess a finding against a versioned rubric with separate binary fields: (a) quote exists verbatim, (b) quote entails the stated factual premise, (c) cited clauses support the interaction claimed, (d) source authority is represented accurately, and (e) uncertainty is handled appropriately. Provide the judge only the source text, retrieved material, finding, and rubric—not another judge's decision. Run at least two independently prompted judges when resources permit; preserve disagreements as unresolved.

Exact quote existence is checked deterministically and is not delegated to a judge. Judge outputs are *machine-assessed rubric compliance*, not human gold. Without a human-calibrated probe set, do not report judge agreement as validated reliability. Report per-field distributions, inter-judge agreement, disagreement examples, and model/version/prompt hashes. Do not use the same judge outputs both to tune the system and to claim independent test performance.

### 5. Machine-silver set (diagnostics only)

Keep the existing 300-row blind two-model silver run as a disagreement/abstention diagnostic. Its 13 YES, 95 NO, and 192 UNCERTAIN decisions and direct-agreement/disagreement counts do not establish truth. A positive finding must pass the exact-evidence gate; even a valid quote does not prove the legal or commercial interpretation is correct.

### 6. External benchmark boundaries

Use CUAD's external expert-derived labels only for the aligned clause-category/presence tasks. Those labels do not validate the project's buyer-side risk predicates, severity, cross-clause logic, enforceability claims, or contract-level exposure. A public risk benchmark can be used only after documenting a task/schema/jurisdiction mapping and showing that the labels actually represent the target predicate; otherwise use it as contextual comparison, not gold substitution.

## Recommended reporting table

| Layer | Report | Claim permitted |
|---|---|---|
| Deterministic invariants | pass/fail counts; leakage and evidence-gate violations | Implementation property / reproducibility |
| Synthetic scenario suite | expected-status matches, error taxonomy, fixture hashes | Fixture conformance only |
| Metamorphic pairs | relation pass rate by transformation; counterexamples | Controlled robustness / consistency |
| LLM judge | rubric-field distributions, judge disagreement, prompt/model hashes | Machine-assessed evidence/rubric diagnostics only |
| Machine silver | YES/NO/UNCERTAIN, agreement and abstention counts | Model-consensus diagnostics only |
| CUAD benchmark | category metrics on held-out contracts | Clause classification only |
| Human gold | currently 0/300 adjudicated | No custom-risk accuracy claim available |

## Release decision

A release can pass engineering gates while the scientific claim remains limited. The prototype may be demonstrated for contract upload, clause classification, evidence-linked risk screening, cross-clause/document analysis, traceability, and review prioritization. The UI and paper must describe outputs as **potential issues for human review**, not legal advice or validated autonomous risk determinations. Do not claim real-world sensitivity, precision/recall, calibrated severity, or legal correctness until an independent target-aligned evaluation is available.

## Next work, in order

1. Keep the deterministic release checks and current 39-case scenario suite green and versioned.
2. Add metamorphic pairs for each cross-clause/document rule and a locked scenario-family split.
3. Add the versioned evidence-grounding judge as a separate diagnostic, if runtime/model budget permits; never overwrite human-gold fields with judge output.
4. If even a small independent review becomes possible later, prioritize a stratified probe set with both positives and negatives, difficult near-misses, abstentions, and evidence-span checks. Treat it as a new calibration/evaluation resource, not a replacement for the full queue.
5. Report the absence of human gold prominently in every paper/release summary.