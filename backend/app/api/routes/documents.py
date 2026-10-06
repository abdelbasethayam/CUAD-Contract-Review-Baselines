"""Document upload, streaming, resumable run status, and artifact download APIs."""
from __future__ import annotations

import asyncio
import json
import queue
import shutil
import tempfile
from pathlib import Path
from threading import Thread

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from ...core.config import RUNS_DIR
from ...models.schemas import ContractClassificationResponse
from ...services.rag_service import classify_contract

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_SUFFIXES = {".pdf", ".txt"}
SAFE_ARTIFACTS = {
    "manifest.json",
    "segments.json",
    "validated.json",
    "embeddings.npy",
    "classification.jsonl",
    "risk_findings.jsonl",
    "contract_checks.json",
    "contract_risk.json",
    "result.json",
    "trace.jsonl",
    "clauses.csv",
    "risk_findings.csv",
    "contract_coverage.json",
    "deterministic_cross_checks.json",
}


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


def _response(pipeline: dict) -> ContractClassificationResponse:
    analysis_id = pipeline.get("analysis_id")
    return ContractClassificationResponse(
        filename=pipeline["filename"],
        total_clauses=len(pipeline["clauses"]),
        analysis_id=analysis_id,
        clauses=pipeline["clauses"],
        contract_risk_assessment=pipeline["contract_risk_assessment"],
        contract_metadata=pipeline.get("contract_metadata") or {"source_filename": pipeline["filename"], "name": pipeline["filename"]},
        downloads={
            name.replace(".", "_"): f"/documents/runs/{analysis_id}/artifact/{name}"
            for name in ("result.json", "contract_risk.json", "risk_findings.jsonl", "risk_findings.csv", "clauses.csv", "contract_coverage.json", "deterministic_cross_checks.json", "classification.jsonl", "manifest.json")
        } if analysis_id else {},
    )


@router.post("/classify", response_model=ContractClassificationResponse)
async def classify_document(file: UploadFile = File(...)):
    tmp_path, _ = _save_upload(file)
    try:
        pipeline = classify_contract(
            tmp_path,
            filename=file.filename or tmp_path.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)
    return _response(pipeline)


@router.post("/classify/stream", include_in_schema=True)
async def classify_document_stream(file: UploadFile = File(...)):
    tmp_path, _ = _save_upload(file)
    filename = file.filename or tmp_path.name
    events: queue.Queue[dict | None] = queue.Queue()

    def publish(event: dict) -> None:
        events.put(event)

    def worker() -> None:
        try:
            pipeline = classify_contract(
                tmp_path,
                progress_callback=publish,
                filename=filename,
            )
            payload = _response(pipeline)
            data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
            events.put({"type": "result", "data": data})
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
            "message": "Upload received; starting resumable analysis",
        }) + "\n\n"
        while True:
            event = await asyncio.to_thread(events.get)
            if event is None:
                break
            yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/runs/{analysis_id}")
def get_run(analysis_id: str):
    root = Path(RUNS_DIR) / analysis_id
    result_path = root / "result.json"
    manifest_path = root / "manifest.json"
    if not root.exists():
        raise HTTPException(status_code=404, detail="Analysis run not found.")
    result = None
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    return {
        "analysis_id": analysis_id,
        "status": manifest.get("status", "UNKNOWN"),
        "result_available": result is not None,
        "manifest": manifest,
        "result": result,
    }


@router.get("/runs/{analysis_id}/artifact/{artifact}")
def download_artifact(analysis_id: str, artifact: str):
    if artifact not in SAFE_ARTIFACTS or Path(artifact).name != artifact:
        raise HTTPException(status_code=400, detail="Artifact is not allowed.")
    root = (Path(RUNS_DIR) / analysis_id).resolve()
    candidate = (root / artifact).resolve()
    if root not in candidate.parents and candidate != root:
        raise HTTPException(status_code=400, detail="Invalid artifact path.")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return FileResponse(candidate, filename=artifact)
