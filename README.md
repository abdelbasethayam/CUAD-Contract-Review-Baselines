# CUAD-Contract-Review-Baselines

AI contract clause classification (CUAD) with RAG, hybrid retrieval, and optional LoRA fine-tuning.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp backend/.env.example backend/.env   # set COHERE_API_KEY, OLLAMA_MODEL
ollama pull qwen2.5:7b
```

## Classification paths

1. **Legacy / API path** — preprocess → dense retrieval → rules → Ollama (`classify_clause`)
2. **Hybrid path (recommended)** — dense + TF-IDF RRF shortlist → letter-logprob Qwen → fusion  
   See `docs/QWEN_IMPROVEMENTS.md` and `scripts/06_run_qwen_improved.py`

## Qwen fine-tuning

Fine-tuning is the main lever for **accuracy** and **macro-F1** beyond RAG/hybrid alone.

| Choice | Model |
|--------|--------|
| **Primary** | `Qwen/Qwen2.5-7B-Instruct` → `ollama pull qwen2.5:7b` |
| Lighter | `Qwen/Qwen3-4B-Instruct` (if available) |
| Avoid as FT base | `Qwen/Qwen3-4B-Thinking-2507` (thinking traces hurt clean label JSON) |

**Data:** `master_clauses_train.csv` is enough (clause text + `clause_type`; ideally `document_id` for document-level validation).

### 1. Install fine-tune dependencies

```bash
pip install -r requirements-finetune.txt
# torch, transformers, datasets, peft, trl, accelerate, bitsandbytes
```

### 2. Build SFT JSONL from master clauses

```bash
python scripts/finetune/prepare_sft_data.py \
  --train data/splits/train/master_clauses_train.csv \
  --test data/splits/test/master_clauses_test.csv \
  --out-dir data/finetune
```

Writes `data/finetune/train.jsonl`, `val.jsonl`, and `labels.json`.

### 3. LoRA train

```bash
python scripts/finetune/train_lora.py \
  --base Qwen/Qwen2.5-7B-Instruct \
  --data-dir data/finetune \
  --out output/ft_qwen25_7b_cuad
```

Uses LoRA (r=16, α=32) by default. Needs a GPU for practical runtime (~12–16GB VRAM with small batch / 4-bit setups).

### 4. Evaluate (accuracy + macro-F1)

```bash
python scripts/finetune/eval_sft.py \
  --base Qwen/Qwen2.5-7B-Instruct \
  --adapter output/ft_qwen25_7b_cuad/adapter \
  --jsonl data/finetune/val.jsonl
```

**Rough expectations after a solid run:** ~75–85% accuracy; macro-F1 often ~0.55–0.70 (rare CUAD labels limit macro-F1).

### 5. Serve with Ollama

Merge or convert the adapter to a GGUF / Modelfile, then:

```bash
export OLLAMA_MODEL=cuad-qwen25-7b   # your custom tag
# use with hybrid runner:
python scripts/06_run_qwen_improved.py run --split test
```

More detail: [`docs/FINETUNE.md`](docs/FINETUNE.md) · [`scripts/finetune/README.md`](scripts/finetune/README.md)

## Docs

| Doc | Topic |
|-----|--------|
| [`docs/FINETUNE.md`](docs/FINETUNE.md) | LoRA, metrics, Ollama, Muffakir note |
| [`docs/QWEN_IMPROVEMENTS.md`](docs/QWEN_IMPROVEMENTS.md) | Hybrid RRF + letter MCQ |
| [`docs/WORLD_CLASS_PIPELINE.md`](docs/WORLD_CLASS_PIPELINE.md) | Accuracy roadmap |

Not legal advice — review support only.
