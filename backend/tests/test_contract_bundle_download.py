import io
import json
import zipfile

from app.api.routes import documents


def test_bundle_contains_original_contract_and_all_saved_run_artifacts(tmp_path, monkeypatch):
    analysis_id = "abcdef0123456789-abcdef0123456789"
    root = tmp_path / analysis_id
    root.mkdir()
    (root / "source.pdf").write_bytes(b"%PDF-original-test")
    (root / "manifest.json").write_text(
        json.dumps({"source": {"filename": "original contract.pdf"}, "status": "COMPLETED"}),
        encoding="utf-8",
    )
    (root / "result.json").write_text('{"clauses": []}', encoding="utf-8")
    (root / "risk_findings.csv").write_text("finding_id\n", encoding="utf-8")
    (root / "trace.jsonl").write_text('{"stage":"complete"}\n', encoding="utf-8")
    monkeypatch.setattr(documents, "RUNS_DIR", tmp_path)

    response = documents.download_contract_bundle(analysis_id)

    assert response.status_code == 200
    assert response.media_type == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.body)) as archive:
        names = set(archive.namelist())
        assert "uploaded_contract/original contract.pdf" in names
        assert "analysis_artifacts/result.json" in names
        assert "analysis_artifacts/risk_findings.csv" in names
        assert "analysis_artifacts/trace.jsonl" in names
        assert "README.txt" in names
        assert "review_view/result.json" in names
        assert "review_view/clauses.csv" in names
        assert "review_view/contract_metadata.json" in names
        normalized = json.loads(archive.read("review_view/result.json"))
        assert normalized["total_clauses"] == 0
        assert archive.read("uploaded_contract/original contract.pdf") == b"%PDF-original-test"


def test_available_downloads_includes_package_when_original_contract_exists(tmp_path, monkeypatch):
    analysis_id = "0123456789abcdef-0123456789abcdef"
    root = tmp_path / analysis_id
    root.mkdir()
    (root / "source.txt").write_text("contract", encoding="utf-8")
    monkeypatch.setattr(documents, "RUNS_DIR", tmp_path)

    downloads = documents._available_downloads(analysis_id)

    assert downloads["contract_bundle_zip"] == f"/documents/runs/{analysis_id}/bundle.zip"
