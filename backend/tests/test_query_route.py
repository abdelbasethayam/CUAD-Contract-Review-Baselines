import json

import pytest
from starlette.requests import Request

from app.api.routes import query


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/query", "headers": [], "client": ("127.0.0.1", 1234)})


def test_query_requires_analysis_id():
    with pytest.raises(Exception):
        query.QueryRequest(question="What is the cap?")


def test_query_rejects_path_traversal(monkeypatch, tmp_path):
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)
    with pytest.raises(query.HTTPException) as exc:
        query._load_analysis("../secret")
    assert exc.value.status_code == 400


def test_query_requires_completed_manifest(monkeypatch, tmp_path):
    run_dir = tmp_path / "abc123"
    run_dir.mkdir()
    (run_dir / "result.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)
    with pytest.raises(query.HTTPException) as exc:
        query._load_analysis("abc123")
    assert exc.value.status_code == 409


def test_query_sends_bounded_grounded_context_and_validates_citation(monkeypatch, tmp_path):
    analysis_id = "abc123"
    run_dir = tmp_path / analysis_id
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(json.dumps({"status": "COMPLETED", "environment": {"git_commit": "abc"}}), encoding="utf-8")
    (run_dir / "result.json").write_text(
        json.dumps({
            "filename": "contract.txt",
            "contract_metadata": {"parties": ["Buyer", "Seller"]},
            "contract_risk_assessment": {"playbook_hash": "hash"},
            "clauses": [{
                "clause_index": 1,
                "predicted_label": "Limitation of Liability",
                "clause_text": "Liability is capped at $100.",
                "risk_findings": [],
            }],
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(query.config, "OPENROUTER_API_KEY", "test-key")
    seen = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "[Clause 1] Liability is capped at $100."}}]}

    def fake_post(url, **kwargs):
        seen["url"] = url
        seen["payload"] = kwargs["json"]
        return Response()

    monkeypatch.setattr(query.requests, "post", fake_post)
    response = query.query_contract(query.QueryRequest(
        analysis_id=analysis_id,
        question="What is the cap?",
    ), _request())
    assert response.grounded is True
    assert response.citations == [{"clause_id": 1, "quote": "Liability is capped at $100."}]
    assert "Liability is capped at $100." in seen["payload"]["messages"][1]["content"]
    assert seen["payload"]["messages"][-1] == {"role": "user", "content": "What is the cap?"}


def test_query_refuses_legal_advice_without_calling_provider(monkeypatch, tmp_path):
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(query.requests, "post", lambda *args, **kwargs: pytest.fail("provider should not be called"))
    response = query.query_contract(query.QueryRequest(
        analysis_id="abc123",
        question="Should I sign this contract?",
    ), _request())
    assert "legal advice" in response.answer
    assert response.model == "safety-policy"
