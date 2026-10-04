#!/usr/bin/env python3
"""Build JSONL SFT data from master_clauses CSVs for CUAD classification.

Uses document-disjoint validation when document_id is available.

Usage:
  python scripts/finetune/prepare_sft_data.py \\
    --train data/splits/train/master_clauses_train.csv \\
    --out-dir data/finetune
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

import pandas as pd

METADATA = {
    "Document Name",
    "Parties",
    "Agreement Date",
    "Effective Date",
    "Expiration Date",
}

SYSTEM = (
    "You are an expert contract analyst. Assign exactly one CUAD clause category "
    "that matches the MAIN legal function of the clause. Reply with JSON only: "
    '{"clause_type": "<label>"}.'
)


def _load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    text_col = "clause_text" if "clause_text" in df.columns else "text"
    label_col = "clause_type" if "clause_type" in df.columns else "label"
    if text_col not in df.columns or label_col not in df.columns:
        raise SystemExit(f"Need text+label columns in {path}")
    df = df.rename(columns={text_col: "clause_text", label_col: "clause_type"})
    if "is_metadata" in df.columns:
        df = df.loc[~df["is_metadata"].astype(bool)]
    df = df[~df["clause_type"].isin(METADATA)]
    df["clause_text"] = df["clause_text"].astype(str).str.strip()
    df["clause_type"] = df["clause_type"].astype(str).str.strip()
    df = df[df["clause_text"].str.len() > 20]
    return df


def _row_to_messages(text: str, label: str, label_list: str) -> dict:
    user = (
        f"CUAD labels (choose one):\n{label_list}\n\n"
        f"Clause:\n\"\"\"{text[:3500]}\"\"\"\n\n"
        'Respond with JSON only: {"clause_type": "<exact label from the list>"}'
    )
    assistant = json.dumps({"clause_type": label}, ensure_ascii=False)
    return {
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "clause_type": label,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--train", type=Path, required=True)
    p.add_argument("--test", type=Path, default=None)
    p.add_argument("--out-dir", type=Path, default=Path("data/finetune"))
    p.add_argument("--val-ratio", type=float, default=0.1)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    train_df = _load_csv(args.train)
    labels = sorted(train_df["clause_type"].unique())
    label_list = "\n".join(f"- {x}" for x in labels)

    rng = random.Random(args.seed)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    if "document_id" in train_df.columns:
        docs = sorted(train_df["document_id"].astype(str).unique())
        rng.shuffle(docs)
        n_val = max(1, int(len(docs) * args.val_ratio))
        val_docs = set(docs[:n_val])
        val_df = train_df[train_df["document_id"].astype(str).isin(val_docs)]
        tr_df = train_df[~train_df["document_id"].astype(str).isin(val_docs)]
    else:
        train_df = train_df.sample(frac=1.0, random_state=args.seed)
        n_val = max(1, int(len(train_df) * args.val_ratio))
        val_df = train_df.iloc[:n_val]
        tr_df = train_df.iloc[n_val:]

    def write_jsonl(df: pd.DataFrame, path: Path) -> None:
        with path.open("w", encoding="utf-8") as f:
            for _, row in df.iterrows():
                rec = _row_to_messages(row["clause_text"], row["clause_type"], label_list)
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    write_jsonl(tr_df, args.out_dir / "train.jsonl")
    write_jsonl(val_df, args.out_dir / "val.jsonl")
    (args.out_dir / "labels.json").write_text(
        json.dumps(labels, indent=2), encoding="utf-8"
    )

    counts = train_df["clause_type"].value_counts().to_dict()
    (args.out_dir / "label_counts.json").write_text(
        json.dumps(counts, indent=2), encoding="utf-8"
    )

    if args.test and args.test.exists():
        test_df = _load_csv(args.test)
        write_jsonl(test_df, args.out_dir / "test.jsonl")

    print(f"train={len(tr_df)} val={len(val_df)} labels={len(labels)}")
    print(f"Wrote {args.out_dir}")


if __name__ == "__main__":
    main()
