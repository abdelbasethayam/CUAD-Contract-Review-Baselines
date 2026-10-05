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

## Fine-tune (best accuracy / macro-F1)

Primary model: **Qwen2.5-7B-Instruct** (not Thinking).

```bash
pip install -r requirements-finetune.txt
# then follow scripts/finetune/README.md
```

Full notes: `docs/FINETUNE.md`

## Docs

| Doc | Topic |
|-----|--------|
| `docs/FINETUNE.md` | LoRA, metrics, Ollama |
| `docs/QWEN_IMPROVEMENTS.md` | Hybrid RRF + letter MCQ |
| `docs/WORLD_CLASS_PIPELINE.md` | Accuracy roadmap |

Not legal advice — review support only.
