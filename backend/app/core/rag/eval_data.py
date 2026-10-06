"""Leakage-safe CUAD evaluation data helpers."""
from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pandas as pd

EXCLUDED_METADATA = {
    "Document Name",
    "Parties",
    "Agreement Date",
    "Effective Date",
    "Expiration Date",
}
VAL_RATIO = 0.10
VAL_SEED = 42


def load_clauses(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "clause_type" not in df.columns and "label" in df.columns:
        df["clause_type"] = df["label"]
    if "document_id" not in df.columns:
        df["document_id"] = df["Filename"]

    clean = (
        df["clause_text_clean"].fillna("").astype(str).str.strip()
        if "clause_text_clean" in df.columns
        else pd.Series("", index=df.index)
    )
    raw_col = (
        df["clause_text"].fillna("").astype(str).str.strip()
        if "clause_text" in df.columns
        else pd.Series("", index=df.index)
    )
    text = clean.where(clean.ne(""), raw_col)

    result = pd.DataFrame({
        "clause_index": df.index.astype(int),
        "document_id": df["document_id"].fillna("").astype(str).str.strip(),
        "clause_type": df["clause_type"].fillna("").astype(str).str.strip(),
        "clause_text": text,
    })
    if "is_metadata" in df.columns:
        meta = df["is_metadata"].fillna(False).astype(str).str.lower().eq("true")
        result = result.loc[~meta].copy()
    result = result.loc[
        result["document_id"].ne("")
        & result["clause_text"].ne("")
        & result["clause_type"].ne("")
        & ~result["clause_type"].isin(EXCLUDED_METADATA)
    ].reset_index(drop=True)
    return result


def document_disjoint_train_val(
    train_df: pd.DataFrame,
    *,
    val_ratio: float = VAL_RATIO,
    seed: int = VAL_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    docs = sorted(train_df["document_id"].unique().tolist())
    rng = random.Random(seed)
    rng.shuffle(docs)
    n_val = max(1, int(len(docs) * val_ratio))
    val_docs = set(docs[:n_val])
    val_df = train_df[train_df["document_id"].isin(val_docs)].copy()
    fit_df = train_df[~train_df["document_id"].isin(val_docs)].copy()
    if set(fit_df["document_id"]) & set(val_df["document_id"]):
        raise AssertionError("Validation and fit contracts overlap.")
    return fit_df.reset_index(drop=True), val_df.reset_index(drop=True)


def embed_texts(
    texts: list[str],
    model_name: str,
    *,
    batch_size: int = 32,
) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
    )
    return np.asarray(vectors, dtype=np.float32)


__all__ = [
    "EXCLUDED_METADATA",
    "load_clauses",
    "document_disjoint_train_val",
    "embed_texts",
]
