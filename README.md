# CUAD Contract Clause Classification

**Student project:** classify commercial contract clauses into CUAD categories using retrieval and large language models.

### GitHub links

| | URL |
|--|-----|
| **This repository** | https://github.com/abdelbasethayam/CUAD-Contract-Review-Baselines |
| **GitHub profile** | https://github.com/abdelbasethayam |
| **Clone** | `git clone https://github.com/abdelbasethayam/CUAD-Contract-Review-Baselines.git` |
| **Fine-tune guide** | https://github.com/abdelbasethayam/CUAD-Contract-Review-Baselines/blob/main/docs/FINETUNE.md |
| **Hybrid / Qwen notes** | https://github.com/abdelbasethayam/CUAD-Contract-Review-Baselines/blob/main/docs/QWEN_IMPROVEMENTS.md |

---

## 1. Problem

Given a clause from a commercial contract, predict its **CUAD clause type** (e.g. Governing Law, Non-Compete, Cap On Liability).

CUAD is a standard benchmark for contract understanding. The task is difficult because:

- Many labels are rare (class imbalance)
- Some labels are easily confused (e.g. Cap vs Uncapped Liability)
- Zero-shot LLMs alone are often weak without good retrieval

---

## 2. Approach (summary)

```
Clause text
    → preprocess (normalize, expand abbreviations)
    → retrieve similar training clauses
         • dense embeddings (Cohere) and/or
         • hybrid dense + TF-IDF (RRF)
    → shortlist candidate labels
    → classify with Qwen (local via Ollama)
         • multiple-choice + letter probabilities, or
         • JSON classification
    → optional rules / confusion-pair fixes
    → predicted label
```

**Main stack recommended in this repo:**

1. **Hybrid retrieval** (dense + TF-IDF, reciprocal rank fusion)  
2. **Fine-tuned Qwen2.5-7B-Instruct** (LoRA) for classification  

A pure RAG + untrained small model is a baseline; fine-tuning is what improves accuracy and macro-F1 the most.

---

## 3. What was implemented

| Component | Description |
|-----------|-------------|
| Preprocessing | Text cleanup, legal abbreviation expansion |
| Dense retrieval | Cohere embeddings + Qdrant |
| Hybrid retrieval | MPNet dense + TF-IDF fused with RRF |
| LLM classifier | Qwen3-8B via Ollama, non-thinking MCQ/logprobs for candidate scoring |
| High-precision rules | Regex priors for clear classes (e.g. Governing Law) |
| Confusion handling | Tie-break for known hard label pairs |
| Evaluation | Accuracy, Recall@K, per-label metrics, error types |
| Fine-tuning | LoRA scripts for Qwen3-8B on document-disjoint train/validation data |

---

## 4. How to run (short)

**Requirements:** Python 3.10+, Ollama, Cohere API key (for embeddings), local or remote Qdrant index.

```bash
git clone https://github.com/abdelbasethayam/CUAD-Contract-Review-Baselines.git
cd CUAD-Contract-Review-Baselines

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp backend/.env.example backend/.env
# Edit .env: set OLLAMA_MODEL=qwen3:8b (Qwen2.5-7B remains a comparison baseline)

ollama pull qwen3:8b
```

### Data validation / classification preparation

The raw CUAD master CSV is kept immutable. Use the reproducible validator/preparer below to create the model-ready long-format training/test files:

```bash
python data/scripts/dataset/prepare_classification.py
```

This keeps the 410/100 contract-disjoint split, excludes the five contract-metadata fields from clause classification, preserves the original clause text, and adds a conservative normalized text view. It also reports multi-label annotation overlaps and other data-quality checks. Do not use the `answer` field as classifier input.

See [docs/DATA_QUALITY_CUAD.md](docs/DATA_QUALITY_CUAD.md) for the audit policy.

**Shot baselines on the real held-out test set:**

```bash
python scripts/01_reembed_local.py
python scripts/07_run_shot_baselines.py
```

**Leakage-safe hybrid Qwen evaluation:**

```bash
python scripts/06_run_qwen_improved.py run --split val --experiment hybrid-rerank-1
python scripts/06_run_qwen_improved.py tune --experiment hybrid-rerank-1
python scripts/06_run_qwen_improved.py run --split test --experiment hybrid-rerank-1
```

The test run requires frozen validation fusion parameters. Test clauses are never used to tune retrieval, reranking, examples, prompts, or fusion.

**Fine-tune Qwen:**

```bash
pip install -r requirements-finetune.txt

python scripts/finetune/prepare_sft_data.py \
  --train data/splits/train/master_clauses_train.csv \
  --test  data/splits/test/master_clauses_test.csv \
  --out-dir data/finetune

python scripts/finetune/train_lora.py \
  --base Qwen/Qwen2.5-7B-Instruct \
  --data-dir data/finetune \
  --out output/ft_qwen25_7b_cuad
```

