1. Files checked
- `RAG_pipeline/config.py`
- `RAG_pipeline/embed_query.py`
- `RAG_pipeline/retriever.py`
- `RAG_pipeline/prompt_template.py`
- `RAG_pipeline/generator.py`
- `RAG_pipeline/rag_pipeline.py`
- `RAG_pipeline/evaluate.py`
- `dataset/splits/train/master_clauses_train.csv`
- `dataset/splits/test/master_clauses_test.csv`
- `dataset/embeddings/train_embeddings.json`
- `dataset/embeddings/train_metadata.jsonl`
- `dataset/qdrant_local/meta.json`
- `dataset/raw/cuad/CUAD_v1/CUAD_v1.json`
- `scripts/.env`

2. Paths checked
- Project root resolved as `I:\gradation project\mvp2`
- `.env` search order: `I:\gradation project\mvp2\.env` then `I:\gradation project\mvp2\scripts\.env`
- Loaded environment file: `I:\gradation project\mvp2\scripts\.env`
- Train split path: `dataset/splits/train/master_clauses_train.csv`
- Test split path: `dataset/splits/test/master_clauses_test.csv`
- Embeddings path: `dataset/embeddings/train_embeddings.json`
- Metadata path: `dataset/embeddings/train_metadata.jsonl`
- Qdrant path: `dataset/qdrant_local`
- Qdrant collection: `cuad_train`
- Raw CUAD path: `dataset/raw/cuad/CUAD_v1/CUAD_v1.json`

3. Qdrant check
- Local Qdrant store exists at `dataset/qdrant_local`
- Collection `cuad_train` exists
- Collection vector size: `1024`
- Collection distance: `Cosine`
- Point count: `5449`

4. Cohere check
- API key variable present in `scripts/.env`
- Query embedding model resolved to `embed-english-v3.0`
- Stored embedding model in `dataset/embeddings/train_embeddings.json`: `embed-english-v3.0`
- Query embedding model matches stored embedding model

5. Train/Test leakage check
- Train split rows: `410`
- Test split rows: `100`
- Train/test document overlap: `0`
- Qdrant payload scan found `410` train documents and `0` test documents
- No TEST documents were found in `cuad_train`

6. Pipeline connection check
- `embed_query.py` loads the same embedding model as the stored embeddings and returns a verification vector in verify mode
- `retriever.py` opens the local Qdrant store and queries `cuad_train`
- `prompt_template.py` receives retrieved clauses and builds the final prompt
- `generator.py` produces the output answer in verify mode or live Cohere mode
- `rag_pipeline.py` orchestrates TEST tasks end to end
- `evaluate.py` runs the TEST-set pipeline and writes results
- No old `scripts/rag/` paths are referenced

7. Problems found and fixes
- `RAG_pipeline/*.py` were empty. Fixed by implementing the seven RAG modules in the current structure.
- `retriever.py` originally used a Qdrant `search` call that is not available in this environment. Fixed by using `query_points`.
- Verification mode originally skipped retrieval. Fixed by using a deterministic surrogate query vector so local Qdrant retrieval is still exercised.
- `retriever.py` imported pandas unnecessarily. Fixed by switching the split document-id checks to `csv.DictReader`.

8. Final status: PASS

9. Exact command to run the RAG on the TEST set
- `python -B -m RAG_pipeline.evaluate --verify`
