import pytest

from app.core import config


def test_missing_openrouter_key_is_safe_until_runtime(monkeypatch):
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", None)
    status = config.openrouter_config_status()
    assert status["api_key_configured"] is False
    assert status["model"] == "nvidia/nemotron-3-ultra-550b-a55b:free"
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY is not configured"):
        config.validate_openrouter_configuration()
