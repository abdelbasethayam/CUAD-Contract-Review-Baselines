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
    cross_checks = _read("backend/app/core/risk/contract_checks.py")
    config = _read("backend/app/core/config.py")
    for name, module in (("risk_engine", source), ("contract_checks", cross_checks)):
        assert "load_calibration" not in module, name
        assert "calibrate_risk_probability" not in module, name
        assert "calibrate_severity" not in module, name
        assert '"confidence_status": "CALIBRATED"' not in module, name
        assert '"severity_status": "CALIBRATED"' not in module, name
    assert "RISK_CALIBRATION_PATH" not in config
    assert "RISK_GOLD_PATH" not in config
    assert '"confidence_status": "UNCALIBRATED"' in source
    assert '"confidence_status": "UNCALIBRATED"' in cross_checks
    assert not (ROOT / "backend/app/core/risk/calibration.py").exists()
    assert not (ROOT / "scripts/risk/fit_calibration.py").exists()


def test_retired_annotation_queue_tools_and_inputs_are_not_in_release_tree():
    retired_paths = [
        "scripts/risk/build_absence_gold_queue.py",
        "scripts/risk/build_gold_queue.py",
        "scripts/risk/build_silver_queue.py",
        "scripts/risk/run_gold_evaluation.py",
        "scripts/risk/run_silver_adjudication.py",
        "scripts/risk/validate_gold_queue.py",
        "data/risk/gold/annotation_queue.csv",
        "data/risk/gold/gold_annotations.csv",
        "data/risk/silver/silver_queue.csv",
        "data/risk/silver/silver_annotations_final_v5_qwen3_gemma3_20261007.csv",
        "docs/PHASE2_NO_GOLD_EVALUATION_PROTOCOL.md",
        "data/risk/GOLD_STATUS.md",
    ]
    existing = [relative for relative in retired_paths if (ROOT / relative).exists()]
    assert existing == [], f"Retired annotation workflow is still present: {existing}"



def test_run_fingerprint_captures_risk_generation_settings(monkeypatch):
    from app.services import rag_service

    monkeypatch.setattr(rag_service, "_code_fingerprint", lambda: "test-code-fingerprint")
    monkeypatch.setattr(rag_service, "RISK_TEMPERATURE", 0.17)
    monkeypatch.setattr(rag_service, "RISK_MAX_TOKENS", 2345)
    monkeypatch.setattr(rag_service, "RISK_NUM_CTX", 12288)
    monkeypatch.setattr(rag_service, "LEGAL_KNOWLEDGE_TOP_K", 6)

    config = rag_service._pipeline_config(12, {"playbook_hash": "test-playbook"})

    assert config["code_fingerprint"] == "test-code-fingerprint"
    assert config["risk_temperature"] == 0.17
    assert config["risk_max_tokens"] == 2345
    assert config["risk_num_ctx"] == 12288
    assert config["legal_knowledge_top_k"] == 6



def test_run_resumption_expects_text_retrieved_check_families():
    source = _read("backend/app/services/rag_service.py")
    assert "for check in applicable_checks(" in source
    assert 'clause_text=str(item.get("clause_text") or "")' in source



def test_clause_text_retrieves_relevant_checks_beyond_the_predicted_label():
    from app.core.risk.risk_playbook import applicable_checks, load_playbook

    playbook = load_playbook()
    clause_text = "Supplier liability shall not exceed fees paid in the prior month."
    checks = applicable_checks(playbook, "Insurance", clause_text=clause_text)
    check_ids = {str(check["id"]) for check in checks}
    cap_ids = {
        str(check["id"])
        for check in playbook["clause_types"]["Cap On Liability"]["checklist"]
    }
    audit_ids = {
        str(check["id"])
        for check in playbook["clause_types"]["Audit Rights"]["checklist"]
    }

    assert cap_ids.issubset(check_ids)
    assert audit_ids.isdisjoint(check_ids)


def test_clause_checkpoint_retries_missing_model_passes():
    from app.services.rag_service import _clause_risk_checkpoint_is_complete

    expected = {"C-1"}
    complete = [{
        "check_id": "C-1",
        "provenance": {
            "rule_engine_version": "playbook-rules-1.0",
            "playbook_hash": "p1",
            "missing_passes": 0,
        },
    }]
    incomplete = [{
        "check_id": "C-1",
        "provenance": {
            "rule_engine_version": "playbook-rules-1.0",
            "playbook_hash": "p1",
            "missing_passes": 1,
        },
    }]

    assert _clause_risk_checkpoint_is_complete(complete, expected, "p1") is True
    assert _clause_risk_checkpoint_is_complete(incomplete, expected, "p1") is False


def test_contract_check_checkpoint_retries_incomplete_model_passes():
    from app.services.rag_service import _contract_checks_checkpoint_is_complete

    playbook = {
        "playbook_hash": "p1",
        "cross_clause_checks": [{"id": "X-1"}],
        "document_level_checks": [{"id": "DOC-1"}],
    }
    payload = {
        "playbook_hash": "p1",
        "model": "test-model",
        "cross_clause_enabled": True,
        "document_checks_enabled": True,
        "cross_clause_findings": [{"check_id": "X-1", "provenance": {"missing_passes": 0}}],
        "document_findings": [{"check_id": "DOC-1", "provenance": {"missing_passes": 0}}],
    }

    assert _contract_checks_checkpoint_is_complete(
        payload, playbook, model="test-model",
        cross_clause_enabled=True, document_checks_enabled=True,
    ) is True

    payload["cross_clause_findings"][0]["provenance"]["missing_passes"] = 1
    assert _contract_checks_checkpoint_is_complete(
        payload, playbook, model="test-model",
        cross_clause_enabled=True, document_checks_enabled=True,
    ) is False



def test_csv_exports_nested_evidence_and_citations_as_json():
    import json
    from app.services.rag_service import _csv_safe_rows

    source_row = {
        "evidence": [{"clause_id": 4, "quote": "Liability is capped."}],
        "supporting_sources": [{"id": "P2", "source_title": "Practice note"}],
        "provenance": {"score_interpretation": "triage only"},
    }

    row = _csv_safe_rows([source_row])[0]

    assert json.loads(row["evidence"]) == source_row["evidence"]
    assert json.loads(row["supporting_sources"]) == source_row["supporting_sources"]
    assert json.loads(row["provenance"]) == source_row["provenance"]
