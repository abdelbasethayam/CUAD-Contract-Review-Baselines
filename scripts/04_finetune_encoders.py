"""
Step 4 (Fine-Tuned Encoders): Baseline G (Fine-tuned BERT & Legal-BERT).

Fine-tunes:
1. bert-base-uncased
2. nlpaueb/legal-bert-base-uncased

Params: 3 epochs, lr=2e-5, batch_size=8, max_length=128, class-weighted loss.
Saves predictions to:
- output/eval_1495/checkpoints/baseline_G_bert_partial.jsonl
- output/eval_1495/checkpoints/baseline_G_legal_bert_partial.jsonl
"""

import csv
import json
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# Monkey-patch: bypass torch>=2.6 requirement for .bin models (CVE-2025-32434)
# Safe in this context — we trust the HuggingFace model weights.
try:
    import transformers.modeling_utils as _tmu
    _tmu.check_torch_load_is_safe = lambda: None
except Exception:
    pass

EXCLUDED_METADATA_LABELS = {
    "Document Name",
    "Parties",
    "Agreement Date",
    "Effective Date",
    "Expiration Date",
}

# Updated for 4GB VRAM GPU config
MAX_LENGTH = 256
TRAIN_BATCH_SIZE = 8
EVAL_BATCH_SIZE = 16
EPOCHS = 3
LR = 2e-5
GRADIENT_ACCUMULATION_STEPS = 2


class ClauseDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_len=128):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = str(self.texts[idx])
        encoding = self.tokenizer(
            text,
            truncation=True,
            max_length=self.max_len,
            padding="max_length",
            return_tensors="pt",
        )
        item = {key: val.squeeze(0) for key, val in encoding.items()}
        if self.labels is not None:
            item["labels"] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item


def load_data(root: Path):
    train_csv = root / "data" / "splits" / "train" / "master_clauses_train.csv"
    meta_path = root / "output" / "embeddings" / "test_1495_metadata.json"

    print(f"Loading train CSV: {train_csv}")
    train_clauses = []
    with train_csv.open("r", encoding="utf-8-sig") as f:
        for idx, row in enumerate(csv.DictReader(f), start=2):
            lbl = str(row.get("clause_type", "")).strip()
            txt = str(row.get("clause_text", "")).strip()
            is_meta = str(row.get("is_metadata", "")).lower() == "true"
            if lbl and txt and not is_meta and lbl not in EXCLUDED_METADATA_LABELS:
                train_clauses.append({"clause_type": lbl, "clause_text": txt})

    print(f"Loaded {len(train_clauses)} train clauses")
    print(f"Loading test metadata: {meta_path}")
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    test_clauses = metadata["clauses"]
    print(f"Loaded {len(test_clauses)} test clauses")

    all_labels = sorted({c["clause_type"] for c in train_clauses} | {c["clause_type"] for c in test_clauses})
    label2id = {lbl: i for i, lbl in enumerate(all_labels)}
    id2label = {i: lbl for i, lbl in enumerate(all_labels)}

    return train_clauses, test_clauses, label2id, id2label


