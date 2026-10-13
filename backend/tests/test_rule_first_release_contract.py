from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_active_risk_and_release_paths_do_not_consume_risk_annotation_queues():
    paths = {
        "risk_prompt_engine": "backend/app/core/risk/risk_engine.py",
        "legacy_risk_detector": "backend/app/core/risk/risk_detector.py",
        "run_service": "backend/app/services/rag_service.py",
        "release_checks": "scripts/risk/run_release_checks.py",
        "integrity_validator": "scripts/risk/validate_evaluation_integrity.py",
        "phase2_report": "scripts/risk/report_phase2_experiment.py",
        "release_package": "scripts/risk/package_phase2_release.py",
    }
    forbidden_references = (
        "gold_annotations.csv",
        "silver_annotations_final_v5",
        "silver_queue.csv",
        "gold/annotation_queue.csv",
        "GOLD_STATUS.md",
    )
    for name, relative_path in paths.items():
        source = _read(relative_path)
        for token in forbidden_references:
            assert token not in source, f"{name} still references {token}"


def test_release_gate_includes_playbook_rule_validator():
    release = _read("scripts/risk/run_release_checks.py")
    assert "scripts/risk/validate_playbook_rules.py" in release
    assert "scripts/risk/validate_evaluation_integrity.py" in release
    report = _read("scripts/risk/report_phase2_experiment.py")
    assert '"evaluation_mode": "PLAYBOOK_RULE_CONFORMANCE"' in report
    assert '"annotation_datasets_read": False' in report
    assert '"risk_text_span_dataset_used_for_flagging": False' in report


def test_rule_resume_freshness_uses_playbook_hash_and_engine_version():
    source = _read("backend/app/services/rag_service.py")
    assert 'get("rule_engine_version") == RULE_ENGINE_VERSION' in source
    assert 'get("playbook_hash") == playbook.get("playbook_hash")' in source


def test_active_risk_engine_does_not_load_calibration_artifacts():
    source = _read("backend/app/core/risk/risk_engine.py")
    assert "load_calibration" not in source
    assert "calibrate_risk_probability" not in source
    assert "calibrate_severity" not in source
    assert '"confidence_status": "UNCALIBRATED"' in source
