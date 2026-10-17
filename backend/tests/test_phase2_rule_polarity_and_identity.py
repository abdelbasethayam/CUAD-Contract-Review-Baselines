from app.core.risk.risk_engine import _expected_trigger_answer, _question_for_check
from app.core.risk.risk_playbook import applicable_checks, load_playbook


def test_negative_trigger_polarity_is_not_assumed_to_be_yes():
    assert _expected_trigger_answer({"id": "AUD-2", "flag_if": "No"}) == "NO"
    assert _expected_trigger_answer({
        "id": "LOL-2",
        "_playbook_category": "Cap On Liability",
        "flag_if": "One-sided protecting only the counterparty",
    }) == "NO"


def test_legacy_open_questions_are_normalized():
    assert _question_for_check({
        "id": "AA-2",
        "_playbook_category": "Anti-Assignment",
        "question": "What is the consent standard?",
    }).startswith("Does the consent standard impose an absolute assignment ban")
    assert _question_for_check({
        "id": "COC-1",
        "_playbook_category": "Change Of Control",
        "question": "What happens on a change of control?",
    }).startswith("Does a change of control trigger automatic termination")
    assert _question_for_check({
        "id": "IP-1",
        "_playbook_category": "Ip Ownership Assignment",
        "question": "Who owns newly created or deliverable IP?",
    }).startswith("Does the vendor retain ownership of newly created or deliverable IP")


def test_duplicate_non_solicit_ids_are_stable_and_distinct():
    playbook = load_playbook()
    checks = applicable_checks(
        playbook,
        "No-Solicit Of Customers",
        clause_text="The supplier shall not solicit customers or employees.",
    )
    duplicates = [item for item in checks if item.get("_base_check_id") in {"NS-1", "NS-2"}]
    assert len(duplicates) == 4
    assert len({item["id"] for item in duplicates}) == 4
    assert {item["_playbook_category"] for item in duplicates} == {
        "No-Solicit Of Customers",
        "No-Solicit Of Employees",
    }
    assert all(item.get("rule_registry_metadata", {}).get("rule_id") for item in duplicates)


def test_negative_trigger_can_return_supported_positive_finding(monkeypatch):
    import json
    from app.core.risk import risk_engine

    clause = "The supplier may audit the customer at any time."
    playbook = {
        "playbook_hash": "synthetic-negative-trigger",
        "sources": {},
        "rule_registry": {"status": "PILOT_REVIEW_ONLY"},
        "clause_types": {
            "Audit Rights": {
                "checklist": [{
                    "id": "AUD-2",
                    "question": "Are notice, frequency, and confidentiality protections for audits stated?",
                    "flag_if": "No",
                    "do_not_flag_if": [],
                    "sources": [],
                    "risk_domain": "Compliance Risk",
                }]
            }
        },
        "deterministic_rules": [],
    }
    response = json.dumps({
        "checks": [{
            "check_id": "AUD-2",
            "answer": "NO",
            "status": "POTENTIAL_RISK",
            "risk_type": "Unbounded audit access",
            "evidence": clause,
            "why_flagged": "The text grants unrestricted audit access without the listed safeguards.",
        }]
    })
    monkeypatch.setattr(risk_engine, "call_ollama", lambda *args, **kwargs: response)
    monkeypatch.setattr(risk_engine, "retrieve_related_contract_context", lambda *args, **kwargs: [])
    monkeypatch.setattr(risk_engine, "detect_legal_indicators", lambda *args, **kwargs: {"matched_indicators": []})
    monkeypatch.setattr(risk_engine, "retrieve_legal_guidance", lambda *args, **kwargs: [])

    findings = risk_engine.analyze_clause_risk(
        clause_index=1,
        clause_text=clause,
        clause_type="Audit Rights",
        query_vector=None,
        contract_clauses=[],
        playbook=playbook,
        passes=1,
    )
    finding = next(item for item in findings if item["check_id"] == "AUD-2")
    assert finding["answer"] == "NO"
    assert finding["risk_status"] == "POTENTIAL_RISK"
    assert finding["risk"] is True
    assert finding["evidence_source_status"] == "VERIFIED"
    assert finding["provenance"]["risk_trigger_answer"] == "NO"
