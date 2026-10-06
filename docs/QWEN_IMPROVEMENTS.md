# Qwen + RAG classification pipeline

This classifier now uses a leakage-safe train/validation/test protocol.

## Recommended architecture

```text
clause
  -> validated text
  -> MPNet dense retrieval + TF-IDF RRF (top 30)
  -> optional BGE cross-encoder reranking
  -> 8 candidate labels
  -> Qwen3-8B, non-thinking mode, MCQ/logprobs
  -> validation-tuned fusion with retrieval votes
  -> final CUAD-derived single label
```

The original CUAD annotations remain untouched. Repeated cross-category spans are retained because CUAD categories are independently annotated.

## Default configuration

```env
OLLAMA_MODEL=qwen3:8b
CLASSIFIER_THINK=false
CLASSIFIER_TEMPERATURE=0.0
CLASSIFIER_TOP_LOGPROBS=20
OLLAMA_NUM_CTX=8192

HYBRID_COLLECTION=cuad_train_mpnet
HYBRID_EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2
HYBRID_K=30
HYBRID_SHORTLIST=8
HYBRID_RERANK=true
HYBRID_RERANKER_MODEL=BAAI/bge-reranker-v2-m3
HYBRID_RERANK_TOP_K=30
HYBRID_INDEX_CACHE=./output/cache/cuad_train_mpnet_hybrid.npz
```

Qwen3 has an explicit non-thinking mode, which is used here because the classifier expects a short answer token. Ollama exposes logprobs as a boolean plus a separate top_logprobs parameter.

## Evaluation

Build the MPNet train/test index first:

```bash
python scripts/01_reembed_local.py
```

Run the explicit shot baselines on the untouched held-out test set:

```bash
python scripts/07_run_shot_baselines.py
```

Run the main hybrid experiment on validation, tune fusion, then run the frozen configuration on test:

```bash
python scripts/06_run_qwen_improved.py run --split val --experiment hybrid-rerank-1
python scripts/06_run_qwen_improved.py tune --experiment hybrid-rerank-1
python scripts/06_run_qwen_improved.py run --split test --experiment hybrid-rerank-1
```

A test run without frozen validation fusion parameters is rejected unless alpha is supplied explicitly. The test split is never used to tune retrieval, examples, fusion, or prompt settings.

## Experiments

| Experiment | Meaning |
|---|---|
| zero-shot | all substantive labels, no demonstrations |
| random-1 / random-5 | full label set + 1 / 5 random demonstrations |
| retrieval-1 / retrieval-5 | dense retrieval + 1 / 5 retrieved demonstrations |
| hybrid-1 | hybrid shortlist + 1 retrieved example per candidate |
| hybrid-2 | hybrid shortlist + 2 retrieved examples per candidate |
| hybrid-rerank-1 | hybrid top-30, BGE reranking, 1 example per candidate |
| hybrid-rerank-2 | hybrid top-30, BGE reranking, 2 examples per candidate |

The hybrid path uses letter probabilities only with a small candidate set. Full 36-label MCQ is intentionally avoided because the letter space and top-logprob list are bounded.

## Fusion

Alpha is tuned on the validation set using macro-F1. The previous fixed alpha=0.6 is only a validation fallback.

Beta remains zero until a separate calibrated per-label-prior experiment is implemented.

## Embedding consistency

The Qdrant collection and query encoder must use the same embedding model. The repository now defaults to sentence-transformers/all-mpnet-base-v2 with the cuad_train_mpnet collection.

## Fine-tuning

```bash
python scripts/finetune/prepare_sft_data.py \
  --train data/splits/train/master_clauses_train.csv \
  --test data/splits/test/master_clauses_test.csv \
  --out-dir data/finetune

python scripts/finetune/train_lora.py \
  --base Qwen/Qwen3-8B \
  --data-dir data/finetune \
  --out output/ft_qwen3_8b_cuad
```

The fine-tuning template disables Qwen3 thinking when the tokenizer supports that switch.
