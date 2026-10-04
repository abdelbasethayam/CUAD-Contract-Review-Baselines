# World-class CUAD classification pipeline

## Honest accuracy roadmap (software eng + computational science)

| Setup | Realistic target | Evidence |
|-------|------------------|----------|
| Zero-shot RAG + 1.5B–4B | 40–65% | Your fixed-10 pilot ~40%; ContractEval Qwen3-8B ~54% F1 |
| Strong retrieval + Qwen3-4B-Thinking + candidate constraint | 60–75% | Prompt + Top-K + thinking helps; still limited by label overlap |
| **Fine-tuned Qwen3-4B on CUAD** | **85–92% detection F1** | HF `Ihteshamstar/qwen3-4b-cuad-extractor` reports ~0.90 detection F1 |
| Fine-tuned encoder (DeBERTa/LegalBERT/TinyRoBERTa) | 85–88% | ContractIQ ~86% F1; DeBERTa single-label up to ~88% |
| Ensemble (fine-tuned encoder + fine-tuned LLM + rules) | **90–95%+ on detection / selected categories** | Requires calibration + human review for production legal use |

**95% zero-shot with a 4B model on all 41 overlapping CUAD labels is not credible.**  
**95% with supervised fine-tuning + ensemble + careful eval is an ambitious but published-adjacent target** (especially for *detection* F1 or high-frequency classes).

Production legal systems should still use human-in-the-loop; never treat model output as legal advice.

## Architecture (this repo)

```
Clause text
  -> advanced_preprocess (normalize, abbrev expand, boilerplate strip)
  -> dense retrieval (Cohere/Qdrant) [optional sparse/hybrid]
  -> candidate labels (Top-K unique)
  -> Qwen3-4B-Thinking-2507 (reasoning then JSON)
  -> parse <think>...</think> + final {"clause_type": ...}
  -> confidence / abstention (NO_APPLICABLE_LABEL)
  -> optional: encoder ensemble vote (fine-tuned LegalBERT/DeBERTa)
```

## Model

Default: **`Qwen/Qwen3-4B-Thinking-2507`** (Ollama tag often `qwen3:4b-thinking-2507` or similar — verify with `ollama list`).

- Native long context (up to 256K on HF; use practical ctx for Ollama).
- Thinking mode emits internal reasoning; we strip it and keep final JSON only.
- Prefer temperature 0.0–0.3 for classification; slightly higher (0.6) only if using pure reasoning benchmarks.

```bash
# Example (tag may vary by Ollama library version)
ollama pull qwen3:4b
# or pull a thinking-2507 GGUF / use vLLM:
# vllm serve Qwen/Qwen3-4B-Thinking-2507 --enable-reasoning --reasoning-parser deepseek_r1
```

## Extra data (beyond your local CUAD splits)

| Resource | Use |
|----------|-----|
| [theatticusproject/cuad](https://huggingface.co/datasets/theatticusproject/cuad) | Official QA/spans |
| [dvgodoy/CUAD_v1_Contract_Understanding_clause_classification](https://huggingface.co/datasets/dvgodoy/CUAD_v1_Contract_Understanding_clause_classification) | 13k labeled clauses for classification fine-tune |
| LEDGAR (LexGLUE) | 100 provision types — auxiliary multi-label pretrain |
| MAUD / ACORD (Atticus) | M&A points / retrieval pairs |
| Original CUAD unlabeled EDGAR dump | Domain continued pretrain |

## Path to >90%

1. Build clean train/val/test from `dvgodoy` + your splits (stratified by label).
2. LoRA fine-tune Qwen3-4B (or train Legal-BERT head) on classification format matching inference.
3. Keep RAG candidates as *soft prior*, not hard constraint, after fine-tune (or use dual head).
4. Ensemble: fine-tuned encoder top-3 + LLM label + keyword rules for easy classes (Governing Law, Insurance).
5. Report **macro-F1, micro-F1, per-label F1**, not only accuracy (imbalance).

See `scripts/finetune_qwen3_cuad.md` and `backend/app/core/rag/thinking_client.py`.
