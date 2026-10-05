# Fine-tune CUAD classifier

**Recommended base:** `Qwen/Qwen2.5-7B-Instruct` (`ollama pull qwen2.5:7b`)

```bash
# 1) Build SFT JSONL from master_clauses CSVs
python scripts/finetune/prepare_sft_data.py \
  --train data/splits/train/master_clauses_train.csv \
  --test data/splits/test/master_clauses_test.csv \
  --out-dir data/finetune

# 2) Install FT deps
pip install -r requirements-finetune.txt

# 3) LoRA train
python scripts/finetune/train_lora.py \
  --base Qwen/Qwen2.5-7B-Instruct \
  --data-dir data/finetune \
  --out output/ft_qwen25_7b_cuad

# 4) Eval accuracy + macro-F1
python scripts/finetune/eval_sft.py \
  --base Qwen/Qwen2.5-7B-Instruct \
  --adapter output/ft_qwen25_7b_cuad/adapter \
  --jsonl data/finetune/val.jsonl
```

See `docs/FINETUNE.md` for model choice, Muffakir note, and Ollama serving.
