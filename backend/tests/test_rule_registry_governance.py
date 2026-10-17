import json
from pathlib import Path

from app.core.risk.confidence_calibration import (
    SUPPORT_SCORE_VERSION,
    confidence_from_support_score,
)
from app.core.risk.risk_playbook import load_playbook
from app.core.risk.risk_engine import _support_score

ROOT = Path(__file__).resolve().parents[2]


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

    assert registry["status"] == "PILOT_REVIEW_ONLY"
    assert registry["base_rule_count"] == 121
    assert registry["candidate_rule_count"] == 1936
    assert registry["production_approved_rule_count"] == 0
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

    assert len(base) == 121
    assert len(candidates) == 1936
    assert len(records) == 2057
    base_keys = {item["base_rule_key"] for item in base}
    assert all(item["base_rule_key"] in base_keys for item in candidates)
    assert all(item["execution_eligible"] is False for item in candidates)
    assert all(item["validation_status"] == "DRAFT_UNVALIDATED" for item in records)
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
