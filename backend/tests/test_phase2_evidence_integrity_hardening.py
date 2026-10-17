import json

from app.core.risk import contract_checks
from app.core.risk.risk_engine import _evidence_source, _majority


def test_missing_model_passes_count_as_abstentions():
    records = [
        {"answer": "YES"},
        {"answer": "YES"},
    ]

    answer, agreement = _majority(records, expected_passes=3)

    assert answer == "YES"
    assert agreement == 0.6667


def test_missing_model_passes_prevent_false_majority():
    records = [{"answer": "YES"}]

    answer, agreement = _majority(records, expected_passes=3)

    assert answer == "DON'T KNOW"
    assert agreement == 0.3333


def test_evidence_source_is_ambiguous_when_quote_occurs_in_multiple_context_clauses():
    context = [
        {"clause_index": 4, "clause_text": "The supplier shall maintain insurance coverage."},
        {"clause_index": 7, "clause_text": "The supplier shall maintain insurance coverage."},
    ]

    source = _evidence_source(
        "The supplier shall maintain insurance coverage.",
        "Insurance requirements apply.",
        1,
        context,
    )

    assert source["evidence_source_status"] == "AMBIGUOUS"
    assert source["evidence_clause_index"] is None
    assert source["evidence_clause_candidates"] == [4, 7]


def test_evidence_source_reports_verified_target_clause():
    source = _evidence_source(
        "Liability is unlimited.",
        "Liability is unlimited.",
        3,
        [{"clause_index": 4, "clause_text": "Liability is unlimited."}],
    )

    assert source["evidence_source_status"] == "VERIFIED"
    assert source["evidence_clause_index"] == 3


def test_cross_clause_finding_abstains_when_evidence_clause_is_not_declared(monkeypatch):
    playbook = {
        "playbook_hash": "test-playbook",
        "sources": {},
        "cross_clause_checks": [{
            "id": "X-1",
            "question": "Does the agreement create a cross-clause risk?",
            "sources": [],
        }],
        "document_level_checks": [],
    }
    clauses = [
        {"clause_index": 1, "predicted_label": "Liability", "clause_text": "Liability is unlimited."},
        {"clause_index": 2, "predicted_label": "Indemnity", "clause_text": "Supplier indemnifies Customer."},
    ]
    response = {
        "cross_clause_findings": [{
            "check_id": "X-1",
            "answer": "YES",
            "status": "POTENTIAL_RISK",
            "risk_type": "Cross-clause exposure",
            "clause_ids": [1],
            "evidence": [{"clause_id": 2, "quote": "Supplier indemnifies Customer."}],
            "why_flagged": "Synthetic test.",
            "score_components": {},
        }],
        "document_findings": [],
    }
    monkeypatch.setattr(contract_checks, "call_ollama", lambda *args, **kwargs: json.dumps(response))

    cross, _ = contract_checks.analyze_contract_checks(
        clauses,
        playbook=playbook,
        passes=1,
    )

    finding = next(item for item in cross if item["check_id"] == "X-1")
    assert finding["risk_status"] == "INSUFFICIENT_EVIDENCE"
    assert finding["evidence"] == []
