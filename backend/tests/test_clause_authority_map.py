import csv
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "risk"))
from validate_clause_authority_map import validate as validate_authority_map  # noqa: E402


def _json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_authority_catalog_and_map_pass_schema_and_taxonomy_validation():
    report, problems = validate_authority_map()
    assert problems == []
    assert report["status"] == "PASS"
    assert report["legal_approval_status"] == "NOT_APPROVED"
    assert report["taxonomy_count"] == 37
    assert report["mapped_clause_count"] == 37
    assert report["authority_record_count"] == 33
    assert report["authority_records_referenced_by_map"] == 33


def test_authority_schemas_validate_committed_records():
    catalog = _json("data/risk/authority_catalog.json")
    catalog_schema = _json("data/risk/authority_catalog.schema.json")
    clause_map = _json("data/risk/clause_authority_map.json")
    map_schema = _json("data/risk/clause_authority_map.schema.json")

    Draft202012Validator.check_schema(catalog_schema)
    Draft202012Validator.check_schema(map_schema)
    assert Draft202012Validator(catalog_schema, format_checker=FormatChecker()).is_valid(catalog)
    assert Draft202012Validator(map_schema, format_checker=FormatChecker()).is_valid(clause_map)


def test_every_clause_category_has_explicit_authority_or_no_universal_statute_rationale():
    playbook = _json("data/risk/commercial_clause_risk_playbook.json")
    clause_map = _json("data/risk/clause_authority_map.json")
    taxonomy = set(playbook["clause_types"])
    mapped = {item["clause_type"]: item for item in clause_map["clauses"]}

    assert set(mapped) == taxonomy
    assert len(mapped) == 37
    for clause_type, item in mapped.items():
        assert item["legal_conclusion_allowed"] is False
        assert item["review_status"] == "RESEARCH_SEED_NOT_LEGALLY_APPROVED"
        assert item["scope_note"].strip()
        assert item["jurisdiction_policy"].strip()
        assert item["required_context"]
        if item["authority_ids"]:
            assert item["authority_coverage_status"] == "LIMITED_PRIMARY_AUTHORITY_LINKED"
        else:
            assert item["authority_coverage_status"] == "NO_UNIVERSAL_PRIMARY_AUTHORITY_IDENTIFIED"
            assert any(
                phrase in item["scope_note"].lower()
                for phrase in ("no universal", "no single general", "no general")
            ), clause_type


def test_authority_catalog_has_traceable_source_provenance_and_no_unreferenced_records():
    catalog = _json("data/risk/authority_catalog.json")
    clause_map = _json("data/risk/clause_authority_map.json")
    by_id = {item["authority_id"]: item for item in catalog["authorities"]}
    referenced = {
        authority_id
        for clause in clause_map["clauses"]
        for authority_id in clause["authority_ids"]
    }

    assert len(by_id) == len(catalog["authorities"])
    assert referenced == set(by_id)
    assert all(item["url"].startswith("https://") for item in by_id.values())
    assert all(item["pinpoint"].strip() for item in by_id.values())
    assert all(item["retrieval_date"] == catalog["retrieval_date"] for item in by_id.values())
    assert all(item["jurisdiction"].strip() for item in by_id.values())
    assert all(item["source_tier"] in {"A", "B"} for item in by_id.values())
    assert all(item["authority_status"].strip() for item in by_id.values())
    assert all(item["effective_date_status"].strip() for item in by_id.values())
    assert all(item["scope_limit"].strip() for item in by_id.values())


def test_noncompete_mapping_does_not_repeat_the_vacated_ftc_rule_as_current_law():
    catalog = _json("data/risk/authority_catalog.json")
    clause_map = _json("data/risk/clause_authority_map.json")
    authority = {item["authority_id"]: item for item in catalog["authorities"]}
    noncompete = next(item for item in clause_map["clauses"] if item["clause_type"] == "Non-Compete")

    ftc = authority["FTC_NONCOMPETE_STATUS_2025"]
    assert ftc["source_type"] == "REGULATOR_STATUS_NOTICE"
    assert "NOT_IN_EFFECT" in ftc["currentness_status"]
    assert "STATE_LAW" in noncompete["jurisdiction_policy"]
    assert noncompete["legal_conclusion_allowed"] is False


