# Live upload smoke test — 2026-10-11

Both files were posted to the running FastAPI `/documents/classify` endpoint after the local Ollama service was started. These are synthetic/repository fixtures used to verify the request-to-result path, not representative real-contract samples and not evidence of legal-risk accuracy.

| Fixture | HTTP | Pipeline | Clauses | Clause findings | Cross-clause findings | Document findings | Assessment | Overall risk | Runtime |
|---|---:|---|---:|---:|---:|---:|---|---|---:|
| TXT synthetic fixture | 200 | COMPLETED | 5 | 8 | 10 | 3 | POTENTIAL_RISK | HIGH | 307.2 s |
| PDF repository fixture | 200 | COMPLETED | 2 | 0 | 10 | 3 | INSUFFICIENT_EVIDENCE | — | 67.2 s |

## Run artifacts

- `data/risk/results/smoke_upload_api_live_20261011.txt.json` — full API response and source SHA-256; analysis ID `56a13430f537613f-fcd070f126af256d`.
- `data/risk/results/smoke_upload_api_live_20261011.pdf.json` — full API response and source SHA-256; analysis ID `db10b978019252fc-fcd070f126af256d`.

## Interpretation and environment notes

- TXT returned HTTP 200 and `COMPLETED`; its synthetic content produced `POTENTIAL_RISK` / `HIGH` with evidence-bearing findings. This is a pipeline demonstration, not a validated risk determination.
- PDF returned HTTP 200 and `COMPLETED`; the fixture produced `INSUFFICIENT_EVIDENCE`, with no clause-level positive findings. Abstention is preferable to inventing a supported risk when the fixture lacks applicable evidence.
- The PDF parser attempted Docling but fell back to `pdfplumber` because `torchvision` is not installed in this server environment. The PDF request still completed.
- Backend `/health` returned `{"status":"ok"}`. Frontend Vite dev server responded on port 5173, and `npm --prefix frontend run build` passed.
- The release-check script separately passed all 18/18 checks, including 105 backend tests. These engineering checks do not establish custom-risk accuracy or legal correctness.
- The first TXT request took 307.2 seconds because Ollama was initially unavailable while the request was already running; the PDF request took 67.2 seconds after the model service was ready. Do not treat these as a controlled latency benchmark.