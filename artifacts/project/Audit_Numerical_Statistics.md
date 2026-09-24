# Numerical Audit Statistics

| Component | Metric | Value | Source/type |
|---|---|---:|---|
| Dataset | raw contracts | 510 | calculated from local CSV/JSON |
| Dataset | CUAD categories | 41 | local CUAD README and columns |
| Dataset | train contracts | 410 | calculated from train wide CSV |
| Dataset | test contracts | 100 | calculated from test wide CSV |
| Dataset | train long rows | 10,545 | calculated from CSV |
| Dataset | test long rows | 2,556 | calculated from CSV |
| Dataset | train substantive rows | 7,004 | calculated from `is_metadata` |
| Dataset | test substantive rows | 1,679 | calculated from `is_metadata` |
| Dataset | train/test overlap | 0 | calculated from document IDs |
| Classification | runtime labels | 36 | `load_labels()` runtime |
| Embeddings | model | `embed-english-v3.0` | artifact/runtime config |
| Embeddings | dimension | 1,024 | artifact/Qdrant |
| Embeddings | stored vectors | 7,004 | artifact |
| Embeddings | batch size | 96 | runtime config |
| Qdrant | CUAD collection | `cuad_train` | runtime config |
| Qdrant | CUAD vectors | 7,004 | read-only runtime inspection |
| Qdrant | CUAD documents | 383 | read-only payload calculation |
| Qdrant | legal collection | `legal_knowledge` | runtime config |
| Qdrant | legal vectors | 30 | read-only runtime inspection |
| Legal KB | source Markdown files | 17 | calculated from current path |
| Legal KB | freshly calculated chunks | 19 | current source chunker |
| Legal KB | stored chunks | 30 | read-only Qdrant inspection |
| Segmentation | Cooley artifact clauses | 120 | persisted artifact |
| Segmentation | Cooley definitions | 20 | persisted artifact |
| Segmentation | ZTO regex-fallback top-level nodes | 16 | runtime observation |
| Retrieval | CUAD Top-K | 5 | runtime config/source |
| Retrieval | legal Top-K | 3 | runtime config/source |
| Ollama | model | `llama3.2:3b` | resolved backend configuration |
| Ollama | timeout | 60 seconds | resolved backend configuration |
| Risk | calibrated risk score | NOT IMPLEMENTED | source inspection |
| Risk | contract-level aggregate | NOT IMPLEMENTED / NOT VERIFIED | source inspection |
| API | classification endpoints | 2 | FastAPI OpenAPI inspection |

