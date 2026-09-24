from app.core.rag import generator


LABELS = ["Insurance", "Termination", "Indemnification"]
DEFINITIONS = {
    "Insurance": "Insurance coverage and insurance obligations.",
    "Termination": "Termination rights, notice, cure, and ending the agreement.",
    "Indemnification": "Defend, indemnify, and hold harmless obligations.",
}


def _classify(monkeypatch, retrieved, response, *, response_side_effect=None):
    monkeypatch.setattr(generator, "retrieve_similar", lambda *args, **kwargs: retrieved)
    if response_side_effect is not None:
        monkeypatch.setattr(
            generator,
            "call_ollama",
            lambda prompt: response_side_effect.pop(0),
        )
    else:
        monkeypatch.setattr(generator, "call_ollama", lambda prompt: response)
    return generator.classify_clause(
        clause_text="The supplier shall maintain insurance coverage for the customer.",
        query_vector=[0.1, 0.2],
        qdrant_client=object(),
        labels=LABELS,
        label_definitions=DEFINITIONS,
        progress_callback=None,
    )


def test_normal_retrieval_returns_one_candidate_label(monkeypatch):
    result = _classify(
        monkeypatch,
        [
            {"clause_type": "Indemnification", "score": 0.87, "clause_text": "..."},
            {"clause_type": "Insurance", "score": 0.84, "clause_text": "..."},
            {"clause_type": "Insurance", "score": 0.81, "clause_text": "..."},
        ],
        '{"clause_type":"Insurance"}',
    )

    assert result["predicted_label"] == "Insurance"
    assert result["predicted_label"] in result["candidate_labels"]
    assert result["fallback_used"] is False


def test_forbidden_unknown_abstains_without_forcing_a_label(monkeypatch):
    result = _classify(
        monkeypatch,
        [
            {"clause_type": "Indemnification", "score": 0.87, "clause_text": "..."},
            {"clause_type": "Insurance", "score": 0.76, "clause_text": "..."},
        ],
        '{"clause_type":"UNKNOWN"}',
    )

    assert result["predicted_label"] == "NO_APPLICABLE_LABEL"
    assert result["prediction_status"] == "NO_APPLICABLE_LABEL"


def test_invalid_arbitrary_label_is_rejected(monkeypatch):
    result = _classify(
        monkeypatch,
        [{"clause_type": "Insurance", "score": 0.72, "clause_text": "..."}],
        '{"clause_type":"General Contract Provision"}',
    )

    assert result["predicted_label"] == "NO_APPLICABLE_LABEL"
    assert result["prediction_status"] == "NO_APPLICABLE_LABEL"


def test_low_similarity_still_returns_a_valid_label(monkeypatch):
    result = _classify(
        monkeypatch,
        [{"clause_type": "Insurance", "score": 0.03, "clause_text": "..."}],
        '{"clause_type":"not-a-label"}',
    )

    assert result["predicted_label"] == "NO_APPLICABLE_LABEL"
    assert result["classification_confidence"] == 0.03


def test_empty_retrieval_abstains_even_if_model_returns_a_label(monkeypatch):
    retrieval_calls = []

    def fake_retrieve(*args, **kwargs):
        retrieval_calls.append(kwargs.get("top_k"))
        return []

    monkeypatch.setattr(generator, "retrieve_similar", fake_retrieve)
    monkeypatch.setattr(generator, "call_ollama", lambda prompt: '{"clause_type":"Insurance"}')

    result = generator.classify_clause(
        clause_text="The supplier shall maintain insurance coverage.",
        query_vector=[0.1, 0.2],
        qdrant_client=object(),
        labels=LABELS,
        label_definitions=DEFINITIONS,
    )

    assert retrieval_calls == [5, 10]
    assert result["retrieval_status"] == "empty_after_retry"
    assert result["candidate_labels"] == LABELS
    assert result["predicted_label"] == "NO_APPLICABLE_LABEL"


def test_multiple_similar_labels_remain_deduplicated_and_ranked(monkeypatch):
    result = _classify(
        monkeypatch,
        [
            {"clause_type": "Insurance", "score": 0.91, "clause_text": "..."},
            {"clause_type": "Insurance", "score": 0.88, "clause_text": "..."},
            {"clause_type": "Termination", "score": 0.84, "clause_text": "..."},
        ],
        '{"clause_type":"Termination"}',
    )

    assert result["candidate_labels"] == ["Insurance", "Termination"]
    assert result["predicted_label"] == "Termination"
    assert result["retrieved_scores"] == [0.91, 0.88, 0.84]


def test_empty_retrieval_and_provider_failure_use_deterministic_full_set_fallback(monkeypatch):
    monkeypatch.setattr(generator, "retrieve_similar", lambda *args, **kwargs: [])

    def fail_provider(prompt):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(generator, "call_ollama", fail_provider)
    result = generator.classify_clause(
        clause_text="The supplier shall maintain insurance coverage.",
        query_vector=[0.1, 0.2],
        qdrant_client=object(),
        labels=LABELS,
        label_definitions=DEFINITIONS,
    )

    assert result["predicted_label"] == "NO_APPLICABLE_LABEL"
    assert result["classification_source"] == "abstention"


def test_progress_never_reports_unknown_as_successful_classification(monkeypatch):
    events = []
    result = _classify(
        monkeypatch,
        [{"clause_type": "Insurance", "score": 0.8, "clause_text": "..."}],
        '{"clause_type":"UNKNOWN"}',
    )
    # Re-run with a callback to verify the user-visible trace.
    monkeypatch.setattr(generator, "retrieve_similar", lambda *args, **kwargs: [{"clause_type": "Insurance", "score": 0.8, "clause_text": "..."}])
    monkeypatch.setattr(generator, "call_ollama", lambda prompt: '{"clause_type":"UNKNOWN"}')
    generator.classify_clause(
        clause_text="The supplier shall maintain insurance coverage.",
        query_vector=[0.1, 0.2],
        qdrant_client=object(),
        labels=LABELS,
        label_definitions=DEFINITIONS,
        progress_callback=events.append,
    )

    messages = [event["message"] for event in events]
    assert result["predicted_label"] == "NO_APPLICABLE_LABEL"
    assert not any(message == "Classification complete: UNKNOWN" for message in messages)
    assert any(message.startswith("Classification selected:") for message in messages)
