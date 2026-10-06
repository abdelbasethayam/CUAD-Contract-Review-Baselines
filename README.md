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
