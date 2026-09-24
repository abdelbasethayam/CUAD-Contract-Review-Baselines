import json

from app.core import config
from app.core.rag import generator
from app.core.risk import risk_detector


def test_openrouter_defaults_are_configurable():
    assert config.OPENROUTER_MODEL == "nvidia/nemotron-3-ultra-550b-a55b:free"
    assert config.OPENROUTER_BASE_URL.endswith("/api/v1")
    assert config.CONTRACT_CONTEXT_TOP_K == 5


def test_ollama_response_parsing_returns_generation_text(monkeypatch):
    monkeypatch.setattr(generator, "OLLAMA_MAX_RETRY_ATTEMPTS", 1)

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"response": '{"clause_type":"Insurance"}'}

    seen = {}

    def fake_post(*args, **kwargs):
        seen["url"] = args[0]
        seen["json"] = kwargs["json"]
        seen["timeout"] = kwargs["timeout"]
        return FakeResponse()

    monkeypatch.setattr(generator.requests, "post", fake_post)
    assert generator.call_ollama("classify") == '{"clause_type":"Insurance"}'
    assert seen["url"].endswith("/api/generate")
    assert seen["json"]["model"] == generator.OLLAMA_MODEL
    assert seen["timeout"] == generator.OLLAMA_TIMEOUT_SECONDS


def test_ollama_retries_provider_failure_with_exponential_backoff(monkeypatch):
    monkeypatch.setattr(generator, "OLLAMA_MAX_RETRY_ATTEMPTS", 2)
    monkeypatch.setattr(generator.time, "sleep", lambda _: None)
    calls = []

    class FakeResponse:
        def __init__(self, status_code):
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError("provider failure")

        def json(self):
            return {"response": "{}"}

    def fake_post(*args, **kwargs):
        calls.append(kwargs)
        return FakeResponse(429 if len(calls) == 1 else 200)

    monkeypatch.setattr(generator.requests, "post", fake_post)
    assert generator.call_ollama("retry") == "{}"
    assert len(calls) == 2


def test_candidate_constrained_classification_rejects_forbidden_abstention():
    labels = ["Insurance", "Termination"]
    assert generator.parse_prediction_result(
        '{"clause_type":"Insurance"}', labels, ["Insurance"]
    )["status"] == "VALID_CANDIDATE"
    assert generator.parse_prediction_result(
        '{"clause_type":"Termination"}', labels, ["Insurance"]
    )["status"] == "OUT_OF_CANDIDATE"
    rejected = generator.parse_prediction_result(
        '{"clause_type":"UNKNOWN"}', labels, ["Insurance"]
    )
    assert rejected["status"] == "FORBIDDEN_ABSTENTION"
    assert rejected["prediction"] is None


def test_malformed_risk_json_is_safe_error():
    result = risk_detector.parse_risk_response("not-json", {})
    assert result["risk"] is False
    assert result["risk_status"] == "ERROR"


def test_risk_requires_exact_contract_evidence(monkeypatch):
    monkeypatch.setattr(risk_detector, "retrieve_legal_guidance", lambda *a, **k: [])
    monkeypatch.setattr(
        risk_detector,
        "call_ollama",
        lambda prompt: json.dumps(
            {
                "risk_status": "POTENTIAL_RISK",
                "risk_type": "Uncapped Liability",
                "risk_level": "HIGH",
                "reason": "The clause creates uncapped exposure.",
                "evidence": "Liability is unlimited.",
            }
        ),
    )
    result = risk_detector.detect_clause_risk(
        "Liability is unlimited.",
        "Uncapped Liability",
    )
    assert result["risk_status"] == "POTENTIAL_RISK"
    assert result["evidence"] == "Liability is unlimited."
    assert result["risk_level"] == "HIGH"


def test_risk_without_valid_evidence_becomes_insufficient(monkeypatch):
    monkeypatch.setattr(risk_detector, "retrieve_legal_guidance", lambda *a, **k: [])
    monkeypatch.setattr(
        risk_detector,
        "call_ollama",
        lambda prompt: '{"risk_status":"POTENTIAL_RISK","risk_type":"Issue","evidence":"generated paraphrase","reason":"Review"}',
    )
    result = risk_detector.detect_clause_risk("The clause is ordinary.", "Insurance")
    assert result["risk"] is False
    assert result["risk_status"] == "INSUFFICIENT_EVIDENCE"
    assert result["risk_level"] is None


def test_related_contract_context_is_passed_to_risk_prompt(monkeypatch):
    monkeypatch.setattr(risk_detector, "retrieve_legal_guidance", lambda *a, **k: [])
    seen = {}

    def fake_call(prompt):
        seen["prompt"] = prompt
        return '{"risk_status":"NO_RISK","risk_type":null,"risk_level":null,"reason":"No issue.","evidence":""}'

    monkeypatch.setattr(risk_detector, "call_ollama", fake_call)
    result = risk_detector.detect_clause_risk(
        "The supplier shall maintain insurance.",
        "Insurance",
        contract_context=[
            {
                "chunk_id": "contract-clause-2",
                "similarity_score": 0.88,
                "clause_text": "The supplier shall indemnify the customer.",
            }
        ],
    )
    assert result["risk_status"] == "NO_RISK"
    assert "contract-clause-2" in seen["prompt"]
