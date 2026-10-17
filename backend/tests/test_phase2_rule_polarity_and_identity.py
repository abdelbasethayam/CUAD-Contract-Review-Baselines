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
