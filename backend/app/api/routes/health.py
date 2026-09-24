"""
GET /health -- basic liveness check for the API.
Location: app/api/routes/health.py
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}