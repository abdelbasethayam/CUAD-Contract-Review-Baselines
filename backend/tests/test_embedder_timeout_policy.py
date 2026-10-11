from types import SimpleNamespace

import pytest

from app.core.rag import embedder


def test_cohere_client_has_finite_timeout_and_no_nested_sdk_retries(monkeypatch):
    monkeypatch.setattr(embedder, "EMBEDDING_BACKEND", "cohere")
    captured = {}

    def fake_client(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(embedder, "COHERE_API_KEY", "test-key")
    monkeypatch.setattr(embedder, "COHERE_TIMEOUT_SECONDS", 12.5)
    monkeypatch.setattr(embedder.cohere, "ClientV2", fake_client)

    embedder.make_cohere_client()

    assert captured["timeout"] == 12.5
    assert captured["max_retries"] == 0


def test_rate_limit_retry_is_bounded_with_capped_backoff(monkeypatch):
    captured = {"calls": 0, "sleeps": []}

    class RateLimited(Exception):
        status_code = 429

    class FakeClient:
        def embed(self, **kwargs):
            captured["calls"] += 1
            if captured["calls"] <= 4:
                raise RateLimited("rate limited")
            return SimpleNamespace(embeddings=SimpleNamespace(float=[[0.1, 0.2]]))

    monkeypatch.setattr(embedder, "COHERE_MAX_RETRY_ATTEMPTS", 8)
    monkeypatch.setattr(embedder, "COHERE_EMBED_BATCH_SIZE", 8)
    monkeypatch.setattr(embedder, "COHERE_MODEL", "test-model")
    monkeypatch.setattr(embedder.time, "sleep", lambda seconds: captured["sleeps"].append(seconds))

    result = embedder.embed_queries(FakeClient(), ["one query"])

    assert result == [[0.1, 0.2]]
    assert captured["calls"] == 5
    assert captured["sleeps"] == [1, 2, 4, 8]


def test_non_rate_limit_embedding_error_fails_fast(monkeypatch):
    captured = {"calls": 0, "sleeps": []}

    class FakeClient:
        def embed(self, **kwargs):
            captured["calls"] += 1
            raise TimeoutError("embedding request timed out")

    monkeypatch.setattr(embedder, "COHERE_MAX_RETRY_ATTEMPTS", 8)
    monkeypatch.setattr(embedder, "COHERE_EMBED_BATCH_SIZE", 8)
    monkeypatch.setattr(embedder.time, "sleep", lambda seconds: captured["sleeps"].append(seconds))

    with pytest.raises(TimeoutError):
        embedder.embed_queries(FakeClient(), ["one query"])

    assert captured["calls"] == 1
    assert captured["sleeps"] == []


def test_local_hashing_backend_is_deterministic_and_correct_dimension(monkeypatch):
    monkeypatch.setattr(embedder, "EMBEDDING_BACKEND", "local_hashing")
    monkeypatch.setattr(embedder, "LOCAL_HASHING_DIM", 256)

    client = embedder.make_cohere_client()
    first = embedder.embed_queries(client, ["liability cap", "termination notice"])
    second = embedder.embed_documents(client, ["liability cap", "termination notice"])

    assert len(first) == 2
    assert len(first[0]) == 256
    assert first == second
    assert first[0] != first[1]
    assert abs(sum(value * value for value in first[0]) - 1.0) < 1e-5


def test_local_hashing_backend_does_not_need_cohere_api_key(monkeypatch):
    monkeypatch.setattr(embedder, "EMBEDDING_BACKEND", "local_hashing")
    monkeypatch.setattr(embedder, "LOCAL_HASHING_DIM", 256)
    monkeypatch.setattr(embedder, "COHERE_API_KEY", None)

    client = embedder.make_cohere_client()
    vectors = embedder.embed_queries(client, ["uncapped liability"])

    assert len(vectors) == 1
    assert len(vectors[0]) == 256
