#build_qdrant.py
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient, models


PROJECT_ROOT = Path(__file__).resolve().parents[2]

for dotenv_path in (
    PROJECT_ROOT / ".env",
    PROJECT_ROOT / "scripts" / ".env",
):
    if dotenv_path.exists():
        load_dotenv(dotenv_path)
        break


EMBEDDINGS_FILE = (
    PROJECT_ROOT
    / "dataset"
    / "embeddings"
    / "train_embeddings.json"
)

METADATA_FILE = (
    PROJECT_ROOT
    / "dataset"
    / "embeddings"
    / "train_metadata.jsonl"
)


QDRANT_URL = os.getenv(
    "QDRANT_URL",
)

QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

QDRANT_PATH = os.getenv(
    "QDRANT_PATH",
    str(PROJECT_ROOT / "dataset" / "qdrant_local"),
)

QDRANT_COLLECTION = os.getenv(
    "QDRANT_COLLECTION",
    "cuad_train",
)

QDRANT_DISTANCE = os.getenv(
    "QDRANT_DISTANCE",
    "COSINE",
)


def validate_files():
    if not EMBEDDINGS_FILE.exists():
        raise FileNotFoundError(
            f"Embeddings file not found:\n{EMBEDDINGS_FILE}\n"
            "Run embed_train.py first."
        )

    if not METADATA_FILE.exists():
        raise FileNotFoundError(
            f"Metadata file not found:\n{METADATA_FILE}\n"
            "Run embed_train.py first."
        )


def load_embeddings():
    with open(EMBEDDINGS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    embeddings = data["embeddings"]

    if not embeddings:
        raise ValueError("No embeddings found.")

    dimension = len(embeddings[0])

    return embeddings, dimension


def load_metadata():
    metadata = []

    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                metadata.append(json.loads(line))

    return metadata


def get_distance():
    if QDRANT_DISTANCE.upper() == "COSINE":
        return models.Distance.COSINE

    if QDRANT_DISTANCE.upper() == "DOT":
        return models.Distance.DOT

    if QDRANT_DISTANCE.upper() == "EUCLID":
        return models.Distance.EUCLID

    raise ValueError(
        f"Unsupported QDRANT_DISTANCE: {QDRANT_DISTANCE}"
    )


def create_client():
    if QDRANT_URL:
        if QDRANT_API_KEY:
            return QdrantClient(
                url=QDRANT_URL,
                api_key=QDRANT_API_KEY,
            )

        return QdrantClient(
            url=QDRANT_URL,
        )

    return QdrantClient(path=QDRANT_PATH)


def create_collection(client, dimension):
    if client.collection_exists(QDRANT_COLLECTION):
        print(
            f"Collection '{QDRANT_COLLECTION}' already exists."
        )

        answer = input(
            "Delete and recreate it? [y/N]: "
        ).strip().lower()

        if answer == "y":
            client.delete_collection(QDRANT_COLLECTION)
        else:
            return

    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=models.VectorParams(
            size=dimension,
            distance=get_distance(),
        ),
    )

    print(
        f"Created collection: {QDRANT_COLLECTION}"
    )


def insert_vectors(client, embeddings, metadata):
    if len(embeddings) != len(metadata):
        raise ValueError(
            "Embeddings count does not match metadata count."
        )

    points = []

    for vector, record in zip(embeddings, metadata):
        points.append(
            models.PointStruct(
                id=record["id"],
                vector=vector,
                payload={
                    "document_id": record["document_id"],
                    "clause_type": record["clause_type"],
                    "clause_text": record["clause_text"],
                    "answer": record.get("answer"),
                    # Carried over from embed_train.py so queries can
                    # filter it out at search time too (e.g. Qdrant
                    # payload filter: is_metadata == False), not just at
                    # embedding time.
                    "is_metadata": record.get("is_metadata", False),
                },
            )
        )

    batch_size = 256

    for start in range(0, len(points), batch_size):
        batch = points[start:start + batch_size]

        client.upsert(
            collection_name=QDRANT_COLLECTION,
            points=batch,
            wait=True,
        )

        print(
            f"Inserted {min(start + batch_size, len(points))}"
            f"/{len(points)}"
        )


def verify_collection(client):
    info = client.get_collection(QDRANT_COLLECTION)

    print()
    print("=" * 60)
    print("QDRANT COLLECTION")
    print("=" * 60)
    print(f"Collection: {QDRANT_COLLECTION}")
    print(f"Vectors:    {info.points_count}")
    print(f"Status:     {info.status}")


def main():
    print("=" * 60)
    print("BUILD CUAD QDRANT COLLECTION")
    print("=" * 60)

    validate_files()

    embeddings, dimension = load_embeddings()
    metadata = load_metadata()

    print(f"Embeddings: {len(embeddings)}")
    print(f"Dimension:  {dimension}")
    print(f"Metadata:   {len(metadata)}")
    print(f"Qdrant:     {QDRANT_URL}")
    print(f"Collection: {QDRANT_COLLECTION}")

    client = create_client()

    create_collection(
        client,
        dimension,
    )

    insert_vectors(
        client,
        embeddings,
        metadata,
    )

    verify_collection(client)

    print()
    print("Qdrant build completed successfully.")


if __name__ == "__main__":
    main()