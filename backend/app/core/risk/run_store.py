"""Content-addressed, resumable Phase 2 analysis artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import PROJECT_ROOT, RUNS_DIR, RISK_PLAYBOOK_PATH


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True
        ).strip()
    except Exception:
        return None


def pipeline_fingerprint(config: dict[str, Any]) -> str:
    payload = json.dumps(config, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class AnalysisRun:
    def __init__(self, analysis_id: str, root: Path):
        self.analysis_id = analysis_id
        self.root = root

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    def path(self, name: str) -> Path:
        value = self.root / name
        value.parent.mkdir(parents=True, exist_ok=True)
        return value

    def write_json(self, name: str, payload: Any) -> Path:
        target = self.path(name)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(tmp, target)
        return target

    def append_jsonl(self, name: str, record: dict) -> None:
        target = self.path(name)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def read_json(self, name: str, default: Any = None) -> Any:
        target = self.root / name
        if not target.exists():
            return default
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default

    def read_jsonl_index(self, name: str, key: str) -> dict[str, dict]:
        target = self.root / name
        result: dict[str, dict] = {}
        if not target.exists():
            return result
        for line in target.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                value = record.get(key)
                if value is not None:
                    result[str(value)] = record
            except json.JSONDecodeError:
                continue
        return result


def create_or_resume_run(
    source_path: Path,
    *,
    filename: str,
    config: dict[str, Any],
) -> AnalysisRun:
    source_hash = sha256_file(source_path)
    fingerprint = pipeline_fingerprint(config)
    analysis_id = f"{source_hash[:16]}-{fingerprint}"
    root = Path(RUNS_DIR) / analysis_id
    root.mkdir(parents=True, exist_ok=True)

    manifest = {
        "analysis_id": analysis_id,
        "source": {
            "filename": filename,
            "sha256": source_hash,
        },
        "pipeline": config,
        "pipeline_fingerprint": fingerprint,
        "playbook_path": str(RISK_PLAYBOOK_PATH),
        "created_or_resumed_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "git_commit": git_commit(),
        },
        "status": "RUNNING",
    }

    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        try:
            old = json.loads(manifest_path.read_text(encoding="utf-8"))
            if old.get("source", {}).get("sha256") != source_hash:
                raise RuntimeError("Run directory collision with a different source file.")
            # Preserve first-run provenance and update resume timestamp.
            manifest = {**old, "last_resumed_at": manifest["created_or_resumed_at"], "status": "RUNNING"}
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Cannot resume corrupted analysis manifest: {exc}") from exc
    else:
        source_copy = root / "source"
        source_copy.parent.mkdir(parents=True, exist_ok=True)
        source_copy.write_bytes(source_path.read_bytes())

    tmp = manifest_path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(tmp, manifest_path)
    return AnalysisRun(analysis_id, root)


def mark_run_complete(run: AnalysisRun, **details: Any) -> None:
    manifest = run.read_json("manifest.json", {}) or {}
    manifest.update(
        {
            "status": "COMPLETED",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            **details,
        }
    )
    run.write_json("manifest.json", manifest)


def mark_run_failed(run: AnalysisRun, error: str) -> None:
    manifest = run.read_json("manifest.json", {}) or {}
    manifest.update(
        {
            "status": "FAILED",
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "error": str(error),
        }
    )
    run.write_json("manifest.json", manifest)
