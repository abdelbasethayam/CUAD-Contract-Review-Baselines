#!/usr/bin/env python3
"""Evaluate a fine-tuned causal LM on CUAD classification JSONL.

Reports accuracy and macro-F1.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel


def parse_label(text: str) -> str | None:
    text = text.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and isinstance(obj.get("clause_type"), str):
            return obj["clause_type"].strip()
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{\s*\"clause_type\"\s*:\s*\"([^\"]+)\"", text)
    return m.group(1).strip() if m else None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="Qwen/Qwen2.5-7B-Instruct")
    p.add_argument("--adapter", type=Path, required=True)
    p.add_argument("--jsonl", type=Path, required=True)
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()

    tok = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.base, trust_remote_code=True, torch_dtype="auto", device_map="auto"
    )
    model = PeftModel.from_pretrained(model, str(args.adapter))
    model.eval()

    rows = [json.loads(l) for l in args.jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        rows = rows[: args.limit]

    correct = 0
    per = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "n": 0})

    for row in rows:
        gold = row.get("clause_type") or ""
        messages = [m for m in row["messages"] if m["role"] != "assistant"]
        prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tok(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=64, do_sample=False)
        gen = tok.decode(out[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=True)
        pred = parse_label(gen) or ""
        per[gold]["n"] += 1
        if pred == gold:
            correct += 1
            per[gold]["tp"] += 1
        else:
            per[gold]["fn"] += 1
            if pred:
                per[pred]["fp"] += 1

    n = max(len(rows), 1)
    f1s = []
    for lab, s in per.items():
        if s["n"] == 0:
            continue
        prec = s["tp"] / (s["tp"] + s["fp"]) if (s["tp"] + s["fp"]) else 0.0
        rec = s["tp"] / (s["tp"] + s["fn"]) if (s["tp"] + s["fn"]) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        f1s.append(f1)

    macro = sum(f1s) / len(f1s) if f1s else 0.0
    print(f"n={len(rows)} accuracy={correct/n:.4f} macro_f1={macro:.4f}")


if __name__ == "__main__":
    main()
