# Quick Demo and Phase 2 Rule-Conformance Guide

## Start the app

From the repository root:

```bash
bash scripts/start_all.sh
```

Open `http://127.0.0.1:5173`. Keep Ollama running with the model configured in `backend/.env`.

## Record the fastest walkthrough

1. Show the Phase 2 rule-conformance snapshot. It reports the number of playbook rules/questions/domains and whether rule validation, classifier-index isolation, and the full release report have actually run. It does not display any human-label or risk-span queue metric.
2. Click **Load saved demo**. This loads only a completed stored result whose document hash matches the repository's synthetic fixture `data/risk/demo_contract_for_reproduction.txt`. A matching filename alone is not sufficient. If no matching saved run exists, upload that fixture once and analyze it.
3. Open **Overview**, **Clauses**, and **Risks**. Point out that deterministic playbook triggers are recorded independently of the predicted CUAD clause label and cite exact text from the uploaded clause.
4. Open **Ask this contract** and ask: “What termination rights and notice periods does this contract specify?” or “What liability wording should I review?” The assistant uses local Ollama and returns citations only when the proposed quote matches the excerpt supplied to it.
5. Click a follow-up question and show how the answer includes the source clauses.

## Rule-based risk logic

- Seven deterministic predicates are declared in `data/risk/commercial_clause_risk_playbook.json` version 1.2.
- The risk engine runs those predicates before optional same-contract retrieval and LLM reasoning.
- A direct pattern hit is a **review trigger**, not a legal conclusion.
- No pattern hit does not prove a clause is risk-free; the playbook question checks remain available for nuanced cases.
- The CUAD classifier is a separate clause-category task. Retrieved CUAD examples are not inserted into risk prompts and do not count as risk evidence.
- Confidence is uncalibrated and severity is a triage signal, not a probability of loss.

## Reproduce the conformance checks

The focused rule validator is independent of a local Qdrant index:

```bash
.venv/bin/python scripts/risk/validate_playbook_rules.py
```

For the complete release check, stop the backend first because embedded Qdrant uses an exclusive file lock:

```bash
.venv/bin/python scripts/risk/run_release_checks.py
```

The complete run includes classifier-index split/payload isolation. Run it after the local classifier indexes have been built and configured. Start the app again afterward:

```bash
bash scripts/start_all.sh
```

`data/risk/results/release_validation.json` and `.md` should show the results of the latest actual run. Do not treat a saved `NOT_RUN` placeholder as a pass.

## Privacy and intended use

The chat generation call uses local Ollama. Clause/category embedding behavior depends on the configured embedding backend; when an external embedding API is configured, clause text can be sent to that provider. Do not use confidential contracts unless that transfer is authorized.

This prototype prioritizes contract text for human review. It is not legal advice or an autonomous legal decision-maker, and it does not establish legal-risk accuracy or enforceability.