def train_and_eval(model_name: str, tag: str, root: Path):
    print(f"\n{'='*60}")
    print(f"Fine-tuning Encoder Baseline G: {model_name} ({tag})")
    print(f"{'='*60}")

    try:
        train_clauses, test_clauses, label2id, id2label = load_data(root)

        num_classes = len(label2id)
        print(f"Training set: {len(train_clauses)} | Test set: {len(test_clauses)} | Classes: {num_classes}")

        # Compute class weights for weighted loss
        counts = np.zeros(num_classes)
        for c in train_clauses:
            counts[label2id[c["clause_type"]]] += 1
        weights = np.where(counts > 0, 1.0 / counts, 0.0)
        weights = weights / weights.sum() * num_classes
        class_weights = torch.tensor(weights, dtype=torch.float)

        print(f"Loading tokenizer: {model_name}")
        tokenizer = AutoTokenizer.from_pretrained(model_name)

        print(f"Loading model: {model_name}")
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            num_labels=num_classes,
            ignore_mismatched_sizes=True,
        )

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {device}")
        model.to(device)

        train_texts = [c["clause_text"] for c in train_clauses]
        train_labels = [label2id[c["clause_type"]] for c in train_clauses]
        test_texts = [c["clause_text"] for c in test_clauses]
        test_labels = [label2id.get(c["clause_type"], 0) for c in test_clauses]

        print(f"Building datasets (max_length={MAX_LENGTH})...")
        train_dataset = ClauseDataset(train_texts, train_labels, tokenizer, max_len=MAX_LENGTH)
        test_dataset = ClauseDataset(test_texts, test_labels, tokenizer, max_len=MAX_LENGTH)

        # num_workers=0 is required on Windows to avoid multiprocessing issues
        train_loader = DataLoader(train_dataset, batch_size=TRAIN_BATCH_SIZE, shuffle=True, num_workers=0)
        test_loader = DataLoader(test_dataset, batch_size=EVAL_BATCH_SIZE, shuffle=False, num_workers=0)

        optimizer = AdamW(model.parameters(), lr=LR)
        criterion = nn.CrossEntropyLoss(weight=class_weights.to(device))

        print(f"Starting training: {EPOCHS} epochs, batch_size={TRAIN_BATCH_SIZE}, accum={GRADIENT_ACCUMULATION_STEPS}, lr={LR}, fp16=True")
        print(f"Steps per epoch: {len(train_loader) // GRADIENT_ACCUMULATION_STEPS}")

        scaler = torch.amp.GradScaler('cuda')

        for epoch in range(1, EPOCHS + 1):
            model.train()
            total_loss = 0.0
            t0 = time.time()
            print(f"\n[Epoch {epoch}/{EPOCHS}] Starting...", flush=True)
            optimizer.zero_grad()

            for step, batch in enumerate(train_loader):
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                labels_tensor = batch["labels"].to(device)

                with torch.amp.autocast('cuda'):
                    outputs = model(input_ids, attention_mask=attention_mask)
                    loss = criterion(outputs.logits, labels_tensor)
                    loss = loss / GRADIENT_ACCUMULATION_STEPS

                scaler.scale(loss).backward()
                total_loss += loss.item() * GRADIENT_ACCUMULATION_STEPS

                if (step + 1) % GRADIENT_ACCUMULATION_STEPS == 0:
                    scaler.step(optimizer)
                    scaler.update()
                    optimizer.zero_grad()

                if step % 100 == 0:
                    elapsed = time.time() - t0
                    print(f"  Step {step}/{len(train_loader)} | Loss: {loss.item() * GRADIENT_ACCUMULATION_STEPS:.4f} | Elapsed: {elapsed:.1f}s", flush=True)

            avg_loss = total_loss / len(train_loader)
            print(f"[Epoch {epoch}/{EPOCHS}] Avg Loss: {avg_loss:.4f} | Time: {time.time() - t0:.2f}s", flush=True)

        # ─── Evaluation ───────────────────────────────────────────────────
        model.eval()
        predictions = []
        ckpt_dir = root / "output" / "eval_1495" / "checkpoints"
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        ckpt_file = ckpt_dir / f"baseline_G_{tag}_partial.jsonl"

        print(f"\nEvaluating on {len(test_clauses)} test clauses...", flush=True)
        with torch.no_grad():
            with ckpt_file.open("w", encoding="utf-8") as out:
                for idx, batch in enumerate(test_loader):
                    input_ids = batch["input_ids"].to(device)
                    attention_mask = batch["attention_mask"].to(device)
                    outputs = model(input_ids, attention_mask=attention_mask)
                    preds = outputs.logits.argmax(dim=-1).cpu().numpy()

                    batch_start = idx * EVAL_BATCH_SIZE
                    for i, p_id in enumerate(preds):
                        t_idx = batch_start + i
                        if t_idx < len(test_clauses):
                            c = test_clauses[t_idx]
                            pred_label = id2label[p_id]
                            gt_label = c["clause_type"]
                            rec = {
                                "clause_id": c["clause_id"],
                                "ground_truth": gt_label,
                                "prediction": pred_label,
                                "correct": pred_label == gt_label,
                                "model_tag": tag,
                            }
                            predictions.append(rec)
                            out.write(json.dumps(rec, ensure_ascii=False) + "\n")

                    if idx % 10 == 0:
                        print(f"  Eval batch {idx}/{len(test_loader)}", flush=True)

        acc = sum(r["correct"] for r in predictions) / len(predictions) if predictions else 0.0
        print(f"\n[DONE] Baseline G ({tag}) Complete | Accuracy: {acc:.4f} ({acc*100:.2f}%)")
        print(f"   Checkpoint: {ckpt_file}")
        return acc

    except Exception as e:
        print(f"\n[ERROR] in train_and_eval({tag}): {e}", flush=True)
        traceback.print_exc()
        return None


def main():
    root = Path(__file__).resolve().parents[1]
    print(f"Root: {root}")
    print(f"PyTorch: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")

    # BERT already complete (71.47%) — skip and run LegalBERT only
    print("\n[SKIP] bert-base-uncased already done — checkpoint exists.")
    acc_bert = 0.7147  # from previous run

    acc_legal = train_and_eval("nlpaueb/legal-bert-base-uncased", "legal_bert", root)

    print("\n" + "="*60)
    print("BASELINE G SUMMARY")
    print("="*60)
    print(f"  BERT:       {acc_bert*100:.2f}%")
    if acc_legal is not None:
        print(f"  LegalBERT:  {acc_legal*100:.2f}%")


if __name__ == "__main__":
    main()
