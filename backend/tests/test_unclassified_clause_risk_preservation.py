from app.services.rag_service import _preserve_risk_findings_for_unclassified_clause


def test_unclassified_clause_keeps_positive_risk_finding():
    clause = {
        "clause_index": 1,
        "classification_status": "NO_APPLICABLE_LABEL",
        "risk_status": "NOT_ANALYZED",
        "risk": False,
        "risk_findings": [{
            "check_id": "OPEN-RISK-1",
            "risk_status": "POTENTIAL_RISK",
            "risk": True,
            "evidence": "exact clause text",
        }],
    }
    result = _preserve_risk_findings_for_unclassified_clause(clause)
    assert result["classification_status"] == "NO_APPLICABLE_LABEL"
    assert len(result["risk_findings"]) == 1
    assert result["risk_status"] == "POTENTIAL_RISK"
    assert result["risk"] is True


def test_unclassified_clause_keeps_unresolved_status_instead_of_becoming_no_risk():
    clause = {
        "classification_status": "NO_APPLICABLE_LABEL",
        "risk_findings": [{"check_id": "OPEN-RISK-1", "risk_status": "INSUFFICIENT_EVIDENCE", "risk": False}],
    }
    result = _preserve_risk_findings_for_unclassified_clause(clause)
    assert result["risk_findings"] == clause["risk_findings"]
    assert result["risk_status"] == "INSUFFICIENT_EVIDENCE"


def test_classified_clause_is_not_changed():
    clause = {"classification_status": "Insurance", "risk_findings": []}
    assert _preserve_risk_findings_for_unclassified_clause(clause) is clause

