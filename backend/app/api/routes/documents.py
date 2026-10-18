"""Document upload, streaming, resumable run status, and artifact download APIs."""
from __future__ import annotations

import asyncio
import csv
import io
import json
import queue
import zipfile
import shutil
import tempfile
import re
from pathlib import Path
from threading import Thread

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse

from ...core.config import RUNS_DIR
from ...models.schemas import ContractClassificationResponse
from ...services.rag_service import classify_contract, _is_contract_header_metadata
from ...core.risk.contract_metadata import extract_contract_metadata

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
}
_ANALYSIS_ID = re.compile(r"^[0-9a-f]{16}-[0-9a-f]{16}$")


def _run_root(analysis_id: str) -> Path:
    if not _ANALYSIS_ID.fullmatch(analysis_id):
        raise HTTPException(status_code=400, detail="Invalid analysis ID.")
    runs_root = Path(RUNS_DIR).resolve()
    root = (runs_root / analysis_id).resolve()
    if runs_root not in root.parents:
        raise HTTPException(status_code=400, detail="Invalid analysis ID.")
    return root


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


def _available_downloads(analysis_id: str | None) -> dict[str, str]:
    if not analysis_id:
        return {}
    root = _run_root(analysis_id)
    names = ("result.json", "contract_risk.json", "risk_findings.jsonl", "risk_findings.csv", "clauses.csv", "classification.jsonl", "manifest.json")
    downloads = {
        name.replace(".", "_"): f"/documents/runs/{analysis_id}/artifact/{name}"
        for name in names if (root / name).is_file()
    }
    if root.is_dir() and any(root.glob("source.*")):
        downloads["contract_bundle_zip"] = f"/documents/runs/{analysis_id}/bundle.zip"
    return downloads


