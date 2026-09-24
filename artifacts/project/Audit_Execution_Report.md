# Execution Audit

## Commands and results

| Command/action | Result |
|---|---|
| Resolve backend configuration and labels with Python 3.11 | PASS: model/path/Top-K values resolved; 36 labels loaded |
| Read-only Qdrant inspection of both local collections | PASS: 7,004 CUAD points and 30 legal points; no upsert/delete performed |
| Read-only collection payload scan | PASS: payload schemas, document counts, labels/categories measured |
| `python -m compileall -q backend/app` | PASS |
| `pytest tests/test_legal_knowledge.py -q` from `backend` | PASS: 17 passed, 2 dependency deprecation warnings |
| full `pytest tests -q` from `backend` | PARTIAL: 44 passed, 1 failure in existing `test_segmenter.py` compact numbered-clause expectation |
| `CONTRACT_PARSER=regex` parser/segmenter trace on test and ZTO PDFs | PASS: completed read-only; no persisted outputs written |
| FastAPI OpenAPI route inspection | PASS: active classify, stream, health, docs, and OpenAPI routes confirmed |
| frontend Vite build | NOT VERIFIED: Node executable unavailable |
| Docling production parser execution | NOT VERIFIED: current host environment lacks Docling; persisted evaluation records it unavailable |
| live Cohere request | NOT VERIFIED: no external embedding request made during audit |
| live Ollama request | NOT VERIFIED: no model request made during audit |
| Docker execution | NOT VERIFIED: Docker daemon unavailable |

## Safety

No source, dataset, `.env`, Qdrant point, collection, embedding artifact, or
model configuration was modified. Audit documentation was written only under
`project/`.

