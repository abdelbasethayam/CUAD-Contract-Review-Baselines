import json
from unittest.mock import patch

from app.core.risk.contract_checks import analyze_contract_checks, _fallback_evidence_for_check
from app.core.risk.deterministic_cross_checks import run_deterministic_cross_checks


CLAUSES = [
    {
        "clause_index": 7,
        "predicted_label": "Liquidated Damages",
        "clause_text": "7. Party B shall be responsible for all of Party A's economic loss and relevant liquidated damages.",
    },
    {
        "clause_index": 10,
        "predicted_label": "Liquidated Damages",
        "clause_text": "10. Party B shall pay one-month freight as liquidated damages and compensate Party A's other losses.",
    },
    {
        "clause_index": 12,
        "predicted_label": "NO_APPLICABLE_LABEL",
        "clause_text": "12. Any dispute shall be subject to the jurisdiction of the People's Court where this Agreement is signed.",
    },
    {
        "clause_index": 13,
        "predicted_label": "NO_APPLICABLE_LABEL",
        "clause_text": "13. The annex of this Agreement constitutes a part of this Agreement and has the same effect as this Agreement.",
    },
    {
        "clause_index": 15,
        "predicted_label": "NO_APPLICABLE_LABEL",
        "clause_text": "15. Any different interpretation of this Agreement by both Parties is subject to final interpretation by Party A.",
    },
]


def _playbook(check_id, question):
    return {
        "playbook_hash": "test-playbook",
        "cross_clause_checks": [{"id": check_id, "question": question, "sources": []}],
        "document_level_checks": [],
    }


def test_fallback_evidence_for_dispute_check_is_specific_to_court_clause():
    check = {"id": "DOC-3", "question": "Are governing law, forum, and dispute mechanism missing or inconsistent?"}
    evidence = _fallback_evidence_for_check(check, CLAUSES)
    assert [item["clause_id"] for item in evidence] == [12]
    assert "People's Court" in evidence[0]["quote"]


def test_fallback_evidence_for_precedence_check_surfaces_unilateral_interpretation_and_annex():
    check = {"id": "DOC-2", "question": "Do definitions or order-of-precedence clauses narrow or reverse a protective substantive clause?"}
    evidence = _fallback_evidence_for_check(check, CLAUSES)
    ids = [item["clause_id"] for item in evidence]
    assert ids[:2] == [15, 13]
    assert "final interpretation by Party A" in evidence[0]["quote"]


def test_missing_model_answer_keeps_exact_evidence_and_actionable_reason():
    playbook = _playbook("DOC-3", "Are governing law, forum, and dispute mechanism missing or inconsistent?")
    with patch("app.core.risk.contract_checks.call_ollama", side_effect=RuntimeError("model unavailable")):
        findings, _ = analyze_contract_checks(CLAUSES, playbook=playbook, passes=1)
    finding = findings[0]
    assert finding["risk_status"] == "INSUFFICIENT_EVIDENCE"
    assert finding["clause_ids"] == [12]
    assert finding["evidence"][0]["quote"] == CLAUSES[2]["clause_text"]
    assert "not a confirmed risk" in finding["why_flagged"]
    assert "does not name the city/place" in finding["why_flagged"]


def test_invalid_model_quote_falls_back_to_exact_contract_excerpt():
    playbook = _playbook("DOC-3", "Are governing law, forum, and dispute mechanism missing or inconsistent?")
    response = json.dumps({
        "cross_clause_findings": [{
            "check_id": "DOC-3",
            "answer": "DON'T KNOW",
            "status": "INSUFFICIENT_EVIDENCE",
            "risk_type": None,
            "clause_ids": [12],
            "evidence": [{"clause_id": 12, "quote": "quote not present in the contract"}],
            "why_flagged": "The cited evidence could not be verified.",
        }],
        "document_findings": [],
    })
    with patch("app.core.risk.contract_checks.call_ollama", return_value=response):
        findings, _ = analyze_contract_checks(CLAUSES, playbook=playbook, passes=1)
    finding = findings[0]
    assert finding["risk_status"] == "INSUFFICIENT_EVIDENCE"
    assert finding["clause_ids"] == [12]
    assert finding["evidence"][0]["quote"] == CLAUSES[2]["clause_text"]
    assert "model's original cited excerpts were incomplete or off-topic" in finding["why_flagged"]


def test_exit_candidate_uses_contract_text_when_classifier_abstains():
    clauses = [
        {"clause_index": 2, "predicted_label": "NO_APPLICABLE_LABEL", "clause_text": "2. This Agreement is valid for an indefinite term."},
        {"clause_index": 8, "predicted_label": "NO_APPLICABLE_LABEL", "clause_text": "8. Party A can terminate this Agreement without compensation."},
        {"clause_index": 9, "predicted_label": "NO_APPLICABLE_LABEL", "clause_text": "9. Party A has the right to terminate this Agreement after breach."},
    ]
    signals = run_deterministic_cross_checks(clauses)
    exit_signal = next(item for item in signals if item["id"] == "DET-EXIT-FAILURE")
    assert {2, 8, 9}.issubset(set(exit_signal["clause_ids"]))


def test_exact_but_off_topic_model_quote_is_replaced_for_document_precedence_check():
    playbook = _playbook("DOC-2", "Do definitions or order-of-precedence clauses narrow or reverse a protective substantive clause?")
    response = json.dumps({
        "cross_clause_findings": [{
            "check_id": "DOC-2",
            "answer": "DON'T KNOW",
            "status": "INSUFFICIENT_EVIDENCE",
            "risk_type": None,
            "clause_ids": [12],
            "evidence": [{"clause_id": 12, "quote": CLAUSES[2]["clause_text"]}],
            "why_flagged": "Termination rights may interact with the dispute clause.",
        }],
        "document_findings": [],
    })
    with patch("app.core.risk.contract_checks.call_ollama", return_value=response):
        findings, _ = analyze_contract_checks(CLAUSES, playbook=playbook, passes=1)
    finding = findings[0]
    assert finding["risk_status"] == "INSUFFICIENT_EVIDENCE"
    assert 12 not in finding["clause_ids"]
    assert 15 in finding["clause_ids"]
    assert "off-topic" in finding["why_flagged"]

[executed on device: jupyter-group-digi2026-g6 (a8417900-e68e-4ee2-bbe7-fc3493ade5e1)]