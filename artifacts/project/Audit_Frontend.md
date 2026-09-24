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

