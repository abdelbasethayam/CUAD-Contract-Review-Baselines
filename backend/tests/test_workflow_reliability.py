import json

import pytest

from app.api.routes import documents
from app.services.rag_service import _trace_callback


def test_run_root_rejects_path_traversal():
    with pytest.raises(documents.HTTPException) as exc:
        documents._run_root("../secret")
    assert exc.value.status_code == 400


def test_trace_records_sequence_and_elapsed(tmp_path):
    class Run:
        analysis_id = "abc"
        def __init__(self):
            self.events = []
            self.status = []
        def append_jsonl(self, name, event):
            self.events.append((name, event))
        def write_json(self, name, payload):
            self.status.append((name, payload))

    run = Run()
    received = []
    trace = _trace_callback(run, received.append)
    trace({"type": "progress", "stage": "extract", "message": "Started"})
    trace({"type": "progress", "stage": "complete", "message": "Done"})
    assert [event[1]["sequence"] for event in run.events] == [1, 2]
    assert all("elapsed_seconds" in event[1] for event in run.events)
    assert received[-1]["stage"] == "complete"
    assert run.status[-1][1]["status"] == "COMPLETED"


def test_completed_run_normalizes_clause_count_and_extracts_header_parties(tmp_path, monkeypatch):
    analysis_id = "fedcba9876543210-fedcba9876543210"
    root = tmp_path / analysis_id
    root.mkdir()
    party_block = (
        "Road Transportation Agreement Party A (Shipper): ZTO Express Co., Ltd. "
        "Address: A. Party B (Carrier): Tonglu Tongze Logistics Ltd. Address: B."
    )
    segments = [
        {"clause_index": 0, "text": party_block, "metadata": {}},
        {"clause_index": 1, "text": "1. The carrier shall provide transport services.", "metadata": {}},
        {"clause_index": 2, "text": "2. The parties agree on payment terms.", "metadata": {}},
    ]
    (root / "manifest.json").write_text(json.dumps({"status": "COMPLETED", "source": {"filename": "transport.pdf"}}), encoding="utf-8")
    (root / "segments.json").write_text(json.dumps(segments), encoding="utf-8")
    (root / "source.pdf").write_bytes(b"%PDF-test")
    (root / "result.json").write_text(json.dumps({
        "analysis_id": analysis_id,
        "filename": "transport.pdf",
        "total_clauses": 3,
        "clauses": [
            {"clause_index": 0, "clause_text": party_block, "predicted_label": "NO_APPLICABLE_LABEL"},
            {"clause_index": 1, "clause_text": segments[1]["text"], "predicted_label": "Insurance"},
            {"clause_index": 2, "clause_text": segments[2]["text"], "predicted_label": "Payment Terms"},
        ],
        "contract_metadata": {},
        "contract_risk_assessment": {},
    }), encoding="utf-8")
    monkeypatch.setattr(documents, "RUNS_DIR", tmp_path)

    payload = documents.get_run(analysis_id)
    result = payload["result"]
    assert result["total_clauses"] == 2
    assert [row["clause_index"] for row in result["clauses"]] == [1, 2]
    assert result["contract_metadata"]["parties"] == ["ZTO Express Co., Ltd", "Tonglu Tongze Logistics Ltd"]
    assert result["downloads"]["contract_bundle_zip"].endswith("/bundle.zip")


def test_run_status_exposes_saved_partial_classifications(tmp_path, monkeypatch):
    analysis_id = "0123456789abcdef-fedcba9876543210"
    root = tmp_path / analysis_id
    root.mkdir()
    party_block = "Agreement Party A: Company A Address: A Party B: Company B Address: B"
    segments = [
        {"clause_index": 0, "text": party_block, "metadata": {}},
        {"clause_index": 1, "text": "1. Supplier shall deliver the services.", "metadata": {}},
    ]
    (root / "manifest.json").write_text(json.dumps({"status": "RUNNING", "source": {"filename": "contract.txt"}}), encoding="utf-8")
    (root / "status.json").write_text(json.dumps({"status": "RUNNING", "last_message": "Classifying clause 1"}), encoding="utf-8")
    (root / "segments.json").write_text(json.dumps(segments), encoding="utf-8")
    (root / "validated.json").write_text(json.dumps([
        {"clause_index": 0, "clause_text": party_block, "status": "DOCUMENT_METADATA"},
        {"clause_index": 1, "clause_text": segments[1]["text"], "status": "VALID_CLAUSE"},
    ]), encoding="utf-8")
    (root / "classification.jsonl").write_text(json.dumps({
        "clause_index": 1, "clause_text": segments[1]["text"], "predicted_label": "Services", "classification_status": "CLASSIFIED"
    }) + "\n", encoding="utf-8")
    (root / "source.txt").write_text("contract source", encoding="utf-8")
    monkeypatch.setattr(documents, "RUNS_DIR", tmp_path)

    payload = documents.get_run(analysis_id)
    assert payload["result_available"] is False
    assert payload["partial_result"]["partial"] is True
    assert payload["partial_result"]["total_clauses"] == 1
    assert [row["clause_index"] for row in payload["partial_result"]["clauses"]] == [1]

[executed on device: jupyter-group-digi2026-g6 (a8417900-e68e-4ee2-bbe7-fc3493ade5e1)]
