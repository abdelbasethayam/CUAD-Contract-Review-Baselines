#emded_train.py
import json
import os
import uuid
import time
from pathlib import Path

import cohere
import pandas as pd
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]

for dotenv_path in (
    PROJECT_ROOT / ".env",
    PROJECT_ROOT / "scripts" / ".env",
):
    if dotenv_path.exists():
        load_dotenv(dotenv_path)
        break


TRAIN_DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "splits"
    / "train"
    / "master_clauses_train.csv"
)

EMBEDDINGS_DIR = PROJECT_ROOT / "output" / "embeddings"
EMBEDDINGS_FILE = EMBEDDINGS_DIR / "train_embeddings.json"
METADATA_FILE = EMBEDDINGS_DIR / "train_metadata.jsonl"


COHERE_API_KEY = os.getenv("COHERE_API_KEY")
COHERE_MODEL = os.getenv(
    "COHERE_MODEL",
    os.getenv("COHERE_EMBED_MODEL", "embed-v4.0"),
)
EMBED_BATCH_SIZE = int(
    os.getenv("COHERE_BATCH_SIZE", os.getenv("EMBED_BATCH_SIZE", "96"))
)

# The dataset now tags each row with is_metadata (Document Name, Parties,
# Agreement/Effective/Expiration Date -- contract metadata, not a
# substantive legal clause type). Embedding those alongside real clauses
# pollutes clause-similarity search, so they're excluded by default.
# Set INCLUDE_METADATA_CLAUSES=true in .env to embed everything instead.
INCLUDE_METADATA_CLAUSES = os.getenv(
    "INCLUDE_METADATA_CLAUSES", "false"
).strip().lower() in {"1", "true", "yes"}


def validate_configuration():
    if not COHERE_API_KEY:
        raise ValueError("COHERE_API_KEY is missing from .env")

    if not TRAIN_DATA_PATH.exists():
        raise FileNotFoundError(
            f"Training data not found:\n{TRAIN_DATA_PATH}"
        )


def load_training_data():
    df = pd.read_csv(TRAIN_DATA_PATH)

    required_columns = {
        "document_id",
        "clause_type",
        "clause_text",
        "answer",
    }

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    if "is_metadata" not in df.columns:
        # Backward compatibility with an older dataset build that doesn't
        # carry the flag -- treat everything as a real clause.
        df["is_metadata"] = False

    return df


def clean_clause_text(value):
    if pd.isna(value):
        return None

    text = str(value).strip()

    if not text:
        return None

    # Defensive: older/raw exports sometimes leave the stringified-list
    # artifacts behind. The current dataset build already parses these,
    # but this keeps the script safe against a stale file.
    if text in {"[]", "nan", "None"}:
        return None

    return text


def clean_answer(value):
    """Return a real None instead of the literal string 'nan' for a
    missing answer -- a contract can have an extracted clause span with
    no annotated answer value, and that should stay null, not become a
    fake string that pollutes filtering/search on the 'answer' payload
    field later.
    """
    if pd.isna(value):
        return None

    text = str(value).strip()

    return text or None


def prepare_records(df):
    if not INCLUDE_METADATA_CLAUSES:
        before = len(df)
        df = df[~df["is_metadata"].astype(bool)]
        skipped_metadata = before - len(df)
    else:
        skipped_metadata = 0

    records = []

    for index, row in df.iterrows():
        clause_text = clean_clause_text(row["clause_text"])

        if clause_text is None:
            continue

        record_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{row['document_id']}::{row['clause_type']}::{index}",
            )
        )

        records.append(
            {
                "id": record_id,
                "document_id": str(row["document_id"]),
                "clause_type": str(row["clause_type"]),
                "clause_text": clause_text,
                "answer": clean_answer(row["answer"]),
                "is_metadata": bool(row["is_metadata"]),
            }
        )

    return records, skipped_metadata


def embed_records(records):
    client = cohere.ClientV2(api_key=COHERE_API_KEY)

    all_embeddings = []

    for start in range(0, len(records), EMBED_BATCH_SIZE):
        batch = records[start:start + EMBED_BATCH_SIZE]

        texts = [record["clause_text"] for record in batch]

        print(
            f"Embedding {start + 1}-{start + len(batch)} "
            f"of {len(records)}"
        )

        response = None
        delay = 5

        for attempt in range(1, 6):
            try:
                response = client.embed(
                    model=COHERE_MODEL,
                    input_type="search_document",
                    texts=texts,
                    embedding_types=["float"],
                )
                break
            except Exception as exc:
                status_code = getattr(exc, "status_code", None)

                if status_code != 429 or attempt == 5:
                    raise

                print(
                    f"Rate limited by Cohere; retrying batch in {delay} "
                    f"seconds (attempt {attempt}/5)."
                )
                time.sleep(delay)
                delay *= 2

        embeddings = response.embeddings.float

        if len(embeddings) != len(batch):
            raise RuntimeError(
                "Number of returned embeddings does not match batch size."
            )

        all_embeddings.extend(embeddings)

    return all_embeddings


def save_results(records, embeddings):
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)

    embedding_data = {
        "model": COHERE_MODEL,
        "count": len(records),
        "dimension": len(embeddings[0]) if embeddings else 0,
        "embeddings": embeddings,
    }

    with open(EMBEDDINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(embedding_data, f)

    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        for record in records:
            f.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )


def main():
    print("=" * 60)
    print("CUAD TRAIN EMBEDDING")
    print("=" * 60)

    validate_configuration()

    print(f"Training data: {TRAIN_DATA_PATH}")
    print(f"Cohere model: {COHERE_MODEL}")
    print(f"Include metadata rows: {INCLUDE_METADATA_CLAUSES}")

    df = load_training_data()

    print(f"Loaded rows: {len(df)}")

    records, skipped_metadata = prepare_records(df)

    print(f"Rows with valid clause text: {len(records)}")
    print(f"Skipped metadata rows: {skipped_metadata}")
    print(
        f"Skipped empty/invalid clauses: "
        f"{len(df) - skipped_metadata - len(records)}"
    )

    if not records:
        raise ValueError("No valid clause text found.")

    embeddings = embed_records(records)

    save_results(records, embeddings)

    print()
    print("=" * 60)
    print("EMBEDDING COMPLETED")
    print("=" * 60)
    print(f"Embeddings: {EMBEDDINGS_FILE}")
    print(f"Metadata:   {METADATA_FILE}")
    print(f"Vectors:    {len(embeddings)}")
    print(f"Dimension:  {len(embeddings[0])}")


if __name__ == "__main__":
    main()