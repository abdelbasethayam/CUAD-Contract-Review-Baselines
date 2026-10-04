#!/usr/bin/env python3
"""Download CUAD clause-classification data from Hugging Face for fine-tuning.

Dataset: dvgodoy/CUAD_v1_Contract_Understanding_clause_classification
(~13k labeled clauses — primary path toward 85–92% after LoRA).

Usage:
  pip install datasets pandas
  python scripts/bootstrap_cuad_hf_data.py --out data/external/cuad_hf_clauses.parquet
"""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/external/cuad_hf_clauses.parquet"),
    )
    parser.add_argument("--max-rows", type=int, default=0, help="0 = all")
    args = parser.parse_args()

    from datasets import load_dataset

    ds = load_dataset("dvgodoy/CUAD_v1_Contract_Understanding_clause_classification")
    split = ds["train"] if "train" in ds else ds[list(ds.keys())[0]]
    df = split.to_pandas()
    if args.max_rows and args.max_rows > 0:
        df = df.head(args.max_rows)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(f"Wrote {len(df)} rows -> {args.out}")
    if "label" in df.columns:
        print(df["label"].value_counts().head(15))


if __name__ == "__main__":
    main()
