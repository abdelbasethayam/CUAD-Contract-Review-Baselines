"""
POST /documents/classify

Accepts an uploaded contract (PDF or .txt), runs it through the RAG
classification pipeline (services.rag_service.classify_contract), and
returns a labeled breakdown of every clause found.

Location: app/api/routes/documents.py
"""

from __future__ import annotations

import asyncio
import json
import queue
import shutil
import tempfile
from threading import Thread
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ...models.schemas import ClauseResult, ContractClassificationResponse
from ...services.rag_service import classify_contract

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_SUFFIXES = {".pdf", ".txt"}


def _save_upload(file: UploadFile) -> tuple[Path, str]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Upload a .pdf or .txt file.",
        )

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
    return Path(tmp.name), suffix


@router.post("/classify", response_model=ContractClassificationResponse)
async def classify_document(
    file: UploadFile = File(...),
) -> ContractClassificationResponse:
    # Stream the upload to a temp file on disk -- classify_contract()
    # expects a Path, and contracts can be too large to hold comfortably
    # in memory.
    tmp_path, _ = _save_upload(file)

    try:
        pipeline = classify_contract(tmp_path)
    except ValueError as exc:
        # No clauses detected, empty file, etc. -- a client-fixable error.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        # Model provider down, Cohere/Qdrant unreachable, etc. -- a server-side
        # dependency failure, not the client's fault.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    return ContractClassificationResponse(
        filename=file.filename or tmp_path.name,
        total_clauses=len(pipeline["clauses"]),
        clauses=[ClauseResult(**r) for r in pipeline["clauses"]],
        contract_risk_assessment=pipeline["contract_risk_assessment"],
    )


@router.post("/classify/stream", include_in_schema=True)
async def classify_document_stream(file: UploadFile = File(...)):
    """Classify a document while streaming pipeline progress as SSE events."""
    tmp_path, _ = _save_upload(file)
    filename = file.filename or tmp_path.name
    events: queue.Queue[dict | None] = queue.Queue()

    def publish(event: dict) -> None:
        events.put(event)

    def worker() -> None:
        try:
            pipeline = classify_contract(tmp_path, progress_callback=publish)
            response = ContractClassificationResponse(
                filename=filename,
                total_clauses=len(pipeline["clauses"]),
                clauses=[ClauseResult(**r) for r in pipeline["clauses"]],
                contract_risk_assessment=pipeline["contract_risk_assessment"],
            )
            payload = response.model_dump() if hasattr(response, "model_dump") else response.dict()
            events.put({"type": "result", "data": payload})
        except ValueError as exc:
            events.put({"type": "error", "status": 422, "message": str(exc)})
        except RuntimeError as exc:
            events.put({"type": "error", "status": 503, "message": str(exc)})
        except Exception as exc:
            events.put({"type": "error", "status": 500, "message": f"Classification failed: {exc}"})
        finally:
            tmp_path.unlink(missing_ok=True)
            events.put(None)

    Thread(target=worker, daemon=True).start()

    async def stream():
        yield "data: " + json.dumps({
            "type": "progress",
            "stage": "upload",
            "message": "Upload received; starting analysis",
        }) + "\n\n"
        while True:
            event = await asyncio.to_thread(events.get)
            if event is None:
                break
            yield "data: " + json.dumps(event) + "\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
