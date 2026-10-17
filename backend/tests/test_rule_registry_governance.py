import csv
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from app.core.risk.confidence_calibration import (
    SUPPORT_SCORE_VERSION,
    confidence_from_support_score,
)
from app.core.risk.risk_playbook import load_playbook
from app.core.risk.risk_engine import _support_score

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "risk"))
from build_rule_registry import AUTHORITY_CATALOG_PATH, AUTHORITY_MAP_PATH, PLAYBOOK_PATH, _git_blob_sha, _source_registry, build_artifacts
from validate_rule_registry import _rule_lifecycle_problems


def _valid_artifact(**overrides):
    artifact = {
        "calibration_status": "VALIDATED_ON_LOCKED_TEST",
        "target": "PREDICTION_CORRECTNESS",
        "support_score_version": SUPPORT_SCORE_VERSION,
        "playbook_hash": "playbook-A",
        "calibration_version": "test-calibration-v1",
        "model_type": "logistic_sigmoid",
        "coefficient": 3.0,
        "intercept": -1.0,
        "calibration_rows": 300,
        "calibration_contract_count": 50,
        "calibration_correct_count": 200,
        "calibration_incorrect_count": 100,
        "locked_test_rows": 100,
        "locked_test_contract_count": 25,
        "locked_test_metrics": {
            "brier_calibrated": 0.10,
            "brier_constant_prevalence_baseline": 0.25,
            "brier_improvement_ci_95": [0.01, 0.20],
            "ece_10_bins": 0.05,
            "test_correct_count": 70,
            "test_incorrect_count": 30,
        },
        "dataset_sha256": "a" * 64,
        "dual_annotator_required": True,
        "adjudicator_required": True,
        "contract_disjoint": True,
    }
    artifact.update(overrides)
    return artifact