def _normalize_saved_result(analysis_id: str, result: dict, root: Path, manifest: dict | None = None) -> dict:
    """Normalize older run records for display without mutating their raw artifacts."""
    segments = []
    segment_path = root / "segments.json"
    if segment_path.is_file():
        try:
            loaded = json.loads(segment_path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                segments = loaded
        except (OSError, json.JSONDecodeError):
            segments = []
    filename = result.get("filename") or ((manifest or {}).get("source") or {}).get("filename") or "Uploaded contract"
    old_metadata = result.get("contract_metadata") or {}
    metadata = extract_contract_metadata(filename, segments or result.get("clauses", []))
    for key in ("document_hash", "document_version", "contract_type", "jurisdiction_candidates"):
        if old_metadata.get(key) is not None:
            metadata[key] = old_metadata[key]
    result["contract_metadata"] = metadata
    result["clauses"] = [
        clause for clause in result.get("clauses", [])
        if not _is_contract_header_metadata(str(clause.get("clause_text") or ""), int(clause.get("clause_index", -1)))
        and clause.get("classification_status") != "DOCUMENT_METADATA"
    ]
    result["total_clauses"] = len(result["clauses"])
    assessment = result.get("contract_risk_assessment") or {}
    if isinstance(assessment, dict):
        for key in ("clause_findings", "findings"):
            if isinstance(assessment.get(key), list):
                assessment[key] = [
                    finding for finding in assessment[key]
                    if not _is_contract_header_metadata(str(finding.get("clause_text") or ""), int(finding.get("clause_index", -1)))
                ]
    result["contract_risk_assessment"] = assessment
    result["downloads"] = _available_downloads(analysis_id)
    return result


def _response(pipeline: dict) -> ContractClassificationResponse:
    analysis_id = pipeline.get("analysis_id")
    return ContractClassificationResponse(
        filename=pipeline["filename"],
        total_clauses=len(pipeline["clauses"]),
        analysis_id=analysis_id,
        clauses=pipeline["clauses"],
        contract_risk_assessment=pipeline["contract_risk_assessment"],
        contract_metadata=pipeline.get("contract_metadata") or {"source_filename": pipeline["filename"], "name": pipeline["filename"]},
        downloads=_available_downloads(analysis_id),
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
            try:
                event = await asyncio.to_thread(events.get, True, 15)
            except queue.Empty:
                # Keep proxies and browsers from treating a long model call as
                # a dead connection. This does not alter the analysis itself.
                yield "data: " + json.dumps({
                    "type": "heartbeat",
                    "stage": "running",
                    "message": "Analysis is still running",
                }) + "\n\n"
                continue
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
    root = _run_root(analysis_id)
    result_path = root / "result.json"
    manifest_path = root / "manifest.json"
    if not root.exists():
        raise HTTPException(status_code=404, detail="Analysis run not found.")
    result = None
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    status_path = root / "status.json"
    status_record = {}
    if status_path.is_file():
        try:
            status_record = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            status_record = {}
    if isinstance(result, dict):
        result = _normalize_saved_result(analysis_id, result, root, manifest)
    partial_result = None
    if result is None:
        rows_by_index = {}
        classification_path = root / "classification.jsonl"
        if classification_path.is_file():
            for line in classification_path.read_text(encoding="utf-8").splitlines():
                try:
                    row = json.loads(line)
                    index = int(row.get("clause_index"))
                    if not _is_contract_header_metadata(str(row.get("clause_text") or ""), index):
                        rows_by_index[index] = row
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
        segments = []
        segments_path = root / "segments.json"
        if segments_path.is_file():
            try:
                loaded = json.loads(segments_path.read_text(encoding="utf-8"))
                if isinstance(loaded, list): segments = loaded
            except (OSError, json.JSONDecodeError):
                segments = []
        filename = (manifest.get("source") or {}).get("filename") or "Uploaded contract"
        total_clauses = 0
        validated_path = root / "validated.json"
        if validated_path.is_file():
            try:
                validation = json.loads(validated_path.read_text(encoding="utf-8"))
                total_clauses = sum(1 for item in validation if item.get("status") not in {"DOCUMENT_METADATA"} and not _is_contract_header_metadata(str(item.get("clause_text") or ""), int(item.get("clause_index", -1))))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                total_clauses = 0
        if not total_clauses:
            total_clauses = sum(1 for item in segments if not item.get("metadata", {}).get("is_signature_metadata") and not _is_contract_header_metadata(str(item.get("text") or ""), int(item.get("clause_index", -1))))
        if rows_by_index:
            partial_result = {
                "analysis_id": analysis_id,
                "filename": filename,
                "total_clauses": total_clauses,
                "clauses": [rows_by_index[index] for index in sorted(rows_by_index)],
                "contract_risk_assessment": {"status": "ANALYSIS_IN_PROGRESS", "reason": "Partial classification results; risk checks may still be running."},
                "contract_metadata": extract_contract_metadata(filename, segments or list(rows_by_index.values())),
                "downloads": _available_downloads(analysis_id),
                "partial": True,
            }
    current_status = status_record.get("status") or manifest.get("status", "UNKNOWN")
    return {
        "analysis_id": analysis_id,
        "status": current_status,
        "result_available": result is not None,
        "manifest": manifest,
        "result": result,
        "partial_result": partial_result,
        "progress": status_record,
    }


@router.get("/runs/{analysis_id}/bundle.zip")
def download_contract_bundle(analysis_id: str):
    root = _run_root(analysis_id)
    if not root.is_dir():
        raise HTTPException(status_code=404, detail="Analysis run not found.")
    manifest_path = root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        manifest = {}
    sources = sorted(root.glob("source.*"))
    if not sources:
        raise HTTPException(status_code=404, detail="The original uploaded contract is not available for this run.")
    source = sources[0]
    source_name = Path((manifest.get("source") or {}).get("filename") or source.name).name
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(source, f"uploaded_contract/{source_name}")
        for item in sorted(root.rglob("*")):
            if not item.is_file() or item == source or item.name == "bundle.zip" or any(part.startswith(".") for part in item.relative_to(root).parts):
                continue
            archive.write(item, f"analysis_artifacts/{item.relative_to(root).as_posix()}")
        payload = get_run(analysis_id).get("result")
        if isinstance(payload, dict):
            archive.writestr("review_view/result.json", json.dumps(payload, ensure_ascii=False, indent=2))
            archive.writestr("review_view/contract_metadata.json", json.dumps(payload.get("contract_metadata") or {}, ensure_ascii=False, indent=2))
            clauses = payload.get("clauses") or []
            clause_buffer = io.StringIO(newline="")
            clause_fields = ["clause_index", "heading", "section_path", "clause_text", "predicted_label", "classification_status", "classification_confidence", "risk_status"]
            clause_writer = csv.DictWriter(clause_buffer, fieldnames=clause_fields, extrasaction="ignore")
            clause_writer.writeheader(); clause_writer.writerows(clauses)
            archive.writestr("review_view/clauses.csv", clause_buffer.getvalue())
            risk_path = root / "risk_findings.csv"
            if risk_path.is_file():
                with risk_path.open("r", newline="", encoding="utf-8-sig") as handle:
                    risk_rows = list(csv.DictReader(handle))
                risk_rows = [row for row in risk_rows if row.get("clause_index") != "0"]
                if risk_rows:
                    risk_buffer = io.StringIO(newline="")
                    risk_writer = csv.DictWriter(risk_buffer, fieldnames=list(risk_rows[0].keys()), extrasaction="ignore")
                    risk_writer.writeheader(); risk_writer.writerows(risk_rows)
                    archive.writestr("review_view/risk_findings.csv", risk_buffer.getvalue())
        archive.writestr("README.txt", "Contract Review Package\n\n"
            f"Analysis ID: {analysis_id}\nOriginal file: {source_name}\n\n"
            "uploaded_contract/ contains the original uploaded contract.\n"
            "analysis_artifacts/ contains the raw persisted run outputs, trace, manifest, and checkpoints.\n"
            "review_view/ contains the normalized result and user-facing clause, risk, and metadata tables.\n\n"
            "Classification scores are internal diagnostics, not calibrated probabilities. Risk findings are review triggers, not legal advice.\n")
    return Response(content=buffer.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="contract-review-{analysis_id}.zip"'})


@router.get("/runs/{analysis_id}/artifact/{artifact}")
def download_artifact(analysis_id: str, artifact: str):
    if artifact not in SAFE_ARTIFACTS or Path(artifact).name != artifact:
        raise HTTPException(status_code=400, detail="Artifact is not allowed.")
    root = _run_root(analysis_id)
    candidate = (root / artifact).resolve()
    if root not in candidate.parents and candidate != root:
        raise HTTPException(status_code=400, detail="Invalid artifact path.")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return FileResponse(candidate, filename=artifact)
