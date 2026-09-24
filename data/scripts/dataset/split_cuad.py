#split_cuad.py
"""
Prepare the CUAD dataset for the clause-classification task.

Pipeline
--------
1. Load the raw master_clauses.csv (wide format: 1 row = 1 contract, 41
   clause-type column pairs: "<Clause Type>" text column + its matching
   "<Clause Type>-Answer" column).
2. Split CONTRACTS (not clauses) into train/test. Splitting happens before
   any reshaping, so every clause belonging to a given contract stays on
   the same side of the split -- this is what prevents data leakage.
3. Reshape each split from wide -> long format (1 row = 1 extracted clause
   span):
       document_id | clause_type | clause_text | answer | is_metadata

Fixes applied vs. the earlier draft of this script
----------------------------------------------------
1. Inconsistent "-Answer" column-name spacing in the raw file
   (e.g. "Non-Compete-Answer" vs "Notice Period To Terminate Renewal-
   Answer" with a stray space) meant a naive exact-suffix match silently
   missed one Answer column and turned it into a bogus 42nd clause_type
   category instead of merging it into the "answer" field of the real
   category. This script matches the suffix with a regex that tolerates
   any spacing/case, so every Answer column is found and merged correctly.
2. clause_text was left as a raw stringified Python list (e.g.
   "['some clause text']") instead of being parsed into plain text.
3. Contracts can have MULTIPLE extracted spans for one clause type. The
   earlier long-format file kept the whole list as one string per row;
   here each span is exploded into its own row, which is the right shape
   for a text classification dataset.
4. Five columns are contract metadata, not substantive/risk-relevant
   clause types: Document Name, Parties, Agreement Date, Effective Date,
   Expiration Date. They are kept in the output (nothing is silently
   dropped) but flagged with is_metadata=True so they can be filtered out
   of the classification label set with one line: df[~df.is_metadata].

Usage
-----
    python prepare_clause_dataset.py

Adjust MASTER_PATH / TRAIN_DIR / TEST_DIR below to match your repo layout.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

# --------------------------------------------------------------------------
# Paths -- adjust to your repo layout
# --------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]

MASTER_PATH = (
    PROJECT_ROOT / "dataset" / "raw" / "cuad" / "CUAD_v1" / "master_clauses.csv"
)

TRAIN_DIR = PROJECT_ROOT / "dataset" / "splits" / "train"
TEST_DIR = PROJECT_ROOT / "dataset" / "splits" / "test"

# Original wide files (1 row = 1 contract), kept for reference so you can
# re-derive other views later without re-running the split.
TRAIN_WIDE_PATH = TRAIN_DIR / "master_clauses_train_wide.csv"
TEST_WIDE_PATH = TEST_DIR / "master_clauses_test_wide.csv"

# Long-format files (1 row = 1 clause span) -- use these for classification.
TRAIN_LONG_PATH = TRAIN_DIR / "master_clauses_train.csv"
TEST_LONG_PATH = TEST_DIR / "master_clauses_test.csv"

TRAIN_SIZE = 410
TEST_SIZE = 100
RANDOM_STATE = 42

ID_COL = "Filename"

# Contract metadata -- not a "clause type" you'd classify for risk purposes.
# Flagged, not deleted.
METADATA_FIELDS = {
    "Document Name",
    "Parties",
    "Agreement Date",
    "Effective Date",
    "Expiration Date",
}

# Matches "-Answer", "- Answer", "-  answer", any case, at the end of a
# column name. Handles the inconsistent spacing in the raw file.
ANSWER_SUFFIX_RE = re.compile(r"\s*-\s*answer\s*$", re.IGNORECASE)


def discover_clause_columns(columns: list[str]) -> dict[str, tuple[str, str | None]]:
    """Map each clause-type name -> (text_column, answer_column | None)."""
    answer_cols: dict[str, str] = {}
    text_cols: list[str] = []

    for col in columns:
        if col == ID_COL:
            continue
        if ANSWER_SUFFIX_RE.search(col):
            base = ANSWER_SUFFIX_RE.sub("", col).strip()
            answer_cols[base] = col
        else:
            text_cols.append(col)

    return {col: (col, answer_cols.get(col)) for col in text_cols}


def parse_spans(raw: object) -> list[str]:
    """Parse a stringified Python list of extracted clause spans."""
    if pd.isna(raw):
        return []
    raw = str(raw).strip()
    if not raw:
        return []
    try:
        parsed = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return [raw]
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [str(parsed).strip()]


def wide_to_long(df: pd.DataFrame) -> pd.DataFrame:
    """Explode a wide (1 row = 1 contract) frame into long clause-span rows."""
    clause_map = discover_clause_columns(list(df.columns))
    rows = []

    for _, row in df.iterrows():
        doc_id = row[ID_COL]
        for clause_type, (text_col, answer_col) in clause_map.items():
            spans = parse_spans(row[text_col])
            if not spans:
                continue
            answer = row[answer_col] if answer_col else None
            for span in spans:
                rows.append(
                    {
                        "document_id": doc_id,
                        "clause_type": clause_type,
                        "clause_text": span,
                        "answer": answer,
                        "is_metadata": clause_type in METADATA_FIELDS,
                    }
                )

    return pd.DataFrame(rows)


def main() -> None:
    if not MASTER_PATH.exists():
        raise FileNotFoundError(f"Dataset not found:\n{MASTER_PATH}")

    df = pd.read_csv(MASTER_PATH, encoding="utf-8-sig")
    print(f"Dataset shape: {df.shape}")

    if len(df) != TRAIN_SIZE + TEST_SIZE:
        raise ValueError(
            f"Expected {TRAIN_SIZE + TEST_SIZE} contracts, but found {len(df)}."
        )

    if df[ID_COL].duplicated().any():
        raise ValueError("Duplicate contract filenames found in the dataset.")

    # Split at CONTRACT level, before any reshaping. This is what keeps
    # every clause of a given contract on one side of the split.
    train_df, test_df = train_test_split(
        df,
        train_size=TRAIN_SIZE,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        shuffle=True,
    )

    train_names = set(train_df[ID_COL])
    test_names = set(test_df[ID_COL])
    overlap = train_names.intersection(test_names)
    if overlap:
        raise ValueError(
            f"Data leakage detected: {len(overlap)} contracts exist in both "
            "train and test."
        )

    TRAIN_DIR.mkdir(parents=True, exist_ok=True)
    TEST_DIR.mkdir(parents=True, exist_ok=True)

    train_df.to_csv(TRAIN_WIDE_PATH, index=False, encoding="utf-8-sig")
    test_df.to_csv(TEST_WIDE_PATH, index=False, encoding="utf-8-sig")

    train_long = wide_to_long(train_df)
    test_long = wide_to_long(test_df)

    train_long.to_csv(TRAIN_LONG_PATH, index=False, encoding="utf-8-sig")
    test_long.to_csv(TEST_LONG_PATH, index=False, encoding="utf-8-sig")

    n_types_train = train_long.loc[~train_long["is_metadata"], "clause_type"].nunique()
    n_types_test = test_long.loc[~test_long["is_metadata"], "clause_type"].nunique()

    print("\nSplit completed successfully.")
    print(f"Total contracts: {len(df)}")
    print(f"Train contracts: {len(train_df)}  -> {len(train_long)} clause-span rows")
    print(f"Test contracts:  {len(test_df)}  -> {len(test_long)} clause-span rows")
    print(f"Classification clause types found (metadata excluded): "
          f"train={n_types_train}, test={n_types_test}")
    print(f"\nWide files (reference):\n  {TRAIN_WIDE_PATH}\n  {TEST_WIDE_PATH}")
    print(f"\nLong files (use these for classification):\n  {TRAIN_LONG_PATH}\n  {TEST_LONG_PATH}")


if __name__ == "__main__":
    main()