# API Audit

## Active endpoints

| Method | Path | Request | Response/behavior |
|---|---|---|---|
| GET | `/health` | none | `{"status":"ok"}` |
| GET | `/docs` | none | dependency-free HTML API documentation page |
| GET/HEAD | `/openapi.json` | none | FastAPI OpenAPI document |
| POST | `/documents/classify` | multipart field `file`, suffix `.pdf` or `.txt` | `ContractClassificationResponse` with ordered `ClauseResult` values |
| POST | `/documents/classify/stream` | multipart field `file`, suffix `.pdf` or `.txt` | `text/event-stream` progress events followed by result/error |

The `/query` router file exists as a v2 stub but is not included by
`backend/app/main.py`; no `/query` endpoint is active in the inspected app.

## Processing and errors

Uploads are copied to a temporary file. Unsupported suffixes return HTTP 400.
`ValueError` from classification maps to HTTP 422, dependency/runtime
`RuntimeError` maps to HTTP 503, and the stream route emits status-bearing error
events. Temporary files are deleted in `finally` blocks.

## Response shape

The top-level response contains `filename`, `total_clauses`, and `clauses`.
Each clause contains its index/text, predicted CUAD label, retrieved labels and
scores, classification status, typed risk status, risk fields, source, and
retrieved legal knowledge. No contract-level risk field exists.

