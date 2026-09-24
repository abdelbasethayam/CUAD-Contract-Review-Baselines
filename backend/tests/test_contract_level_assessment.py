from __future__ import annotations

import json

from app.core.risk import contract_assessor


def _clauses():
    return [
        {
            "clause_index": 1,
            "clause_text": "Supplier liability is unlimited.",
            "predicted_label": "Uncapped Liability",
            "classification_status": "VALID_CANDIDATE",
            "classification_confidence": 0.91,
            "retrieved_examples": [{"clause_type": "Uncapped Liability", "score": 0.91, "clause_text": "Liability is unlimited."}],
        },
        {
            "clause_index": 2,
            "clause_text": "Supplier shall maintain insurance.",
            "predicted_label": "Insurance",
            "classification_status": "VALID_CANDIDATE",
            "classification_confidence": 0.82,
            "retrieved_examples": [],
        },
    ]


def test_contract_risk_model_is_called_once_for_multiple_clauses(monkeypatch):
    calls = []
    monkeypatch.setattr(contract_assessor, "retrieve_contract_guidance", lambda *args, **kwargs: [])

    def fake_model(prompt):
        calls.append(prompt)
        return json.dumps({
            "overall_risk": "HIGH",
            "summary": "Uncapped exposure is stated in the contract.",
            "risk_domains": [{
                "domain": "Liability",
                "severity": "HIGH",
                "title": "Uncapped liability",
                "description": "The supplier liability is not limited.",
                "evidence": [{"clause_id": 1, "quote": "Supplier liability is unlimited."}],
                "impact": "Potentially broad financial exposure.",
                "likelihood": "MEDIUM",
                "exposure": "Uncapped",
                "reasoning": "The wording expressly states unlimited liability.",
                "recommendation": "Review a negotiated cap and carve-outs.",
            }],
            "positive_protections": [],
            "missing_protections": [],
            "cross_clause_findings": [],
            "limitations": [],
        })

    monkeypatch.setattr(contract_assessor, "call_ollama", lambda prompt, **kwargs: fake_model(prompt))
    result = contract_assessor.assess_contract_risk(_clauses())

    assert len(calls) == 1
    assert result["status"] == "COMPLETED"
    assert result["risk_domains"][0]["evidence"][0]["clause_id"] == 1


def test_malformed_risk_output_is_unavailable_not_no_risk(monkeypatch):
    monkeypatch.setattr(contract_assessor, "retrieve_contract_guidance", lambda *args, **kwargs: [])
    calls = []
    monkeypatch.setattr(
        contract_assessor,
        "call_ollama",
        lambda prompt, **kwargs: (calls.append(prompt) or "not json"),
    )

    result = contract_assessor.assess_contract_risk(_clauses())

    assert result["status"] == "RISK_ANALYSIS_UNAVAILABLE"
    assert result["overall_risk"] is None
    assert len(calls) == 1


def test_unsupported_risk_schema_is_unavailable_after_one_call(monkeypatch):
    monkeypatch.setattr(contract_assessor, "retrieve_contract_guidance", lambda *args, **kwargs: [])
    calls = []
    monkeypatch.setattr(
        contract_assessor,
        "call_ollama",
        lambda prompt, **kwargs: (calls.append(prompt) or '{"overall_risk":"HIGH","summary":"Missing required fields."}'),
    )

    result = contract_assessor.assess_contract_risk(_clauses())

    assert result["status"] == "RISK_ANALYSIS_UNAVAILABLE"
    assert len(calls) == 1


def test_evidence_aggregation_keeps_no_applicable_label_explicit():
    evidence = contract_assessor.build_contract_evidence([
        {"clause_index": 0, "clause_text": "Signature page", "predicted_label": "NO_APPLICABLE_LABEL"}
    ])
    assert evidence["classified_clauses"][0]["label"] == "NO_APPLICABLE_LABEL"
