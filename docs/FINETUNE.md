# Fine-tune CUAD classifier

## Which model?

| Model | Role |
|-------|------|
| **`Qwen/Qwen2.5-7B-Instruct`** | **Primary choice** — best balance for classification accuracy + macro-F1, stable JSON, works with Ollama |
| `Qwen/Qwen3-4B-Instruct` (or Instruct-2507) | Lighter GPU; good if 7B does not fit |
| `Qwen/Qwen3-4B-Thinking-2507` | **Not primary for FT classification** — thinking traces hurt clean JSON/letter training; use only for research |

## Data

`master_clauses_train.csv` is enough if it has clause text + `clause_type` (ideally `document_id` for doc-level splits).

```bash
python scripts/finetune/prepare_sft_data.py \
  --train data/splits/train/master_clauses_train.csv \
  --test data/splits/test/master_clauses_test.csv \
  --out-dir data/finetune
```

## Train (LoRA)

```bash
pip install torch transformers datasets peft trl accelerate bitsandbytes

python scripts/finetune/train_lora.py \
  --base Qwen/Qwen2.5-7B-Instruct \
  --data-dir data/finetune \
  --out output/ft_qwen25_7b_cuad
```

GPU: ~12–16GB VRAM with 4-bit / small batch (adjust batch/grad_accum). CPU is possible but very slow.

## Eval

```bash
python scripts/finetune/eval_sft.py \
  --base Qwen/Qwen2.5-7B-Instruct \
  --adapter output/ft_qwen25_7b_cuad/adapter \
  --jsonl data/finetune/val.jsonl
```

Expect roughly **~75–85% accuracy** and **macro-F1 often ~0.55–0.70** after a solid run (depends on label balance). Rare labels limit macro-F1.

## Serve with Ollama

Merge adapter into base (or use a tool that loads PEFT), convert to GGUF, create a Modelfile, then:

```bash
export OLLAMA_MODEL=cuad-qwen25-7b   # your custom tag
```

Use with hybrid path: `scripts/06_run_qwen_improved.py`.

## Muffakir (https://github.com/Mohamed28112003/Muffakir)

**Useful for:** RAG hyperparameter search (retriever, top-k, rerank, eval loops) on your own data.

**Not a substitute for:** LLM LoRA fine-tuning on CUAD labels.

Optional later: use Muffakir Composer to A/B dense vs hybrid retrieval configs; keep this repo’s hybrid RRF + fine-tuned Qwen as the generation classifier.
