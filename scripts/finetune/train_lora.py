#!/usr/bin/env python3
"""LoRA SFT for CUAD clause classification.

Recommended base (best accuracy / macro-F1 tradeoff for this task):
  Qwen/Qwen3-8B

Lighter alternative:
  Qwen/Qwen3-4B-Instruct-2507   (if available) or Qwen/Qwen3-4B-Instruct

Not recommended as primary FT base for classification:
  Qwen/Qwen3-4B-Thinking-2507  (long think traces; weaker structured JSON)

Usage:
  pip install "torch" transformers datasets peft trl accelerate bitsandbytes
  # Optional faster: pip install unsloth

  python scripts/finetune/prepare_sft_data.py \\
    --train data/splits/train/master_clauses_train.csv \\
    --test data/splits/test/master_clauses_test.csv \\
    --out-dir data/finetune

  python scripts/finetune/train_lora.py \\
    --base Qwen/Qwen2.5-7B-Instruct \\
    --data-dir data/finetune \\
    --out output/ft_qwen3_8b_cuad
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        default="Qwen/Qwen2.5-7B-Instruct",
        help="HF model id. Prefer Instruct over Thinking for classification.",
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data/finetune"))
    parser.add_argument("--out", type=Path, default=Path("output/ft_qwen25_7b_cuad"))
    parser.add_argument("--max-seq-len", type=int, default=2048)
    parser.add_argument("--epochs", type=float, default=2.0)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--max-steps", type=int, default=-1)
    args = parser.parse_args()

    train_path = args.data_dir / "train.jsonl"
    val_path = args.data_dir / "val.jsonl"
    if not train_path.exists():
        raise SystemExit(f"Missing {train_path}. Run prepare_sft_data.py first.")

    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import LoraConfig
    from trl import SFTTrainer, SFTConfig

    data_files = {"train": str(train_path)}
    if val_path.exists():
        data_files["validation"] = str(val_path)
    ds = load_dataset("json", data_files=data_files)

    tokenizer = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.base,
        trust_remote_code=True,
        torch_dtype="auto",
        device_map="auto",
    )

    def formatting(example):
        # Chat template when available
        messages = example["messages"]
        if hasattr(tokenizer, "apply_chat_template"):
            try:
                text = tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=False,
                    enable_thinking=False,
                )
            except TypeError:
                text = tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=False
                )
        else:
            parts = []
            for m in messages:
                parts.append(f"{m['role'].upper()}:\n{m['content']}")
            text = "\n\n".join(parts)
        return {"text": text}

    ds = ds.map(formatting)

    lora = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )

    args.out.mkdir(parents=True, exist_ok=True)
    sft_args = SFTConfig(
        output_dir=str(args.out),
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        logging_steps=10,
        save_strategy="epoch",
        eval_strategy="epoch" if "validation" in ds else "no",
        bf16=True,
        max_length=args.max_seq_len,
        dataset_text_field="text",
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_args,
        train_dataset=ds["train"],
        eval_dataset=ds["validation"] if "validation" in ds else None,
        peft_config=lora,
        processing_class=tokenizer,
    )
    trainer.train()
    trainer.save_model(str(args.out / "adapter"))
    tokenizer.save_pretrained(str(args.out / "adapter"))

    meta = {
        "base": args.base,
        "recommended": "Qwen/Qwen2.5-7B-Instruct",
        "data_dir": str(args.data_dir),
        "lora_r": args.lora_r,
        "epochs": args.epochs,
    }
    (args.out / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Saved adapter -> {args.out / 'adapter'}")
    print("Next: merge or load adapter in Ollama / vLLM; eval with scripts/finetune/eval_sft.py")


if __name__ == "__main__":
    main()
