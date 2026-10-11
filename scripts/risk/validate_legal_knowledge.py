#!/usr/bin/env python3
"""Check that legal-knowledge indexing/retrieval works for representative clause families.

Run with the backend stopped when Qdrant is embedded/local, because the local
Qdrant storage lock is single-process.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from backend.app.core.rag.embedder import make_cohere_client
from backend.app.core.rag.retriever import make_qdrant_client
from backend.app.core.legal_knowledge.retriever import retrieve_legal_guidance

CASES = [
    ("Cap On Liability", "Supplier liability is unlimited and indemnification may fall outside the limitation of liability cap."),
    ("Termination For Convenience", "Supplier may terminate immediately; notice, cure and transition should be checked."),
    ("License Grant", "The license is perpetual and transferable, and the software is business critical."),
]

def main() -> int:
    cohere = make_cohere_client()
    qdrant = make_qdrant_client()
    checks = []
    try:
        for clause_type, text in CASES:
            hits = retrieve_legal_guidance(
                text,
                clause_type,
                cohere_client=cohere,
                qdrant_client=qdrant,
                top_k=3,
            )
            checks.append({
                "clause_type": clause_type,
                "match_count": len(hits),
                "sources": [
                    {
                        "source_name": hit.get("source_name"),
                        "title": hit.get("title"),
                        "source_tier": hit.get("source_tier"),
                        "authority_status": hit.get("authority_status"),
                        "dense_score": hit.get("dense_score"),
                        "rrf_score": hit.get("rrf_score"),
                    }
                    for hit in hits
                ],
                "passed": len(hits) > 0 and all(
                    hit.get("source_name") and hit.get("source_tier")
                    for hit in hits
                ),
            })
    finally:
        close = getattr(qdrant, "close", None)
        if callable(close):
            close()
        close = getattr(cohere, "close", None)
        if callable(close):
            close()

    report = {
        "status": "PASS" if all(x["passed"] for x in checks) else "FAIL",
        "case_count": len(checks),
        "checks": checks,
        "note": "Retrieval quality is not legal correctness. Returned sources are contextual guidance; contract findings still require exact contract evidence.",
    }
    out = ROOT / "data" / "risk" / "results" / "legal_knowledge_retrieval_validation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**report, "output": str(out.relative_to(ROOT))}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
