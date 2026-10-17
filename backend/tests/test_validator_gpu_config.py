from types import SimpleNamespace

from app.core.rag import validator


def test_clause_validator_respects_configured_ollama_gpu_server(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": '{"is_clause": true}'}

    def fake_post(url, json, timeout):
        captured.update({"url": url, "payload": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr(validator.requests, "post", fake_post)
    monkeypatch.setattr(validator, "OLLAMA_URL", "http://127.0.0.1:11434")
    monkeypatch.setattr(validator, "OLLAMA_MODEL", "qwen3:8b")
    monkeypatch.setattr(validator, "OLLAMA_TIMEOUT_SECONDS", 12)
    monkeypatch.setattr(validator, "OLLAMA_MAX_RETRY_ATTEMPTS", 1)

    assert validator.is_real_clause("Supplier shall maintain insurance.")

    options = captured["payload"]["options"]
    assert captured["url"] == "http://127.0.0.1:11434/api/generate"
    assert captured["payload"]["model"] == "qwen3:8b"
    assert captured["payload"]["think"] is False
    assert captured["payload"]["format"] == "json"
    assert options["num_ctx"] == 512
    assert "num_gpu" not in options
    assert captured["timeout"] == 12
