#!/usr/bin/env python3
"""Validate and hash the local hashing CUAD and legal-knowledge Qdrant indexes."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from qdrant_client import QdrantClient

ROOT = Path(__file__).resolve().parents[2]
QDRANT_PATH = ROOT / "data" / "qdrant_local"
TRAIN_MANIFEST = ROOT / "data" / "risk" / "results" / "local_hashing_cuad_index_manifest.json"
LEGAL_COLLECTION = "legal_knowledge_hashing"
CUAD_COLLECTION = "cuad_train_hashing"
LEGAL_MD_ROOT = ROOT / "backend" / "data" / "legal_knowledge"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    train_manifest = json.loads(TRAIN_MANIFEST.read_text(encoding="utf-8"))
    legal_docs = [
        p for p in sorted(LEGAL_MD_ROOT.rglob("*.md"))
        if p.name not in {"risk_indicators.md", "source_catalog.md", "clause_coverage.md"}
    ]
    registry = LEGAL_MD_ROOT / "source_registry.json"
    legal_doc_hashes = {p.relative_to(ROOT).as_posix(): sha256(p) for p in legal_docs}

    client = QdrantClient(path=str(QDRANT_PATH))
    try:
        expected = {
            CUAD_COLLECTION: int(train_manifest["counts"]["eligible_train_rows"]),
            LEGAL_COLLECTION: 19,
        }
        collections = {}
        problems = []
        for name, expected_count in expected.items():
            if not client.collection_exists(name):
                problems.append(f"missing_collection:{name}")
                continue
            info = client.get_collection(name)
            size = int(info.config.params.vectors.size)
            count = int(info.points_count or 0)
            if count != expected_count:
                problems.append(f"count_mismatch:{name}:{count}!={expected_count}")
            if size != 768:
                problems.append(f"dimension_mismatch:{name}:{size}!=768")
            seen = 0
            metadata_bad = 0
            offset = None
            while True:
                points, offset = client.scroll(
                    collection_name=name,
                    limit=512,
                    offset=offset,
                    with_payload=["embedding_backend", "embedding_dimension", "document_id", "split", "source_name", "source_tier"],
                    with_vectors=False,
                )
                for point in points:
                    seen += 1
                    payload = point.payload or {}
                    if payload.get("embedding_backend") != "local_hashing":
                        metadata_bad += 1
                    if int(payload.get("embedding_dimension") or -1) != 768:
                        metadata_bad += 1
                    if name == CUAD_COLLECTION and payload.get("split") != "train":
                        metadata_bad += 1
                    if name == LEGAL_COLLECTION and not payload.get("source_name"):
                        metadata_bad += 1
                if offset is None:
                    break
            if metadata_bad:
                problems.append(f"payload_metadata_failures:{name}:{metadata_bad}")
            collections[name] = {
                "point_count": count,
                "scanned_point_count": seen,
                "vector_dimension": size,
                "metadata_failures": metadata_bad,
            }
    finally:
        client.close()

    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not problems else "FAIL",
        "embedding_backend": "local_hashing",
        "embedding_spec": {
            "implementation": "sklearn.feature_extraction.text.HashingVectorizer",
            "dimension": 768,
            "ngram_range": [1, 2],
            "alternate_sign": False,
            "normalization": "l2",
            "caveat": "Lexical-vector retrieval; not a pretrained semantic embedding model.",
        },
        "qdrant_path": "data/qdrant_local",
        "cuad_train_collection": CUAD_COLLECTION,
        "legal_knowledge_collection": LEGAL_COLLECTION,
        "collections": collections,
        "sources": {
            "train_index_manifest_sha256": sha256(TRAIN_MANIFEST),
            "legal_source_registry_sha256": sha256(registry),
            "legal_markdown_files": legal_doc_hashes,
        },
        "train_test_isolation": {
            "source_train_csv_sha256": train_manifest["source"]["train_csv_sha256"],
            "source_test_csv_sha256": train_manifest["source"]["test_csv_sha256"],
            "train_test_contract_overlap": train_manifest["counts"]["train_test_contract_overlap"],
            "indexed_train_rows": train_manifest["counts"]["indexed_points"],
            "test_rows_indexed": 0,
        },
        "problems": problems,
    }
    out = ROOT / "data" / "risk" / "results" / "local_hashing_index_manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "output": str(out.relative_to(ROOT)), "collections": collections, "problems": problems}, indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
