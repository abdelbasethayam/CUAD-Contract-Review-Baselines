# Frontend Audit

`frontend/src/App.jsx` renders a React upload form and posts the selected PDF or
TXT to `/documents/classify/stream`. Vite proxies `/documents` to
`http://127.0.0.1:8000` during development.

The frontend parses SSE `progress`, `result`, and `error` events. It displays
the file name, clause count, live stage trace, CUAD label, clause text,
classification/risk status, reason, evidence, source, legal guidance, and
retrieved CUAD labels/scores.

Risk badges are driven by structured `risk_status` values rather than reason
string matching. The summary displays potential risks, configured no-risk
clauses, supported categories, unavailable analyses, skipped analyses, and
errors. There is no confidence or contract-level score display.

The frontend build configuration is present and `frontend/dist` exists, but a
current Vite build was NOT VERIFIED because the environment contained frontend
dependencies but no Node runtime executable.

## Update: interface redesign

The interface was rebuilt around a document-first layout: a landing page with a
single upload action, a results workspace with "Terms to review" and "Clauses"
views, and a persistent "Ask this contract" panel.

- Findings are grouped by risk domain, de-duplicated across clause, cross-clause,
  document and rule-based sources, and each shows the exact quoted wording.
- Unresolved checks are kept separate and are never presented as safe.
- Internal status strings, calibration notes, run diagnostics and per-file
  download lists were removed from the main view. The metrics endpoint is unchanged.
- No severity or probability is displayed, consistent with
  `data/risk/RISK_SCORE_POLICY.md`.
- `npm run build` was run successfully with Node 22 / Vite 5.

