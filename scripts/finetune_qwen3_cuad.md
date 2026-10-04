# Fine-tune Qwen3-4B for CUAD clause classification (path to ~90%+)

## Why fine-tune

Zero-shot RAG classification plateaus well below 90%. Published work:

- Fine-tuned **Qwen3-4B** CUAD extractor: **~0.90 detection F1** (Hugging Face: `Ihteshamstar/qwen3-4b-cuad-extractor`)
- Fine-tuned encoders on CUAD-style tasks: **~86–88%**

## Data

```bash
pip install datasets transformers peft accelerate trl

python - <<'PY'
from datasets import load_dataset
ds = load_dataset("dvgodoy/CUAD_v1_Contract_Understanding_clause_classification")
print(ds)
print(ds["train"][0])
PY
```

Recommended splits: stratify by `label`, hold out 10–15% test never used for prompt tuning.

### Training example format

```text
### Clause:
{clause_text}

### Task:
Classify into exactly one CUAD label from: {label_list}

### Answer:
{"clause_type": "Governing Law"}
```

Optional: include retrieved Top-K examples in train (retrieval-augmented fine-tune) so train == serve.

## LoRA sketch (Unsloth / PEFT)

```python
# Pseudocode — adapt to your GPU and Unsloth/TRL version
from unsloth import FastLanguageModel
model, tokenizer = FastLanguageModel.from_pretrained(
    "Qwen/Qwen3-4B-Thinking-2507",  # or Instruct-2507 for stricter JSON
    max_seq_length=4096,
    load_in_4bit=True,
)
model = FastLanguageModel.get_peft_model(model, r=16, lora_alpha=32, target_modules="all-linear")
# SFTTrainer on JSON-only targets; mask loss on prompt tokens
```

**Tip:** For structured JSON output, fine-tune the **Instruct-2507** variant or train Thinking models with a supervised final-answer segment only (ignore loss inside `<think>` if present).

## Evaluation

```bash
python -m backend.eval.run_classification_eval --fixed-json data/eval/your_holdout.json
```

Track per-label F1; rare labels (e.g. Source Code Escrow) need oversampling or hierarchical grouping.

## Serving fine-tuned weights

- Merge LoRA → GGUF → Ollama Modelfile, **or**
- vLLM with the merged HF checkpoint

Point `OLLAMA_MODEL` / `CLASSIFIER_MODEL` at the fine-tuned tag.
