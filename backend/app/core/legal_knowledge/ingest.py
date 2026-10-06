"""Ingest curated legal guidance into a separate Qdrant collection.

Run from the backend directory:
    python -m app.core.legal_knowledge.ingest
"""

from __future__ import annotations

import argparse
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path

from qdrant_client import models

from ..config import LEGAL_KNOWLEDGE_COLLECTION, LEGAL_KNOWLEDGE_PATH, LEGAL_KNOWLEDGE_REGISTRY_PATH
from ..rag.embedder import embed_documents, make_cohere_client
from ..rag.retriever import make_qdrant_client

REQUIRED_METADATA = {
    "source_name",
    "source_url",
    "title",
    "clause_category",
    "document_filename",
    "source_tier",
    "authority_status",
    "jurisdiction",
    "contract_type",
    "access_type",
    "license_status",
}

DOCUMENTATION_ONLY_FILES = {
    "risk_indicators.md",
    "source_catalog.md",
    "clause_coverage.md",
}


def load_source_registry(path: Path = LEGAL_KNOWLEDGE_REGISTRY_PATH) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(item.get("source_name")): dict(item)
        for item in (data.get("sources") or [])
        if item.get("source_name")
    }


def parse_knowledge_document(path: Path, registry: dict[str, dict] | None = None) -> dict:    text = path.read_text(encoding="utf-8")
    metadata: dict[str, str] = {}
    body = text

    if text.startswith("---"):
        _, raw_metadata, body = text.split("---", 2)
        for line in raw_metadata.strip().splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()

    registry = registry or {}
    registry_record = registry.get(metadata.get("source_name"), {})
    metadata = {**registry_record, **metadata}
    missing = REQUIRED_METADATA - set(metadata)
    if missing:
        raise ValueError(f"{path} is missing metadata fields: {sorted(missing)}")

    metadata["document_filename"] = metadata.get("document_filename") or path.name
    return {"metadata": metadata, "text": body.strip()}


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunks.append(normalized[start:end].strip())
        if end == len(normalized):
            break
        start = max(0, end - overlap)
    return [chunk for chunk in chunks if chunk]


def load_curated_chunks(base_path: Path = LEGAL_KNOWLEDGE_PATH) -> list[dict]:
    chunks: list[dict] = []
    for path in sorted(base_path.rglob("*.md")):
        if path.name in DOCUMENTATION_ONLY_FILES:
            continue
        parsed = parse_knowledge_document(path)
        metadata = parsed["metadata"]
        for index, chunk in enumerate(chunk_text(parsed["text"])):
            chunk_key = f"{path.as_posix()}::{index}"
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_key))
            chunks.append(
                {
                    "id": chunk_id,
                    "text": chunk,
                    "metadata": {
                        "source_name": metadata["source_name"],
                        "source_url": metadata["source_url"],
                        "title": metadata["title"],
                        "clause_category": metadata["clause_category"],
                        "document_filename": metadata["document_filename"],
                        "chunk_id": chunk_id,
                    },
                }
            )
    return chunks


def recreate_collection(client, vector_size: int, collection_name: str) -> None:
    if client.collection_exists(collection_name):
        return
    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=vector_size,
            distance=models.Distance.COSINE,
        ),
    )


def ingest_legal_knowledge(
    collection_name: str = LEGAL_KNOWLEDGE_COLLECTION,
    base_path: Path = LEGAL_KNOWLEDGE_PATH,
) -> int:
    chunks = load_curated_chunks(base_path)
    if not chunks:
        raise ValueError(f"No legal knowledge markdown files found under {base_path}")

    cohere_client = make_cohere_client()
    vectors = embed_documents(cohere_client, [chunk["text"] for chunk in chunks])
    if not vectors:
        raise RuntimeError("No embeddings were created for legal knowledge chunks.")

    qdrant_client = make_qdrant_client()
    recreate_collection(qdrant_client, len(vectors[0]), collection_name)

    points = []
    for chunk, vector in zip(chunks, vectors):
        payload = {
            "retrieved_text": chunk["text"],
            **chunk["metadata"],
        }
        points.append(
            models.PointStruct(
                id=chunk["id"],
                vector=vector,
                payload=payload,
            )
        )

    qdrant_client.upsert(collection_name=collection_name, points=points, wait=True)
    return len(points)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", default=LEGAL_KNOWLEDGE_COLLECTION)
    parser.add_argument("--path", type=Path, default=LEGAL_KNOWLEDGE_PATH)
    args = parser.parse_args()

    count = ingest_legal_knowledge(
        collection_name=args.collection,
        base_path=args.path,
    )
    print(f"Ingested {count} legal knowledge chunks into {args.collection}.")


if __name__ == "__main__":
    main()
