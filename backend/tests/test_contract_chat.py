import hashlib
import json
from pathlib import Path

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

def test_contract_chat_retrieval_expands_legal_synonyms_and_prioritizes_risk_findings():
    clauses = [
        {"clause_index": 1, "predicted_label": "Payment Terms", "clause_text": "Invoices are payable within thirty days."},
        {"clause_index": 2, "predicted_label": "Cap On Liability", "clause_text": "Supplier's aggregate liability shall not exceed fees paid in the previous one month."},
        {"clause_index": 3, "predicted_label": "Termination", "clause_text": "Supplier may terminate immediately for any breach.", "risk_findings": [
            {"risk_status": "POTENTIAL_RISK", "risk_type": "Unequal termination rights", "why_flagged": "Immediate termination is one-sided."}
        ]},
    ]
    selected = query._select_clauses(clauses, "What exposure does the supplier liability cap create?")
    assert selected[0]["clause_index"] == 2

    selected = query._select_clauses(clauses, "What are the main risks?")
    assert selected[0]["clause_index"] == 3


def test_contract_chat_fails_closed_when_contract_question_has_no_verified_citation(monkeypatch, tmp_path):
    analysis_id = "0123456789abcdef-0123456789abcdef"
    run_root = tmp_path / analysis_id
    run_root.mkdir()
    (run_root / "result.json").write_text(json.dumps({
        "analysis_id": analysis_id,
        "clauses": [{"clause_index": 1, "clause_text": "Supplier may terminate with notice.", "predicted_label": "Termination"}],
        "contract_risk_assessment": {},
    }), encoding="utf-8")
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(query, "_call_local_chat", lambda *args, **kwargs: json.dumps({
        "answer": "The customer has a 30-day termination right.",
        "insufficient_evidence": False,
        "citations": [],
        "follow_up_questions": [],
    }))
    response = TestClient(app).post("/query/contract", json={
        "analysis_id": analysis_id,
        "question": "What termination rights does the customer have?",
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["insufficient_evidence"] is True
    assert data["citations"] == []
    assert "couldn't verify a supporting quote" in data["answer"]


def test_contract_chat_returns_verified_extractive_fallback_when_local_model_is_unavailable(monkeypatch, tmp_path):
    analysis_id = "0123456789abcdef-0123456789abcdef"
    run_root = tmp_path / analysis_id
    run_root.mkdir()
    source = "Supplier may terminate this Agreement immediately for any breach after written notice."
    (run_root / "result.json").write_text(json.dumps({
        "analysis_id": analysis_id,
        "filename": "fallback.txt",
        "clauses": [{"clause_index": 5, "heading": "Termination", "predicted_label": "Termination", "clause_text": source}],
        "contract_risk_assessment": {},
    }), encoding="utf-8")
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)
    def unavailable(*args, **kwargs):
        raise RuntimeError("Ollama offline")
    monkeypatch.setattr(query, "_call_local_chat", unavailable)
    response = TestClient(app).post("/query/contract", json={
        "analysis_id": analysis_id,
        "question": "What termination rights are stated?",
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["model"] == "EXTRACTIVE_FALLBACK"
    assert data["insufficient_evidence"] is True
    assert data["citations"][0]["clause_index"] == 5
    assert data["citations"][0]["quote"] in source
    assert "have not generated an interpretation" in data["answer"]


def test_demo_analysis_generates_reproducible_walkthrough_without_prior_upload(monkeypatch, tmp_path):
    original_fixture = Path(query.PROJECT_ROOT) / "data" / "risk" / "demo_contract_for_reproduction.txt"
    fixture_path = tmp_path / "data" / "risk" / "demo_contract_for_reproduction.txt"
    fixture_path.parent.mkdir(parents=True)
    fixture_path.write_bytes(original_fixture.read_bytes())
    runs_root = tmp_path / "runs"
    monkeypatch.setattr(query, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(query, "RUNS_DIR", runs_root)

    response = TestClient(app).get("/query/demo-analysis")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["demo_mode"] is True
    assert data["total_clauses"] == 11
    assert data["analysis_id"]
    assert "illustrative" in data["notice"].lower()
    assert data["contract_metadata"]["document_hash"] == hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    assert len([finding for clause in data["clauses"] for finding in clause["risk_findings"]]) >= 8
    saved = runs_root / data["analysis_id"] / "result.json"
    assert saved.is_file()
    stored = json.loads(saved.read_text(encoding="utf-8"))
    assert stored["demo_mode"] is True
    assert stored["analysis_id"] == data["analysis_id"]
    assert "contract_risk_json" in data["downloads"]
    assert "clauses_csv" in data["downloads"]
    assert "manifest_json" in data["downloads"]


def test_demo_contract_endpoint_downloads_repository_fixture(monkeypatch, tmp_path):
    original_fixture = Path(query.PROJECT_ROOT) / "data" / "risk" / "demo_contract_for_reproduction.txt"
    fixture_path = tmp_path / "data" / "risk" / "demo_contract_for_reproduction.txt"
    fixture_path.parent.mkdir(parents=True)
    fixture_path.write_bytes(original_fixture.read_bytes())
    monkeypatch.setattr(query, "PROJECT_ROOT", tmp_path)
    response = TestClient(app).get("/query/demo-contract")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert response.content == fixture_path.read_bytes()
