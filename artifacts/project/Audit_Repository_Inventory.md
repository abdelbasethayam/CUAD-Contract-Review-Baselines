# Repository Inventory

Audit basis: source inspection of the current working tree. Paths are relative to the repository root.

| File or directory | Purpose | Inputs | Outputs | Important functions/classes |
|---|---|---|---|---|
| `backend/app/core/config.py` | Runtime configuration and label loading | `.env`, split CSVs | resolved settings and CUAD labels | `load_labels` |
| `backend/app/core/rag/hybrid_parser.py` | Docling-first PDF parsing with fallback | PDF/TXT | ordered `DocumentBlock` objects | `parse_document`, `ParsedDocument` |
| `backend/app/core/rag/clause_segmenter.py` | Structure-aware clause tree construction | parser blocks | `ClauseNode` tree | `segment_document`, `validate_clause_tree` |
| `backend/app/core/rag/segmenter.py` | Legacy/page-cleaning segmentation helpers | pages/text | cleaned pages or flat clauses | `extract_page_layers`, `split_into_clauses` |
| `backend/app/core/rag/embedder.py` | Cohere embedding client | query/document text | float vectors | `embed_queries`, `embed_documents` |
| `backend/app/core/rag/retriever.py` | CUAD dense retrieval | query vector | Top-K CUAD payloads | `make_qdrant_client`, `retrieve_similar` |
| `backend/app/core/rag/generator.py` | CUAD retrieval-to-Ollama classification | clause and Top-K results | label and status | `classify_clause`, `parse_prediction_result`, `call_ollama` |
| `backend/app/core/rag/prompt.py` | Classification definitions and prompt | candidates/examples/features | constrained JSON prompt | `build_prompt`, `load_label_definitions` |
| `backend/app/core/rag/validator.py` | Fragment validation | candidate clause text | real-clause boolean | `is_real_clause` |
| `backend/app/services/rag_service.py` | Uploaded-contract orchestration | uploaded file | ordered result dictionaries | `classify_contract`, `_classify_contract` |
| `backend/app/core/legal_knowledge/ingest.py` | Curated Markdown ingestion | legal Markdown | legal Qdrant points | `chunk_text`, `load_curated_chunks`, `ingest_legal_knowledge` |
| `backend/app/core/legal_knowledge/retriever.py` | Category-filtered legal retrieval | CUAD label and clause | legal guidance Top-K | `map_clause_category`, `retrieve_legal_guidance` |
| `backend/app/core/risk/risk_detector.py` | Rule/indicator/Ollama risk analysis | classified clause and guidance | typed risk result | `detect_legal_indicators`, `detect_clause_risk`, `parse_risk_response` |
| `backend/app/models/schemas.py` | API response models | result dictionaries | `ClauseResult`, contract response | `RiskStatus`, `RiskLevel` |
| `backend/app/api/routes/documents.py` | Upload and JSON/SSE API | PDF/TXT multipart upload | classification response | `/documents/classify`, `/documents/classify/stream` |
| `backend/app/main.py` | FastAPI application | routers and static build | API application | `app` |
| `data/raw/cuad/CUAD_v1` | Local CUAD v1 source | downloaded dataset | raw JSON/CSV/contracts | n/a |
| `data/scripts/dataset/split_cuad.py` | CUAD split and reshape | raw wide CSV | train/test wide and long CSVs | `wide_to_long`, `main` |
| `data/scripts/embedding/embed_train.py` | Stored CUAD embeddings | train long CSV | embeddings JSON and metadata JSONL | `prepare_records`, `embed_records` |
| `data/scripts/embedding/build_qdrant.py` | CUAD Qdrant construction | embeddings and metadata | `cuad_train` collection | `create_collection`, `insert_vectors` |
| `data/splits`, `data/embeddings`, `data/qdrant_local` | Persisted retrieval artifacts | processed CUAD | current indexed vectors | n/a |
| `backend/data/legal_knowledge` | Curated legal source | Markdown with front matter | legal KB chunks | n/a |
| `frontend/src/App.jsx` | Upload and result UI | API SSE result | clause/risk display | `ContractClassifier` |
| `backend/tests` | Regression tests | source modules/fixtures | pass/fail results | segmentation, legal KB, API tests |
| `Dockerfile` | Production image definition | frontend/backend source | FastAPI image | multi-stage build |

Prior diagnostics and reports under `artifacts/` are evidence files, not active runtime modules unless imported by source code.

