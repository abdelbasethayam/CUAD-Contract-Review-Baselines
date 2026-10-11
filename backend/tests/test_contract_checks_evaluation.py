import json

from app.core.risk import contract_checks


def _fixture_playbook():
    return {
        "playbook_hash": "synthetic-test-playbook",
        "sources": {},
        "cross_clause_checks": [
            {
                "id": "X-10",
                "pair": ["Cap On Liability", "Indemnification"],
                "risk_domain": "Liability Risk",
                "risk_subdomain": "Remedy interaction",
                "question": "Is indemnification outside the liability cap?",
                "flag_if": "Yes",
                "sources": [],
            }
        ],
        "document_level_checks": [
            {
                "id": "DOC-2",
                "risk_domain": "Dispute Resolution Risk",
                "question": "Do precedence terms reverse substantive protections?",
                "flag_if": "Yes",
                "sources": [],
            }
        ],
        "clause_types": {},
    }


def _contract_clauses():
    return [
        {
            "clause_index": 0,
            "predicted_label": "Cap On Liability",
            "clause_text": "Supplier liability shall not exceed fees paid in the prior month.",
        },
        {
            "clause_index": 1,
            "predicted_label": "Indemnification",
            "clause_text": "Supplier indemnifies Customer for all claims outside any liability cap.",
        },
        {
            "clause_index": 2,
            "predicted_label": "Governing Law",
            "clause_text": "Supplier's online terms prevail over this Agreement in every conflict.",
        },
    ]


def test_cross_clause_and_document_findings_require_exact_contract_quotes(monkeypatch):
    payload = {
        "cross_clause_findings": [
            {
                "check_id": "X-10",
                "answer": "YES",
                "status": "POTENTIAL_RISK",
                "risk_type": "Indemnity outside cap",
                "clause_ids": [0, 1],
                "evidence": [
                    {"clause_id": 0, "quote": "Supplier liability shall not exceed fees paid in the prior month."},
                    {"clause_id": 1, "quote": "Supplier indemnifies Customer for all claims outside any liability cap."},
                ],
                "why_flagged": "The clauses may leave indemnity exposure outside the low cap.",
                "score_components": {
                    "exposure_magnitude": 4,
                    "likelihood_uncertainty": 3,
                    "scope_duration": 4,
                    "control_weakness": 4,
                },
            }
        ],
        "document_findings": [
            {
                "check_id": "DOC-2",
                "answer": "YES",
                "status": "POTENTIAL_RISK",
                "risk_type": "Precedence override",
                "clause_ids": [2],
                "evidence": [
                    {"clause_id": 2, "quote": "Supplier's online terms prevail over this Agreement in every conflict."}
                ],
                "why_flagged": "Precedence favors the online terms.",
                "score_components": {
                    "exposure_magnitude": 3,
                    "likelihood_uncertainty": 3,
                    "scope_duration": 3,
                    "control_weakness": 4,
                },
            }
        ],
    }
    monkeypatch.setattr(contract_checks, "load_calibration", lambda: {})
    monkeypatch.setattr(contract_checks, "call_ollama", lambda *args, **kwargs: json.dumps(payload))

    cross, document = contract_checks.analyze_contract_checks(
        _contract_clauses(),
        playbook=_fixture_playbook(),
        passes=1,
    )

    x10 = next(item for item in cross if item["check_id"] == "X-10")
    doc2 = next(item for item in document if item["check_id"] == "DOC-2")
    assert x10["risk_status"] == "POTENTIAL_RISK"
    assert x10["risk_domain"] == "Liability Risk"
    assert set(x10["clause_ids"]) == {0, 1}
    assert len(x10["evidence"]) == 2
    assert doc2["risk_status"] == "POTENTIAL_RISK"
    assert doc2["risk_domain"] == "Dispute Resolution Risk"
    assert doc2["evidence"][0]["quote"] in _contract_clauses()[2]["clause_text"]


def test_cross_clause_finding_with_nonexistent_quote_abstains(monkeypatch):
    payload = {
        "cross_clause_findings": [
            {
                "check_id": "X-10",
                "answer": "YES",
                "status": "POTENTIAL_RISK",
                "risk_type": "Invented finding",
                "clause_ids": [0, 1],
                "evidence": [
                    {"clause_id": 0, "quote": "The contract has unlimited liability."}
                ],
                "why_flagged": "This sentence is not in the supplied contract.",
                "score_components": {},
            }
        ],
        "document_findings": [],
    }
    monkeypatch.setattr(contract_checks, "load_calibration", lambda: {})
    monkeypatch.setattr(contract_checks, "call_ollama", lambda *args, **kwargs: json.dumps(payload))

    cross, _ = contract_checks.analyze_contract_checks(
        _contract_clauses(),
        playbook=_fixture_playbook(),
        passes=1,
    )
    x10 = next(item for item in cross if item["check_id"] == "X-10")
    assert x10["risk_status"] == "INSUFFICIENT_EVIDENCE"
    assert x10["evidence"] == []


def test_omitted_cross_clause_and_document_checks_are_preserved_as_unresolved(monkeypatch):
    monkeypatch.setattr(contract_checks, "load_calibration", lambda: {})
    monkeypatch.setattr(
        contract_checks,
        "call_ollama",
        lambda *args, **kwargs: json.dumps(
            {"cross_clause_findings": [], "document_findings": []}
        ),
    )
    playbook = _fixture_playbook()
    cross, document = contract_checks.analyze_contract_checks(
        _contract_clauses(),
        playbook=playbook,
        passes=1,
    )
    assert len(cross) == 1 and cross[0]["risk_status"] == "INSUFFICIENT_EVIDENCE"
    assert len(document) == 1 and document[0]["risk_status"] == "INSUFFICIENT_EVIDENCE"