def test_ucc_authorities_are_explicitly_limited_to_goods_transactions():
    clause_map = _json("data/risk/clause_authority_map.json")
    categories = {item["clause_type"]: item for item in clause_map["clauses"]}
    for name in ("Anti-Assignment", "Cap On Liability", "Liquidated Damages", "Warranty Duration"):
        assert "goods" in categories[name]["scope_note"].lower()
        assert categories[name]["legal_conclusion_allowed"] is False


def test_rule_review_queue_contains_authority_mapping_for_all_clause_rules():
    with (ROOT / "data/risk/rule_review_queue.csv").open(encoding="utf-8", newline="") as handle:
        queue = list(csv.DictReader(handle))
    assert len(queue) == 121
    required = {
        "authority_map_clause_type",
        "authority_map_ids_json",
        "authority_sources_json",
        "authority_coverage_status",
        "authority_scope_note",
        "authority_jurisdiction_policy",
        "authority_map_review_status",
    }
    assert required <= set(queue[0])

    clause_rows = [row for row in queue if row["clause_type"]]
    non_clause_rows = [row for row in queue if not row["clause_type"]]
    assert len(clause_rows) == 101
    assert len(non_clause_rows) == 20
    assert all(row["authority_map_clause_type"] == row["clause_type"] for row in clause_rows)
    assert all(row["authority_map_review_status"] == "RESEARCH_SEED_NOT_LEGALLY_APPROVED" for row in queue)
    assert all(row["authority_coverage_status"] != "" for row in queue)
    catalog = _json("data/risk/authority_catalog.json")
    catalog_by_id = {item["authority_id"]: item for item in catalog["authorities"]}
    for row in clause_rows:
        ids = json.loads(row["authority_map_ids_json"])
        sources = json.loads(row["authority_sources_json"])
        assert len(sources) == len(ids)
        assert [source["authority_id"] for source in sources] == ids
        for source in sources:
            assert source["url"].startswith("https://")
            assert source["source_type"] in {"FEDERAL_STATUTE", "STATE_STATUTE", "REGULATOR_STATUS_NOTICE", "PRIMARY_COURT_OPINION_REPUBLISHED"}
            assert source["pinpoint"]
            assert source["jurisdiction"]
            assert source["source_tier"] in {"A", "B"}
            assert source["retrieval_date"] == catalog["retrieval_date"]
            assert source["authority_status"]
            assert source["effective_date_status"]
            assert catalog_by_id[source["authority_id"]]["url"] == source["url"]
    assert all(json.loads(row["authority_map_ids_json"]) is not None for row in queue)
    assert all(
        json.loads(row["authority_sources_json"]) == []
        and row["authority_coverage_status"] == "RULE_FAMILY_SPECIFIC_AUTHORITY_REVIEW_REQUIRED"
        for row in non_clause_rows
    )

def test_release_checks_include_authority_and_registry_gates():
    runner = (ROOT / "scripts/risk/run_release_checks.py").read_text(encoding="utf-8")
    for check in (
        "rule_registry_reproducibility",
        "rule_registry_governance",
        "clause_authority_map",
        "risk_gold_schema",
        "rule_review_queue_reproducibility",
    ):
        assert f'("{check}"' in runner
    for path in (
        'ROOT / "data/risk/authority_catalog.json"',
        'ROOT / "data/risk/clause_authority_map.json"',
        'ROOT / "data/risk/evaluation/risk_gold.schema.json"',
        'ROOT / "scripts/risk/validate_risk_gold.py"',
        'ROOT / "data/risk/rule_registry.jsonl"',
        'ROOT / "data/risk/rule_review_queue.csv"',
    ):
        assert path in runner