def test_runtime_loads_governed_registry_and_explicit_source_metadata():
    playbook = load_playbook()
    registry = playbook["rule_registry"]
    manifest = json.loads((ROOT / "data/risk/rule_registry_manifest.json").read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in (ROOT / "data/risk/rule_registry.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    base_count = sum(item["record_kind"] == "BASE_RULE" for item in records)
    candidate_count = sum(item["record_kind"] == "CONTEXT_VARIANT_CANDIDATE" for item in records)

    assert registry["status"] == "PILOT_REVIEW_ONLY"
    assert registry["base_rule_count"] == base_count == manifest["base_rule_count"]
    assert registry["candidate_rule_count"] == candidate_count == manifest["candidate_rule_count"]
    assert registry["production_approved_rule_count"] == manifest["production_approved_rule_count"]
    assert registry["legal_conclusion_allowed"] is False

    check = playbook["clause_types"]["Cap On Liability"]["checklist"][0]
    metadata = check["rule_registry_metadata"]
    assert metadata["validation_status"] == "DRAFT_UNVALIDATED"
    assert metadata["execution_status"] == "PILOT_REVIEW_ONLY"
    assert metadata["legal_conclusion_allowed"] is False
    assert "jurisdiction_scope" in metadata
    assert "source_status" in metadata
    assert metadata["citation_status"] == "INCOMPLETE_SOURCE_CITATION"
    assert metadata["legal_authority"]["can_support_legal_conclusion"] is False
    assert metadata["legal_authority"]["sources"]
    assert metadata["source_tier"]
    assert metadata["effective_dates"]
    assert metadata["pinpoint_citations"]
    for authority in metadata["legal_authority"]["sources"]:
        assert "jurisdiction" in authority
        assert "effective_date" in authority
        assert "source_tier" in authority
        assert "pinpoint_citation" in authority
        assert authority["can_support_legal_conclusion"] is False

    source = playbook["sources"]["P1"]
    assert "jurisdiction" in source
    assert "effective_date" in source
    assert "pinpoint_citation" in source
    assert source["pinpoint_citation"] is None
    assert source["can_support_legal_conclusion"] is False
    assert source["citation_status"] != "VERIFIED_PINPOINT"


def test_registry_has_more_than_one_thousand_disabled_candidates_not_fake_approved_rules():
    records = [
        json.loads(line)
        for line in (ROOT / "data/risk/rule_registry.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    base = [item for item in records if item["record_kind"] == "BASE_RULE"]
    candidates = [item for item in records if item["record_kind"] == "CONTEXT_VARIANT_CANDIDATE"]

    manifest = json.loads((ROOT / "data/risk/rule_registry_manifest.json").read_text(encoding="utf-8"))
    assert len(base) == manifest["base_rule_count"]
    assert len(candidates) == manifest["candidate_rule_count"]
    assert len(records) == manifest["total_rule_records"]
    assert len(candidates) == len(base) * manifest["candidate_profile_count"]
    assert len(candidates) >= 1000
    base_keys = {item["base_rule_key"] for item in base}
    assert all(item["base_rule_key"] in base_keys for item in candidates)
    assert all(item["execution_eligible"] is False for item in candidates)
    assert all(item["validation_status"] == "DRAFT_UNVALIDATED" for item in candidates)
    assert all(item["validation_status"] in {"DRAFT_UNVALIDATED", "IN_REVIEW", "ADJUDICATED", "APPROVED", "REJECTED"} for item in base)
    assert all(item["legal_conclusion_allowed"] is False for item in records)


def test_confidence_is_not_fabricated_without_a_calibration_artifact(tmp_path):
    result = confidence_from_support_score(
        0.91,
        playbook_hash="test-playbook",
        artifact_path=tmp_path / "missing.json",
    )
    assert result["confidence"] is None
    assert result["confidence_status"] == "UNCALIBRATED"
    assert result["confidence_target"] == "PREDICTION_CORRECTNESS"


def test_confidence_artifact_must_match_playbook_and_score_version(tmp_path):
    artifact_path = tmp_path / "confidence.json"
    artifact_path.write_text(json.dumps(_valid_artifact()), encoding="utf-8")

    valid = confidence_from_support_score(
        0.8,
        playbook_hash="playbook-A",
        artifact_path=artifact_path,
    )
    stale = confidence_from_support_score(
        0.8,
        playbook_hash="playbook-B",
        artifact_path=artifact_path,
    )

    assert valid["confidence"] is not None
    assert 0.0 <= valid["confidence"] <= 1.0
    assert valid["confidence_status"] == "CALIBRATED_PREDICTION_CORRECTNESS"
    assert valid["confidence_calibration_version"] == "test-calibration-v1"
    assert stale["confidence"] is None
    assert stale["confidence_status"] == "CALIBRATION_STALE_FOR_PLAYBOOK"


def test_confidence_artifact_status_string_alone_cannot_bypass_audit_gates(tmp_path):
    artifact_path = tmp_path / "confidence.json"
    artifact_path.write_text(
        json.dumps(_valid_artifact(locked_test_metrics={
            "brier_calibrated": 0.30,
            "brier_constant_prevalence_baseline": 0.25,
            "brier_improvement_ci_95": [-0.10, 0.01],
            "ece_10_bins": 0.20,
            "test_correct_count": 70,
            "test_incorrect_count": 30,
        })),
        encoding="utf-8",
    )
    result = confidence_from_support_score(
        0.8,
        playbook_hash="playbook-A",
        artifact_path=artifact_path,
    )
    assert result["confidence"] is None
    assert result["confidence_status"] == "CALIBRATION_AUDIT_GATES_FAILED"


def test_raw_support_feature_does_not_reward_yes_over_no():
    yes = _support_score(answer="YES", evidence_ok=True, agreement=0.8, indicator_match=True)
    no = _support_score(answer="NO", evidence_ok=True, agreement=0.8, indicator_match=True)
    unknown = _support_score(answer="DON'T KNOW", evidence_ok=True, agreement=1.0, indicator_match=True)

    assert yes == no
    assert 0.0 <= yes <= 1.0
    assert unknown == 0.0

def test_rule_schema_requires_independent_adjudication_before_approval():
    schema = json.loads((ROOT / "data/risk/rule_registry.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    records = [
        json.loads(line)
        for line in (ROOT / "data/risk/rule_registry.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    approved = next(item.copy() for item in records if item["record_kind"] == "BASE_RULE")
    approved.update({
        "validation_status": "APPROVED",
        "approval_status": "APPROVED",
        "execution_status": "APPROVED_FOR_EXECUTION",
        "execution_eligible": True,
        "review_governance": {
            "status": "APPROVED",
            "reviewer_ids": ["reviewer-a", "reviewer-b"],
            "reviewer_decisions": [
                {
                    "reviewer_id": "reviewer-a",
                    "decision": "POTENTIAL_RISK",
                    "rationale": "The cited clause appears to satisfy the test predicate.",
                    "reviewed_at": "2026-10-17T00:10:00Z"
                },
                {
                    "reviewer_id": "reviewer-b",
                    "decision": "INSUFFICIENT_EVIDENCE",
                    "rationale": "The available excerpt does not resolve the exception.",
                    "reviewed_at": "2026-10-17T00:15:00Z"
                }
            ],
            "adjudicator_id": "independent-adjudicator",
            "adjudication_reference": "ADJ-2026-001",
            "adjudicated_at": "2026-10-17T00:00:00Z",
            "approved_by": "policy-owner",
            "approved_at": "2026-10-17T00:30:00Z",
            "approval_basis": "Authority, scope, evidence and exception suite independently reviewed."
        }
    })
    assert validator.is_valid(approved)

    invalid = approved.copy()
    invalid.pop("review_governance")
    assert not validator.is_valid(invalid)

def test_source_registry_uses_verified_metadata_from_governed_playbook_input():
    source = {
        "citation": "Synthetic authority fixture for registry unit testing.",
        "source_url": "https://example.test/authority",
        "source_tier": "A",
        "authority_status": "BINDING_PRIMARY_AUTHORITY",
        "jurisdiction": "US-CA",
        "contract_type": "commercial_general",
        "effective_date": "2026-01-01",
        "effective_date_status": "VERIFIED",
        "pinpoint_citation": "Synthetic § 1, paragraph 2",
        "retrieval_date": "2026-10-17",
        "citation_status": "VERIFIED_PINPOINT",
        "license_status": "PUBLIC_DOMAIN",
        "transferability": "US-CA only",
        "can_support_legal_conclusion": True,
        "missing_metadata": [],
        "metadata_note": "Synthetic test data only."
    }
    registry = _source_registry({"sources": {"SYNTHETIC_TEST_SOURCE": source}})
    item = registry["sources"][0]

    assert registry["verified_pinpoint_source_count"] == 1
    assert registry["status"] == "ALL_PINPOINT_CITATIONS_VERIFIED"
    assert item["source_tier"] == "A"
    assert item["jurisdiction"] == "US-CA"
    assert item["pinpoint_citation"] == "Synthetic § 1, paragraph 2"
    assert item["retrieval_date"] == "2026-10-17"
    assert item["can_support_legal_conclusion"] is True

    source_without_retrieval_date = {**source, "retrieval_date": None}
    incomplete = _source_registry({"sources": {"SYNTHETIC_TEST_SOURCE": source_without_retrieval_date}})
    assert incomplete["verified_pinpoint_source_count"] == 0
    assert incomplete["status"] == "INCOMPLETE_SOURCE_CITATIONS"

def test_review_queue_covers_every_base_rule_and_surfaces_missing_case_suites():
    manifest = json.loads((ROOT / "data/risk/rule_registry_manifest.json").read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in (ROOT / "data/risk/rule_registry.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    base_ids = {
        item["rule_id"]
        for item in records
        if item["record_kind"] == "BASE_RULE"
    }
    with (ROOT / "data/risk/rule_review_queue.csv").open(encoding="utf-8", newline="") as handle:
        queue = list(csv.DictReader(handle))

    assert len(queue) == manifest["base_rule_count"]
    assert {row["rule_id"] for row in queue} == base_ids
    assert all(row["source_playbook_hash"] == manifest["source_playbook_hash"] for row in queue)
    incomplete = [row for row in queue if row["case_suite_status"] == "INCOMPLETE"]
    complete = [row for row in queue if row["case_suite_status"] == "COMPLETE"]
    expected_complete = sum(
        all((item.get("regression_cases") or {}).get(key) for key in ("positive", "negative", "edge"))
        for item in records
        if item["record_kind"] == "BASE_RULE"
    )
    assert len(complete) == expected_complete
    assert len(incomplete) == len(queue) - len(complete)
    assert all("AUTHOR_POSITIVE_NEGATIVE_EDGE_CASES" in row["next_action"] for row in incomplete)

def _approved_rule_fixture():
    records = [
        json.loads(line)
        for line in (ROOT / "data/risk/rule_registry.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rule = next(item.copy() for item in records if item["record_kind"] == "BASE_RULE")
    rule.update({
        "validation_status": "APPROVED",
        "approval_status": "APPROVED",
        "execution_status": "APPROVED_FOR_EXECUTION",
        "execution_eligible": True,
        "legal_conclusion_allowed": False,
        "jurisdiction_scope": ["US-CA"],
        "jurisdiction_status": "VERIFIED",
        "regression_cases": {
            "positive": [{"contract_text": "Synthetic positive case.", "expected": "POTENTIAL_RISK"}],
            "negative": [{"contract_text": "Synthetic protected control.", "expected": "NO_RISK"}],
            "edge": [{"contract_text": "Synthetic ambiguity case.", "expected": "INSUFFICIENT_EVIDENCE"}],
        },
        "legal_authority": {
            "sources": [{
                "source_id": "SYNTHETIC_TEST_SOURCE",
                "citation_status": "VERIFIED_PINPOINT",
                "pinpoint_citation": "Synthetic § 1, paragraph 2",
                "retrieval_date": "2026-10-17",
                "jurisdiction": "US-CA",
                "effective_date_status": "VERIFIED",
            }]
        },
        "review_governance": {
            "status": "APPROVED",
            "reviewer_ids": ["reviewer-a", "reviewer-b"],
            "reviewer_decisions": [
                {
                    "reviewer_id": "reviewer-a",
                    "decision": "POTENTIAL_RISK",
                    "rationale": "The trigger appears to match.",
                    "reviewed_at": "2026-10-17T00:10:00Z",
                },
                {
                    "reviewer_id": "reviewer-b",
                    "decision": "INSUFFICIENT_EVIDENCE",
                    "rationale": "The exception requires adjudication.",
                    "reviewed_at": "2026-10-17T00:15:00Z",
                },
            ],
            "adjudicator_id": "independent-adjudicator",
            "adjudication_reference": "ADJ-2026-001",
            "adjudicated_at": "2026-10-17T00:20:00Z",
            "approved_by": "policy-owner",
            "approved_at": "2026-10-17T00:30:00Z",
            "approval_basis": "Synthetic test fixture only.",
        },
    })
    return rule


def test_approval_lifecycle_rejects_rules_without_verified_scope_and_exception_cases():
    rule = _approved_rule_fixture()
    rule["jurisdiction_status"] = "UNRESOLVED"
    rule["jurisdiction_scope"] = ["UNSPECIFIED"]
    rule["regression_cases"] = {"positive": [], "negative": [], "edge": []}
    rule["legal_authority"] = {"sources": []}

    problems = _rule_lifecycle_problems(rule)
    assert any("approved_rule_missing_positive_negative_edge_tests" in item for item in problems)
    assert any("approved_rule_jurisdiction_not_verified" in item for item in problems)
    assert any("approved_rule_source_scope_not_verified" in item for item in problems)


def test_approval_lifecycle_accepts_a_fully_adjudicated_test_fixture():
    assert _rule_lifecycle_problems(_approved_rule_fixture()) == []

def test_global_playbook_approval_does_not_promote_unreviewed_rules():
    playbook = json.loads(PLAYBOOK_PATH.read_text(encoding="utf-8"))
    playbook["approval_status"] = "APPROVED"
    registry_text, _, manifest_text = build_artifacts(playbook)
    records = [json.loads(line) for line in registry_text.splitlines() if line.strip()]
    manifest = json.loads(manifest_text)
    base = [item for item in records if item["record_kind"] == "BASE_RULE"]
    candidates = [item for item in records if item["record_kind"] == "CONTEXT_VARIANT_CANDIDATE"]

    assert manifest["policy_status"] == "APPROVED"
    assert manifest["production_approved_rule_count"] == 0
    assert all(item["approval_status"] == "UNAPPROVED" for item in base)
    assert all(item["validation_status"] == "DRAFT_UNVALIDATED" for item in base)
    assert all(item["approval_status"] == "UNAPPROVED" for item in candidates)
    assert all(item["execution_eligible"] is False for item in candidates)

def test_generated_registry_embeds_authority_metadata_and_hashes_for_every_base_rule():
    manifest = json.loads((ROOT / "data/risk/rule_registry_manifest.json").read_text(encoding="utf-8"))
    clause_map = json.loads(AUTHORITY_MAP_PATH.read_text(encoding="utf-8"))
    catalog = json.loads(AUTHORITY_CATALOG_PATH.read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in (ROOT / "data/risk/rule_registry.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    base = [item for item in records if item["record_kind"] == "BASE_RULE"]
    candidates = [item for item in records if item["record_kind"] == "CONTEXT_VARIANT_CANDIDATE"]
    map_by_clause = {item["clause_type"]: item for item in clause_map["clauses"]}
    authority_by_id = {item["authority_id"]: item for item in catalog["authorities"]}

    assert manifest["authority_map_hash"] == _git_blob_sha(AUTHORITY_MAP_PATH.read_bytes())
    assert manifest["authority_catalog_hash"] == _git_blob_sha(AUTHORITY_CATALOG_PATH.read_bytes())
    assert manifest["authority_catalog_count"] == len(catalog["authorities"])
    assert manifest["mapped_clause_count"] == 37
    assert manifest["rule_authority_map_record_count"] == len(base) == 121
    assert all("authority_map" in item for item in base)
    assert all("authority_map" in item["inherited_fields"] for item in candidates)

    for rule in base:
        mapped = rule["authority_map"]
        assert rule["legal_conclusion_allowed"] is False
        assert mapped["review_status"] == "RESEARCH_SEED_NOT_LEGALLY_APPROVED"
        if rule.get("clause_type") in map_by_clause:
            expected = map_by_clause[rule["clause_type"]]
            assert mapped["clause_type"] == expected["clause_type"]
            assert mapped["authority_ids"] == expected["authority_ids"]
            assert mapped["authority_coverage_status"] == expected["authority_coverage_status"]
        else:
            assert mapped["clause_type"] is None
            assert mapped["authority_coverage_status"] == "RULE_FAMILY_SPECIFIC_AUTHORITY_REVIEW_REQUIRED"
        assert [source["authority_id"] for source in mapped["authority_sources"]] == mapped["authority_ids"]
        for source in mapped["authority_sources"]:
            catalog_source = authority_by_id[source["authority_id"]]
            assert source["url"] == catalog_source["url"]
            assert source["pinpoint"] == catalog_source["pinpoint"]
            assert source["jurisdiction"] == catalog_source["jurisdiction"]
            assert source["source_tier"] == catalog_source["source_tier"]
            assert source["effective_date_status"] == catalog_source["effective_date_status"]
            assert source["retrieval_date"] == catalog_source["retrieval_date"]
