import json
import re

from app.core.risk import contract_checks


def _playbook():
    return {
        "playbook_hash": "test-hash",
        "sources": {},
        "clause_types": {},
        "cross_clause_checks": [
            {
                "id": f"X-{i}",
                "question": f"Question for cross-check {i}?",
                "pair": ["Cap On Liability", "Indemnification"],
                "risk_domain": "Liability Risk",
                "sources": [],
            }
            for i in range(1, 11)
        ],
        "document_level_checks": [
            {
                "id": f"DOC-{i}",
                "question": f"Question for document-check {i}?",
                "risk_domain": "Commercial Risk",
                "sources": [],
            }
            for i in range(1, 4)
        ],
    }


def _fake_model_answer(prompt):
    cross_block = prompt.split("CROSS-CLAUSE CHECKS\n", 1)[1].split("\n\nDOCUMENT CHECKS\n", 1)[0]
    doc_block = prompt.split("DOCUMENT CHECKS\n", 1)[1].split("\n\nDETERMINISTIC INTERACTION SIGNALS", 1)[0]
    cross = json.loads(cross_block)
    docs = json.loads(doc_block)
    return json.dumps({
        "cross_clause_findings": [
            {"check_id": item["id"], "answer": "NO", "status": "NO_RISK",
             "risk_type": None, "clause_ids": [1], "evidence": [],
             "why_flagged": "No synthetic risk condition was detected.", "score_components": {}}
            for item in cross
        ],
        "document_findings": [
            {"check_id": item["id"], "answer": "NO", "status": "NO_RISK",
             "risk_type": None, "clause_ids": [1], "evidence": [],
             "why_flagged": "No synthetic document-level risk condition was detected.", "score_components": {}}
            for item in docs
        ],
    })


def test_cross_document_checks_are_batched_and_all_13_results_survive(monkeypatch):
    calls = []

    def fake_call(prompt, **kwargs):
        calls.append(prompt)
        return _fake_model_answer(prompt)

    monkeypatch.setattr(contract_checks, "call_ollama", fake_call)
    clauses = [
        {"clause_index": 1, "predicted_label": "Cap On Liability", "clause_text": "Liability is capped."},
        {"clause_index": 2, "predicted_label": "Indemnification", "clause_text": "Indemnification is subject to the cap."},
    ]

    cross, document = contract_checks.analyze_contract_checks(
        clauses, playbook=_playbook(), passes=1
    )

    assert len(calls) == 4  # ceil((10 cross + 3 document checks) / 4)
    assert {item["check_id"] for item in cross} == {f"X-{i}" for i in range(1, 11)}
    assert {item["check_id"] for item in document} == {f"DOC-{i}" for i in range(1, 4)}
    assert all(item["risk_status"] == "NO_RISK" for item in cross + document)


def test_malformed_model_batch_only_abstains_for_that_batch(monkeypatch):
    calls = []

    def fake_call(prompt, **kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            return "truncated non-JSON response"
        return _fake_model_answer(prompt)

    monkeypatch.setattr(contract_checks, "call_ollama", fake_call)
    clauses = [
        {"clause_index": 1, "predicted_label": "Cap On Liability", "clause_text": "Liability is capped."},
        {"clause_index": 2, "predicted_label": "Indemnification", "clause_text": "Indemnification is subject to the cap."},
    ]

    cross, document = contract_checks.analyze_contract_checks(
        clauses, playbook=_playbook(), passes=1
    )
    cross_by_id = {item["check_id"]: item for item in cross}
    document_by_id = {item["check_id"]: item for item in document}

    assert len(calls) == 4
    assert set(cross_by_id) == {f"X-{i}" for i in range(1, 11)}
    assert set(document_by_id) == {f"DOC-{i}" for i in range(1, 4)}
    for i in range(1, 5):
        assert cross_by_id[f"X-{i}"]["risk_status"] == "INSUFFICIENT_EVIDENCE"
        assert cross_by_id[f"X-{i}"]["answer"] == "DON'T KNOW"
    for i in range(5, 11):
        assert cross_by_id[f"X-{i}"]["risk_status"] == "NO_RISK"
    assert all(item["risk_status"] == "NO_RISK" for item in document_by_id.values())
