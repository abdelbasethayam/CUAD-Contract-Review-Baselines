# Fine-tune CUAD classifier

## Which model?

| Model | Role |
|-------|------|
| **`Qwen/Qwen3-8B`** | **Primary experiment** — newer Qwen generation; use non-thinking mode for structured classification |
| `Qwen/Qwen2.5-7B-Instruct` | Historical baseline for comparison |
| `Qwen3 Thinking variants` | Not primary for this MCQ/JSON classifier; disable thinking for the final classification path |

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
  --base Qwen/Qwen3-8B \
  --data-dir data/finetune \
  --out output/ft_qwen3_8b_cuad
```

GPU: ~12–16GB VRAM with 4-bit / small batch (adjust batch/grad_accum). CPU is possible but very slow.

## Eval

```bash
python scripts/finetune/eval_sft.py \
  --base Qwen/Qwen3-8B \
  --adapter output/ft_qwen3_8b_cuad/adapter \
  --jsonl data/finetune/val.jsonl
```

Do not hard-code an expected score. Select the checkpoint by document-disjoint validation macro-F1, then report accuracy and macro-F1 once on the untouched test split.

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