Details: [docs/FINETUNE.md](https://github.com/abdelbasethayam/CUAD-Contract-Review-Baselines/blob/main/docs/FINETUNE.md), [docs/QWEN_IMPROVEMENTS.md](https://github.com/abdelbasethayam/CUAD-Contract-Review-Baselines/blob/main/docs/QWEN_IMPROVEMENTS.md).

---

## Phase 2 — Uploadable contract risk review

The repository now contains an end-to-end PDF/TXT upload application that performs clause segmentation, CUAD clause classification, buyer-side playbook risk checks, exact contract-evidence validation, cross-clause/document checks, and contract-level triage. The current interactive profile uses one risk reasoning pass for lower latency; this does not constitute multi-pass agreement, risk confidence remains uncalibrated without human gold, and exact-evidence gating remains enabled. Set `RISK_SELF_CONSISTENCY_PASSES=3` for a slower repeated-pass diagnostic run.

**Start the UI/API:** configure Ollama and backend/.env, then run bash scripts/start_all.sh. The API health check is curl -fsS http://127.0.0.1:8000/health; the frontend is usually on port 5173.

**Run the synthetic TXT smoke and audit, using the configured interactive setting:**
    .venv/bin/python scripts/risk/smoke_upload_api.py
    .venv/bin/python scripts/risk/audit_smoke_run.py

For a PDF test fixture, run `python scripts/risk/smoke_upload_api.py --file test_contract.pdf --out data/risk/results/smoke_upload_api_pdf_result.json`, then audit it with `python scripts/risk/audit_smoke_run.py --input data/risk/results/smoke_upload_api_pdf_result.json --suffix pdf`. The checked-in run records include the earlier three-pass TXT/PDF runs plus a one-pass TXT run for a measured latency comparison.

**Rebuild the no-network retrieval profile from source:** stop the backend, then run `bash scripts/risk/build_local_retrieval_profile.sh`. This rebuilds both 768-dimensional local hashing indexes, proves train/test/index isolation, checks representative legal guidance retrieval, regenerates the team export/report, and runs the release suite. Start the app afterward with `bash scripts/start_all.sh`. Do not rebuild the embedded Qdrant collections while the backend is running.

**Regenerate reproducible artifacts (without rebuilding indexes):**
    .venv/bin/python scripts/risk/validate_evaluation_integrity.py
    .venv/bin/python scripts/risk/normalize_playbook_domains.py
    .venv/bin/python scripts/risk/export_team_pack.py
    .venv/bin/python scripts/risk/report_phase2_experiment.py
    .venv/bin/python scripts/risk/run_release_checks.py

Full guides: docs/PHASE2_RISK_PIPELINE.md, docs/PHASE2_REPRODUCIBILITY.md, and docs/PHASE2_PAPER_DRAFT.md. Release validation can be recorded with python scripts/risk/run_release_checks.py.

The risk playbook is review guidance, not legal ground truth. The 300-case risk benchmark is model-generated **silver**, not human gold. Custom-risk accuracy is therefore unavailable; the paper and reports intentionally make no precision/recall/F1 claims for the custom risk predicates.

**Privacy and offline mode:** the default `EMBEDDING_BACKEND=cohere` sends clause/query text to Cohere for embeddings and requires network access. For a local-only mode, set `EMBEDDING_BACKEND=local_hashing`, `LOCAL_HASHING_DIM=768`, `QDRANT_COLLECTION=cuad_train_hashing`, and `LEGAL_KNOWLEDGE_COLLECTION=legal_knowledge_hashing` in `backend/.env`, then stop the backend and run `bash scripts/risk/build_local_retrieval_profile.sh`. Restart with `bash scripts/start_all.sh`. This local mode uses deterministic HashingVectorizer/cosine retrieval (lexical-vector baseline), not a pretrained semantic embedding model, and must be evaluated as a separate configuration. Ollama generation and Qdrant remain local; do not upload confidential documents to any network-enabled mode unless the transfer is authorized.

---

## 5. Evaluation policy

The repository no longer publishes guessed accuracy ranges for the final pipeline. Report:

- accuracy
- macro-F1
- held-out test clause count and contract count
- candidate shortlist recall
- per-label F1 / support
- the exact model, embedding model, reranker, shot count, and frozen fusion parameters

Use validation for all configuration decisions. Use the untouched test split only after the configuration is frozen.

---

## 6. Project structure (main folders)

```
backend/app/core/rag/     # retrieval, prompts, classifier, rules
backend/eval/             # evaluation scripts
scripts/                  # hybrid runner, analysis
scripts/finetune/         # prepare data, LoRA train, eval
data/splits/              # train/test clause CSVs
docs/                     # design and fine-tune notes
```

Browse on GitHub: https://github.com/abdelbasethayam/CUAD-Contract-Review-Baselines/tree/main

---

## 7. Limitations

- Output is **decision support**, not legal advice.
- Rare CUAD labels keep **macro-F1** lower than overall accuracy.
- Quality depends on a correct train index (Qdrant) and consistent embedding model.
- Fine-tuning needs a GPU for practical runtime.

---

## 8. References

- CUAD dataset (Atticus Project) — contract understanding benchmark  
- Qwen2.5 / Qwen3 models (Alibaba) — local LLM via Ollama  
- Hybrid retrieval via reciprocal rank fusion (dense + lexical)

---

## 9. Author

- **GitHub:** [abdelbasethayam](https://github.com/abdelbasethayam)  
- **Project repo:** [CUAD-Contract-Review-Baselines](https://github.com/abdelbasethayam/CUAD-Contract-Review-Baselines)

*For course submission: report test-set accuracy and macro-F1 after running evaluation on your split; attach hybrid `--no-llm` shortlist recall as an ablation.*
