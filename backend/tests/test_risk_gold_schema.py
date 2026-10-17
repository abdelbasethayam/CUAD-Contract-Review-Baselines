import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "risk"))
from validate_risk_gold import SCHEMA_PATH, validate_records  # noqa: E402


def _load_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _fixtures():
    schema = _load_json("data/risk/evaluation/risk_gold.schema.json")
    playbook = _load_json("data/risk/commercial_clause_risk_playbook.json")
    catalog = _load_json("data/risk/authority_catalog.json")
    registry = [
        json.loads(line)
        for line in (ROOT / "data/risk/rule_registry.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    base_rule = next(item for item in registry if item["record_kind"] == "BASE_RULE" and item.get("clause_type"))
    text = "The supplier may terminate immediately without notice."
    quote = text
    record = {
        "schema_version": 1,
        "record_id": "SYNTHETIC-GOLD-001",
        "contract_id": "SYNTHETIC-CONTRACT-001",
        "source_document_sha256": "a" * 64,
        "normalized_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "clause_type": base_rule["clause_type"],
        "rule_id": base_rule["rule_id"],
        "review_target": "COMMERCIAL_REVIEW_TRIGGER",
        "perspective": "customer_buyer",
        "contract_type": "synthetic commercial services agreement",
        "governing_law": {
            "status": "UNRESOLVED",
            "declared_law": None,
            "resolved_law": None,
            "relevant_date": None,
            "verification_basis": "Synthetic fixture; no legal proposition asserted."
        },
        "decision": "POTENTIAL_RISK",
        "evidence_basis": "EXACT_QUOTE",
        "evidence": [{
            "clause_id": "CLAUSE-1",
            "start_char": 0,
            "end_char": len(quote),
            "quote": quote,
            "quote_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
            "page": 1
        }],
        "authority_refs": [],
        "reviewer_1": {
            "reviewer_id": "reviewer-a",
            "decision": "POTENTIAL_RISK",
            "rationale": "Synthetic fixture tests schema and evidence provenance only.",
            "reviewed_at": "2026-10-17T08:00:00Z"
        },
        "reviewer_2": {
            "reviewer_id": "reviewer-b",
            "decision": "INSUFFICIENT_EVIDENCE",
            "rationale": "Synthetic fixture demonstrates an independent disagreement.",
            "reviewed_at": "2026-10-17T08:05:00Z"
        },
        "adjudication": {
            "adjudicator_id": "adjudicator-c",
            "final_decision": "POTENTIAL_RISK",
            "rationale": "Synthetic fixture outcome for validator tests only.",
            "adjudicated_at": "2026-10-17T08:10:00Z",
            "adjudication_reference": "SYNTHETIC-ADJ-001"
        },
        "split": "TRAIN",
        "near_duplicate_group_id": "SYNTHETIC-TEMPLATE-001",
        "dataset_version": "synthetic-test-v1",
        "annotation_guide_version": "1.0.0"
    }
    return schema, playbook, catalog, registry, text, record


def _validate(record, text_by_contract=None):
    schema, playbook, catalog, registry, _, _ = _fixtures()
    return validate_records(
        [record],
        schema=schema,
        taxonomy=set(playbook["clause_types"]),
        base_rule_ids={item["rule_id"] for item in registry if item["record_kind"] == "BASE_RULE"},
        authority_by_id={item["authority_id"]: item for item in catalog["authorities"]},
        normalized_text_by_contract=text_by_contract,
    )


def test_risk_gold_schema_is_valid_and_synthetic_fixture_passes():
    schema, playbook, catalog, registry, text, record = _fixtures()
    from jsonschema import Draft202012Validator, FormatChecker

    Draft202012Validator.check_schema(schema)
    assert Draft202012Validator(schema, format_checker=FormatChecker()).is_valid(record)
    assert _validate(record, {record["contract_id"]: text}) == []


def test_gold_validator_rejects_reused_reviewer_and_adjudicator_identity():
    _, _, _, _, _, record = _fixtures()
    record["reviewer_2"]["reviewer_id"] = record["reviewer_1"]["reviewer_id"]
    record["adjudication"]["adjudicator_id"] = record["reviewer_1"]["reviewer_id"]
    problems = _validate(record)
    assert any("reviewers_must_be_distinct" in item for item in problems)
    assert any("adjudicator_must_be_independent" in item for item in problems)


def test_gold_validator_rejects_contract_or_template_leakage_across_splits():
    _, _, _, _, _, first = _fixtures()
    second = json.loads(json.dumps(first))
    second["record_id"] = "SYNTHETIC-GOLD-002"
    second["split"] = "TEST"
    problems = validate_records(
        [first, second],
        schema=_fixtures()[0],
        taxonomy=set(_fixtures()[1]["clause_types"]),
        base_rule_ids={item["rule_id"] for item in _fixtures()[3] if item["record_kind"] == "BASE_RULE"},
        authority_by_id={item["authority_id"]: item for item in _fixtures()[2]["authorities"]},
    )
    assert any("contract_leakage_across_splits" in item for item in problems)
    assert any("near_duplicate_leakage_across_splits" in item for item in problems)


def test_gold_validator_checks_exact_quote_hash_and_source_offsets():
    _, _, _, _, text, record = _fixtures()
    record["evidence"][0]["quote_sha256"] = "b" * 64
    record["evidence"][0]["start_char"] = 1
    problems = _validate(record, {record["contract_id"]: text})
    assert any("evidence_quote_hash_mismatch" in item for item in problems)
    assert any("evidence_quote_not_exact_source_span" in item for item in problems)


def test_legal_proposition_requires_verified_effective_period_not_just_a_source_link():
    _, _, catalog, _, text, record = _fixtures()
    source = next(item for item in catalog["authorities"] if item["authority_id"] == "USC_17_106")
    record["review_target"] = "LEGAL_PROPOSITION"
    record["governing_law"] = {
        "status": "VERIFIED",
        "declared_law": "United States federal law",
        "resolved_law": "US-FEDERAL",
        "relevant_date": "2026-10-17",
        "verification_basis": "Synthetic fixture deliberately does not provide a real legal analysis."
    }
    record["authority_refs"] = [{
        "authority_id": source["authority_id"],
        "citation": source["citation"],
        "pinpoint": source["pinpoint"],
        "jurisdiction": source["jurisdiction"],
        "source_tier": source["source_tier"],
        "effective_date_status": source["effective_date_status"],
        "retrieval_date": source["retrieval_date"],
        "verification_status": source["verification_status"],
        "applicability_basis": "Synthetic fixture: authority is within the stated jurisdiction and statutory subject-matter scope."
    }]
    problems = _validate(record, {record["contract_id"]: text})
    assert any("authority_effective_period_not_verified" in item for item in problems)

def test_gold_validator_fails_closed_when_normalized_contract_text_is_missing():
    _, _, _, _, _, record = _fixtures()
    problems = _validate(record, {})
    assert any("normalized_text_missing_for_contract" in item for item in problems)

def test_gold_validator_rejects_record_decision_that_differs_from_adjudication():
    _, _, _, _, text, record = _fixtures()
    record["decision"] = "NO_RISK"
    record["evidence_basis"] = "ABSENCE_AFTER_DOCUMENT_SCAN"
    record["evidence"] = []
    problems = _validate(record, {record["contract_id"]: text})
    assert any("record_decision_must_match_adjudication" in item for item in problems)

def test_legal_proposition_rejects_authority_from_a_different_state():
    _, _, catalog, _, text, record = _fixtures()
    source = next(item for item in catalog["authorities"] if item["authority_id"] == "NY_UCC_2_719")
    record["review_target"] = "LEGAL_PROPOSITION"
    record["governing_law"] = {
        "status": "VERIFIED",
        "declared_law": "Delaware law",
        "resolved_law": "US-DE",
        "relevant_date": "2026-10-17",
        "verification_basis": "Synthetic fixture for jurisdiction mismatch regression."
    }
    record["authority_refs"] = [{
        "authority_id": source["authority_id"],
        "citation": source["citation"],
        "pinpoint": source["pinpoint"],
        "jurisdiction": source["jurisdiction"],
        "source_tier": source["source_tier"],
        "effective_date_status": source["effective_date_status"],
        "retrieval_date": source["retrieval_date"],
        "verification_status": source["verification_status"],
        "applicability_basis": "Deliberately incompatible New York authority for a Delaware-governed contract."
    }]
    problems = _validate(record, {record["contract_id"]: text})
    assert any("authority_jurisdiction_mismatch" in item for item in problems)


def test_legal_proposition_rejects_source_whose_official_text_was_not_verified():
    _, _, catalog, _, text, record = _fixtures()
    source = next(item for item in catalog["authorities"] if item["authority_id"] == "CA_BPC_16600")
    record["review_target"] = "LEGAL_PROPOSITION"
    record["governing_law"] = {
        "status": "VERIFIED",
        "declared_law": "California law",
        "resolved_law": "US-CA",
        "relevant_date": "2026-10-17",
        "verification_basis": "Synthetic fixture for source-verification regression."
    }
    record["authority_refs"] = [{
        "authority_id": source["authority_id"],
        "citation": source["citation"],
        "pinpoint": source["pinpoint"],
        "jurisdiction": source["jurisdiction"],
        "source_tier": source["source_tier"],
        "effective_date_status": source["effective_date_status"],
        "retrieval_date": source["retrieval_date"],
        "verification_status": source["verification_status"],
        "applicability_basis": "Deliberately unverified official-text lead."
    }]
    problems = _validate(record, {record["contract_id"]: text})
    assert any("authority_source_verification_not_cleared" in item for item in problems)
