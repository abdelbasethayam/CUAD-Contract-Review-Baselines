#!/usr/bin/env python3
"""Validate dataset isolation for clause classification only.

This validator deliberately does not read risk-span, silver-risk, or gold-risk
annotation queues. Custom risk flags are playbook rules/questions applied to the
uploaded contract, not a supervised text-span task.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from qdrant_client import QdrantClient
from app.core.config import HYBRID_COLLECTION, QDRANT_COLLECTION, QDRANT_PATH


def read_documents(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def scroll_document_ids(client: QdrantClient, name: str) -> tuple[set[str], int, list[str]]:
    document_ids: set[str] = set()
    point_count = 0
    missing_payload_ids: list[str] = []
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=name,
            limit=512,
            offset=offset,
            with_payload=["document_id"],
            with_vectors=False,
        )
        point_count += len(points)
        for point in points:
            document_id = str((point.payload or {}).get("document_id") or "").strip()
            if not document_id:
                missing_payload_ids.append(str(point.id))
            else:
                document_ids.add(document_id)
        if offset is None:
            break
    return document_ids, point_count, missing_payload_ids


def main() -> int:
    train_path = ROOT / "data" / "splits" / "train" / "master_clauses_train.csv"
    test_path = ROOT / "data" / "splits" / "test" / "master_clauses_test.csv"
    train_rows = read_documents(train_path)
    test_rows = read_documents(test_path)
    train_docs = {str(row.get("document_id") or "").strip() for row in train_rows}
    test_docs = {str(row.get("document_id") or "").strip() for row in test_rows}
    train_docs.discard("")
    test_docs.discard("")
    checks: list[dict] = []

    def check(name: str, passed: bool, detail) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    check("train_test_contract_overlap", not (train_docs & test_docs), len(train_docs & test_docs))
    check("train_and_test_have_contract_ids", bool(train_docs) and bool(test_docs), {
        "train_contracts": len(train_docs), "test_contracts": len(test_docs)
    })
    check("training_split_nonempty", len(train_rows) > 0, len(train_rows))
    check("test_split_nonempty", len(test_rows) > 0, len(test_rows))

    client = QdrantClient(path=str(QDRANT_PATH))
    try:
        existing = {item.name for item in client.get_collections().collections}
        requested = list(dict.fromkeys([
            str(QDRANT_COLLECTION),
            str(HYBRID_COLLECTION),
            "cuad_train_hashing",
            "cuad_train_mpnet",
            "cuad_train",
        ]))
        classifier_collections = [name for name in requested if name in existing]
        check("configured_classifier_collections_exist", QDRANT_COLLECTION in existing and HYBRID_COLLECTION in existing, {
            "configured": [QDRANT_COLLECTION, HYBRID_COLLECTION],
            "found": classifier_collections,
            "available": sorted(existing),
        })

        for name in classifier_collections:
            ids, count, missing = scroll_document_ids(client, name)
            check(f"{name}_payload_train_only", ids <= train_docs, sorted(ids - train_docs)[:30])
            check(f"{name}_payload_no_test_contracts", not (ids & test_docs), sorted(ids & test_docs)[:30])
            check(f"{name}_payload_has_document_ids", not missing, {
                "missing_payload_id_count": len(missing),
                "sample_point_ids": missing[:10],
            })
            check(f"{name}_is_nonempty", count > 0, count)
    finally:
        client.close()

    all_passed = all(item["passed"] for item in checks)
    report = {
        "schema_version": 2,
        "status": "PASS" if all_passed else "FAIL",
        "validation_scope": "CUAD_CLAUSE_CLASSIFICATION_INDEX_ISOLATION_ONLY",
        "risk_annotations_read": False,
        "human_gold_required": False,
        "train_contracts": len(train_docs),
        "test_contracts": len(test_docs),
        "train_clause_rows": len(train_rows),
        "test_clause_rows": len(test_rows),
        "checks_total": len(checks),
        "checks_passed": sum(item["passed"] for item in checks),
        "all_passed": all_passed,
        "checks": checks,
        "interpretation": (
            "Validates the split and payload isolation of the clause-category classification index. "
            "It does not use risk-text-span datasets and does not estimate legal-risk accuracy. "
            "The risk pipeline is evaluated separately by playbook-rule conformance, exact quote "
            "validation, same-contract evidence constraints, synthetic question regression tests and unit tests."
        ),
    }
    out = ROOT / "data" / "risk" / "EVALUATION_INTEGRITY_REPORT.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
