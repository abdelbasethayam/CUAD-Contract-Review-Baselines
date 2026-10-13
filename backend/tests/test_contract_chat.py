import hashlib
import json

from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import query


def test_contract_chat_validates_analysis_id_and_question():
    client = TestClient(app)
    response = client.post("/query/contract", json={
        "analysis_id": "../etc/passwd",
        "question": "What does this say?",
    })
    assert response.status_code == 400

    response = client.post("/query/contract", json={
        "analysis_id": "0123456789abcdef-0123456789abcdef",
        "question": "",
    })
    assert response.status_code == 422


def test_contract_chat_verifies_exact_quote_before_returning_citation(monkeypatch, tmp_path):
    analysis_id = "0123456789abcdef-0123456789abcdef"
    run_root = tmp_path / analysis_id
    run_root.mkdir()
    clause_text = "Either party may terminate this Agreement upon thirty days written notice."
    stored = {
        "analysis_id": analysis_id,
        "filename": "demo.txt",
        "contract_metadata": {"name": "Demo"},
        "clauses": [{
            "clause_index": 1,
            "clause_text": clause_text,
            "predicted_label": "Termination For Convenience",
            "risk_status": "POTENTIAL_RISK",
            "risk_findings": [],
        }],
        "contract_risk_assessment": {"status": "POTENTIAL_RISK"},
    }
    (run_root / "result.json").write_text(json.dumps(stored), encoding="utf-8")
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(
        query,
        "_call_local_chat",
        lambda *args, **kwargs: json.dumps({
            "answer": "Either party can terminate on thirty days written notice.",
            "insufficient_evidence": False,
            "citations": [{
                "clause_index": 1,
                "quote": clause_text,
                "reason": "This is the termination provision.",
            }],
            "follow_up_questions": ["Are there termination fees?"],
        }),
    )

    response = TestClient(app).post("/query/contract", json={
        "analysis_id": analysis_id,
        "question": "How can a party terminate this agreement?",
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["citations"][0]["clause_index"] == 1
    assert data["citations"][0]["quote"] == clause_text
    assert data["insufficient_evidence"] is False
    assert data["follow_up_questions"] == ["Are there termination fees?"]


def test_contract_chat_rejects_unverifiable_quote(monkeypatch, tmp_path):
    analysis_id = "0123456789abcdef-0123456789abcdef"
    run_root = tmp_path / analysis_id
    run_root.mkdir()
    (run_root / "result.json").write_text(json.dumps({
        "analysis_id": analysis_id,
        "clauses": [{
            "clause_index": 4,
            "clause_text": "A long clause with actual source evidence.",
        }],
        "contract_risk_assessment": {},
    }), encoding="utf-8")
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(query, "_call_local_chat", lambda *args, **kwargs: json.dumps({
        "answer": "This contract has unlimited liability.",
        "insufficient_evidence": False,
        "citations": [{
            "clause_index": 4,
            "quote": "This fabricated text does not appear in the source.",
            "reason": "fake",
        }],
        "follow_up_questions": [],
    }))

    response = TestClient(app).post("/query/contract", json={
        "analysis_id": analysis_id,
        "question": "What liability does this contract define?",
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["insufficient_evidence"] is True
    assert data["citations"] == []
    assert "couldn't verify" in data["answer"]


def test_metrics_endpoint_never_returns_annotation_queue_metrics(monkeypatch, tmp_path):
    monkeypatch.setattr(query, "PROJECT_ROOT", tmp_path)
    response = TestClient(app).get("/query/phase2-metrics")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["evaluation_mode"] == "PLAYBOOK_RULE_CONFORMANCE"
    assert data["rule_validation"]["status"] == "NOT_RUN"
    assert data["classification_index_isolation"]["status"] == "NOT_RUN"
    assert "gold" not in json.dumps(data).lower()
    assert "silver" not in json.dumps(data).lower()
    assert "legal-risk accuracy" in data["warning"]


def test_demo_endpoint_only_returns_hash_matched_repository_fixture(monkeypatch, tmp_path):
    analysis_id = "0123456789abcdef-0123456789abcdef"
    runs_root = tmp_path / "runs"
    fixture_path = tmp_path / "data" / "risk" / "demo_contract_for_reproduction.txt"
    fixture_path.parent.mkdir(parents=True)
    fixture_bytes = b"Synthetic demo contract fixture, not a user-uploaded contract."
    fixture_path.write_bytes(fixture_bytes)
    fixture_hash = hashlib.sha256(fixture_bytes).hexdigest()

    matching_run = runs_root / analysis_id
    matching_run.mkdir(parents=True)
    valid = {
        "analysis_id": analysis_id,
        "filename": "demo_contract_for_reproduction.txt",
        "contract_metadata": {"document_hash": fixture_hash, "name": "Synthetic demo"},
        "clauses": [{"clause_index": index, "clause_text": "Sample clause text."} for index in range(8)],
        "contract_risk_assessment": {},
    }
    (matching_run / "result.json").write_text(json.dumps(valid), encoding="utf-8")

    private_run = runs_root / "fedcba9876543210-fedcba9876543210"
    private_run.mkdir(parents=True)
    private_data = {
        **valid,
        "analysis_id": private_run.name,
        "contract_metadata": {"document_hash": "different-document-hash"},
    }
    (private_run / "result.json").write_text(json.dumps(private_data), encoding="utf-8")

    monkeypatch.setattr(query, "RUNS_DIR", runs_root)
    monkeypatch.setattr(query, "PROJECT_ROOT", tmp_path)
    response = TestClient(app).get("/query/demo-analysis")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["demo_mode"] is True
    assert data["filename"] == fixture_path.name
    assert data["analysis_id"] == analysis_id
    assert data["total_clauses"] == 8
