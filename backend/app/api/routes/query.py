"""
v1 only supports clause classification (see documents.py). This endpoint
is stubbed out now so the route/file exists in the project structure, but
intentionally returns 501 until the v2 QA pipeline (per-document chunking +
retrieval + generation) is built.

Location: app/api/routes/query.py
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/query", tags=["query"])


class QueryRequest(BaseModel):
    question: str


@router.post("")
def query_contract(request: QueryRequest) -> dict:
    raise HTTPException(
        status_code=501,
        detail=(
            "Free-text contract Q&A is not implemented yet (planned for v2). "
            "v1 supports clause classification via POST /documents/classify."
        ),
    )