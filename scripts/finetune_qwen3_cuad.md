# Fine-tune Qwen3-8B for CUAD-derived clause classification

## Goal

Compare a LoRA fine-tuned Qwen3-8B classifier against the non-fine-tuned Qwen3-8B hybrid RAG pipeline. Do not assume a target accuracy before running validation.

## Data protocol

- Keep the raw CUAD source immutable.
- Use the repository's 410/100 document-disjoint train/test split.
- Create the SFT train/validation split from the 410 training contracts only.
- Never use the 100-contract test split for prompt, retrieval, fusion, or training decisions.
- Retain legitimate cross-category span reuse; it is part of the CUAD annotation design.

## Prepare

```bash
python scripts/finetune/prepare_sft_data.py \
  --train data/splits/train/master_clauses_train.csv \
  --test data/splits/test/master_clauses_test.csv \
  --out-dir data/finetune
```

## Train

```bash
python scripts/finetune/train_lora.py \
  --base Qwen/Qwen3-8B \
  --data-dir data/finetune \
  --out output/ft_qwen3_8b_cuad
```

The training script disables Qwen3 thinking in the chat template when the tokenizer supports that switch. This keeps the training target aligned with the structured classification output.

## Recommended tuning

Start with the shipped LoRA configuration. Use validation macro-F1 to choose among small sweeps of learning rate, LoRA rank, and epoch count. Keep the tokenizer/template and label set fixed across runs.

## Evaluation

Evaluate the fine-tuned model on the validation split first. After selecting the checkpoint, run the 100-contract test split exactly once for the reported result.

Compare the fine-tuned model both with:

1. Qwen3-8B zero-/one-/five-shot baselines.
2. Qwen3-8B hybrid RAG with optional BGE reranking.

## Serving

Merge the LoRA adapter into the base model or serve the adapter with a compatible runtime, then point `OLLAMA_MODEL` at the resulting local model. For the hybrid production path, keep the same MPNet retrieval and candidate shortlist settings used during evaluation.

## Important

The single-label target is a project-derived flattening of the original CUAD category annotations. The original dataset can annotate the same clause for multiple independent categories, so SFT results should be interpreted as performance on this derived task.
