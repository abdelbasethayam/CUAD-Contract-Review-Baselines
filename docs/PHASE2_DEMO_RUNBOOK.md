# Phase 2 Recorded Demo Runbook

## Purpose

Produce a clean 2–3 minute walkthrough of the CUAD Contract Review workspace. The walkthrough demonstrates the interface and evidence workflow; it is **not** evidence of legal accuracy or production readiness.

## Before recording

1. Check out the latest `phase2/playbook-rule-first-no-gold` branch.
2. Install dependencies and configure `backend/.env` as described in the README. The default embeddings configuration sends clause/query text to Cohere; do not use confidential contracts unless the transfer is authorized.
3. Start the API and frontend:

   ```bash
   bash scripts/start_all.sh
   ```

4. Confirm the API health endpoint returns `{"status":"ok"}` at `http://127.0.0.1:8000/health` and open the frontend at `http://127.0.0.1:5173`.
5. For the live Q&A portion, ensure Ollama is running and the configured `RISK_MODEL` is installed. The default model is `qwen3:8b`. Pull and warm it before recording if needed:

   ```bash
   ollama pull qwen3:8b
   ollama run qwen3:8b
   ```

   Exit the interactive model session after it has loaded if needed; keep the Ollama service running. Before recording, run the six-question semantic/citation smoke check:

   ```bash
   python scripts/risk/evaluate_contract_chat_demo.py --out data/risk/results/contract_chat_demo_evaluation.json
   ```

   The script checks liability-cap comparison and party attribution, termination rights, governing-law uncertainty, insurance limits, post-termination data handling, indemnity/liability-cap ambiguity, and citation provenance. This is a small deterministic smoke suite, not a statistically valid accuracy benchmark. Fix any failure before presenting the chatbot as working. If Ollama is unavailable, the chatbot intentionally falls back to verified source excerpts and labels that response as a source-only fallback—it does not pretend to have interpreted the contract.
6. Close unrelated tabs, browser developer tools, and desktop notifications. Use a 1920×1080 capture, browser zoom around 90–100%, and wait for the API status to show **API connected**.

## Demo flow (about 2 minutes)

### 0:00–0:15 — Introduce the workspace

Show the landing page and the three core ideas: exact-text evidence, cross-clause review, and traceable findings.

Suggested narration: “This workspace separates clause classification from commercial review triggers. It shows the wording behind a finding instead of asking the user to trust a score.”

### 0:15–0:30 — Open the guided demo

Click **Open guided demo**. It should work on a clean install without a previous upload or model inference. The API creates a deterministic walkthrough from `data/risk/demo_contract_for_reproduction.txt` and returns 11 synthetic contract sections, illustrative findings, and audit artifacts.

Keep the **SYNTHETIC DEMO** label and the notice visible. Do not imply the illustrative findings were produced or legally validated by a model.

### 0:30–0:55 — Overview and contract profile

Point out the parties, unresolved governing-law field, contract-level status, and the fact that confidence remains uncalibrated. Explain that the governing law is deferred to an Order Form in the fixture; the assistant should not silently assume a jurisdiction.

### 0:55–1:25 — Evidence-backed risks

Open **Risks** and show:
- The supplier/customer liability-cap asymmetry.
- The broad customer indemnity and missing supplier IP-infringement indemnity.
- The changing online terms and precedence clause.

Open one finding and read the exact quoted provision. Explain that each item is a review candidate, not a legal conclusion. Use the **Clauses** tab to search for a section heading or phrase and show the surrounding language.

### 1:25–1:55 — Ask the contract

Open **Ask this contract** and use these prepared questions one at a time:
1. `How is supplier liability capped, and how does it compare with the customer's cap?`
2. `What termination rights does each party have?`
3. `Can we determine the governing law from this document alone?`

Look for an answer in plain language with exact quoted clauses and clause numbers. If the contract does not support an answer, the assistant should say so. If the local model is unavailable, show the source-only fallback honestly rather than implying an AI interpretation occurred.

### 1:55–2:15 — Audit trail

Return to **Overview** and open one or two download links. Mention that findings and the manifest can be inspected outside the UI. Finish by reiterating that the demonstration is about evidence traceability and workflow, not measured legal-risk accuracy.

## Pre-record checklist

- [ ] Latest feature-branch commit is checked out.
- [ ] Python and full-stack GitHub Actions pass for the exact commit being recorded.
- [ ] `/health` returns `ok` and the UI shows **API connected**.
- [ ] **Open guided demo** works from a clean runtime without uploading the fixture first.
- [ ] The demo is labelled synthetic; the notice remains visible.
- [ ] The three Q&A prompts return verified clause quotes; no unsupported claim is narrated as fact.
- [ ] Ollama is warmed up, or the source-only fallback is shown transparently.
- [ ] Downloads work and no private contract or API key appears on screen.
- [ ] Browser zoom, cursor, window size, and notifications are prepared.

## Claims the recording must not make

- Do not call the synthetic findings legal advice or independently adjudicated ground truth.
- Do not present the number of rules or passing unit tests as legal-risk accuracy.
- Do not present an uncalibrated support score as a probability or a severity rating.
- Do not claim that the current playbook is production-approved. The release remains blocked pending rule-by-rule review, independent adjudication, and a frozen project-specific gold evaluation set.
