import json
from pathlib import Path

from app.core.risk.deterministic_rules import evaluate_playbook_rules
from app.core.risk.risk_playbook import load_playbook

ROOT = Path(__file__).resolve().parents[2]


def test_every_deterministic_rule_has_executed_positive_negative_and_edge_cases():
    playbook = load_playbook()
    rules_by_id = {item["id"]: item for item in playbook["deterministic_rules"]}
    registry = [
        json.loads(line)
        for line in (ROOT / "data/risk/rule_registry.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    deterministic = [
        item for item in registry
        if item["record_kind"] == "BASE_RULE" and item.get("rule_family") == "DETERMINISTIC_REGEX"
    ]
    assert len(deterministic) == 7

    for record in deterministic:
        rule_id = record["base_rule_id"]
        assert rule_id in rules_by_id
        cases = record["regression_cases"]
        assert cases["positive"], f"{rule_id}: no positive cases"
        assert cases["negative"], f"{rule_id}: no negative cases"
        assert cases["edge"], f"{rule_id}: no edge cases"

        for text in cases["positive"]:
            findings = evaluate_playbook_rules(
                clause_text=text,
                clause_index=1,
                clause_type="Regression test",
                playbook=playbook,
            )
            assert rule_id in {item["check_id"] for item in findings}, f"{rule_id}: positive missed: {text}"

        for text in cases["negative"]:
            findings = evaluate_playbook_rules(
                clause_text=text,
                clause_index=1,
                clause_type="Regression test",
                playbook=playbook,
            )
            assert rule_id not in {item["check_id"] for item in findings}, f"{rule_id}: negative false positive: {text}"

        for case in cases["edge"]:
            findings = evaluate_playbook_rules(
                clause_text=case["text"],
                clause_index=1,
                clause_type="Regression test",
                playbook=playbook,
            )
            actual = rule_id in {item["check_id"] for item in findings}
            assert actual is case["expected_match"], f"{rule_id}: edge mismatch: {case['text']}"
