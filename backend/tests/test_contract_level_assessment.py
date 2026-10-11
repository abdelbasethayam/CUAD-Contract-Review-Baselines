from __future__ import annotations

from app.core.risk.contract_risk_engine import aggregate_clause_risks


def _finding(**overrides):
    finding = {
        "clause_index": 1,
        "clause_text": "Supplier liability is unlimited.",
        "predicted_label": "Uncapped Liability",
        "classification_status": "VALID_CANDIDATE",
        "classification_confidence": 0.91,
        "check_id": "UNC-1",
        "risk_domain": "Liability Risk",
        "risk_subdomain": "Uncapped Monetary Exposure",
        "risk_status": "POTENTIAL_RISK",
        "risk": True,
        "risk_type": "Uncapped Liability",
        "risk_level": "HIGH",
        "severity": "HIGH",
        "severity_score": 18.0,
        "final_score": 18,
        "raw_support_score": 0.9,
        "score_components": {
            "exposure_magnitude": 5,
            "likelihood_uncertainty": 4,
            "scope_duration": 5,
            "control_weakness": 4,
        },
        "evidence": "Supplier liability is unlimited.",
        "why_flagged": "The clause expressly states unlimited liability.",
        "related_contract_context": [],
        "provenance": {"check_id": "UNC-1", "playbook_hash": "test-playbook"},
    }
    finding.update(overrides)
    return finding


def test_contract_aggregation_summarizes_validated_clause_evidence():
    playbook = {
        "clause_types": {
            "Uncapped Liability": {
                "checklist": [
                    {
                        "id": "UNC-1",
                        "risk_domain": "Liability Risk",
                        "risk_subdomain": "Uncapped Monetary Exposure",
                        "question": "Is liability uncapped?",
                    }
                ]
            }
        },
        "cross_clause_checks": [],
        "document_level_checks": [],
    }

    result = aggregate_clause_risks([_finding()], playbook=playbook)

    assert result["status"] == "POTENTIAL_RISK"
    assert result["overall_risk"] == "CRITICAL"
    assert result["affected_clauses"] == [1]
    assert result["risk_domains"][0]["domain"] == "Liability Risk"
    assert result["key_risks"][0]["evidence"] == "Supplier liability is unlimited."
    assert result["key_risks"][0]["risk_subdomain"] == "Uncapped Monetary Exposure"


def test_unresolved_findings_remain_insufficient_evidence_not_no_risk():
    result = aggregate_clause_risks(
        [
            _finding(
                risk=False,
                risk_status="INSUFFICIENT_EVIDENCE",
                evidence="",
                risk_level=None,
                severity=None,
                final_score=None,
                why_flagged="The relevant limitation and carve-outs could not be located.",
            )
        ],
        playbook={"clause_types": {}, "cross_clause_checks": [], "document_level_checks": []},
    )

    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["overall_risk"] is None
    assert result["unresolved_check_count"] == 1


def test_malformed_or_missing_model_result_does_not_create_a_positive_finding():
    # A missing result is represented explicitly by the risk engine as unresolved.
    result = aggregate_clause_risks(
        [
            _finding(
                risk=False,
                risk_status="INSUFFICIENT_EVIDENCE",
                evidence="",
                risk_level=None,
                severity=None,
                final_score=None,
                why_flagged="No usable model answer was returned.",
            )
        ],
        playbook={"clause_types": {}, "cross_clause_checks": [], "document_level_checks": []},
    )

    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["key_risks"] == []


def test_no_applicable_label_does_not_create_a_contract_risk():
    result = aggregate_clause_risks(
        [
            {
                "clause_index": 0,
                "clause_text": "Signature page",
                "predicted_label": "NO_APPLICABLE_LABEL",
                "risk": False,
                "risk_status": "NO_RISK",
                "evidence": "",
            }
        ],
        playbook={"clause_types": {}, "cross_clause_checks": [], "document_level_checks": []},
    )

    assert result["status"] == "NO_RISK"
    assert result["overall_risk"] is None
    assert result["key_risks"] == []
