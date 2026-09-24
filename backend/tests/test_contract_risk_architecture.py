import json

from app.core.risk import aggregator, risk_detector
from app.core.risk.knowledge_base import match_risk_domains
from app.models.schemas import ContractClassificationResponse


def _positive_finding(**overrides):
    finding = {
        "clause_index": 0,
        "clause_text": "Liability is unlimited.",
        "predicted_label": "Insurance",
        "classification_status": "VALID_CANDIDATE",
        "risk": True,
        "risk_status": "POTENTIAL_RISK",
        "risk_type": "Uncapped Liability",
        "risk_level": None,
        "risk_domains": ["Liability Risk"],
        "reason": "The clause creates uncapped exposure.",
        "evidence": "Liability is unlimited.",
        "legal_knowledge": [],
        "related_contract_context": [],
    }
    finding.update(overrides)
    return finding


def test_unknown_classification_still_runs_risk_analysis(monkeypatch):
    calls = []
    monkeypatch.setattr(risk_detector, "retrieve_legal_guidance", lambda *args, **kwargs: [])

    def fake_openrouter(prompt):
        calls.append(prompt)
        return json.dumps(
            {
                "risk_status": "POTENTIAL_RISK",
                "risk_type": "Uncapped Liability",
                "risk_level": "HIGH",
                "reason": "The clause creates uncapped exposure.",
                "evidence": "Liability is unlimited.",
            }
        )

    monkeypatch.setattr(risk_detector, "call_ollama", fake_openrouter)
    result = risk_detector.detect_clause_risk(
        "Liability is unlimited.",
        "UNKNOWN",
        classification_status="UNKNOWN",
    )

    assert calls
    assert result["risk_status"] == "POTENTIAL_RISK"
    assert result["evidence"] == "Liability is unlimited."


def test_malformed_classification_status_does_not_skip_risk_analysis(monkeypatch):
    monkeypatch.setattr(risk_detector, "retrieve_legal_guidance", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        risk_detector,
        "call_ollama",
        lambda prompt: '{"risk_status":"POTENTIAL_RISK","risk_type":"Insurance gap","reason":"Review the coverage.","evidence":"The supplier shall maintain insurance."}',
    )

    result = risk_detector.detect_clause_risk(
        "The supplier shall maintain insurance.",
        "UNKNOWN",
        classification_status="MALFORMED_RESPONSE",
    )

    assert result["risk_status"] == "POTENTIAL_RISK"


def test_risk_taxonomy_is_independent_of_cuad_label():
    matches = match_risk_domains(
        "The supplier shall indemnify and hold harmless the customer.",
        "UNKNOWN",
    )

    assert any(item["risk_domain"] == "Liability Risk" for item in matches)


def test_multiple_clause_findings_are_aggregated_without_score_averaging():
    findings = [
        _positive_finding(),
        _positive_finding(
            clause_index=1,
            clause_text="Supplier shall indemnify Customer for third-party claims.",
            risk_type="Indemnification",
            risk_domains=["Liability Risk", "Financial Risk"],
            evidence="Supplier shall indemnify Customer for third-party claims.",
        ),
    ]

    assessment = aggregator.aggregate_contract_risk(findings, use_llm=False)

    assert assessment["overall_status"] == "POTENTIAL_RISK"
    assert assessment["overall_risk"] == "HIGH"
    assert assessment["affected_clauses"] == [0, 1]
    assert len(assessment["supporting_clause_findings"]) == 2
    assert "score" not in assessment


def test_aggregator_rejects_legal_guidance_as_contract_evidence():
    finding = _positive_finding(
        clause_text="The parties will review this provision annually.",
        evidence="Review uncapped liability wording.",
        legal_knowledge=[
            {"retrieved_text": "Review uncapped liability wording."},
        ],
    )

    assessment = aggregator.aggregate_contract_risk([finding], use_llm=False)

    assert assessment["overall_status"] == "NO_RISK"
    assert assessment["evidence"] == []


def test_aggregator_rejects_cuad_example_as_contract_evidence():
    finding = _positive_finding(
        clause_text="The customer may request a quarterly report.",
        evidence="Liability is unlimited.",
        retrieved_examples=[{"clause_text": "Liability is unlimited."}],
    )

    assessment = aggregator.aggregate_contract_risk([finding], use_llm=False)

    assert assessment["overall_status"] == "NO_RISK"
    assert assessment["evidence"] == []


def test_exact_related_contract_context_can_support_a_finding():
    finding = _positive_finding(
        clause_text="The customer may request a quarterly report.",
        evidence="Liability is unlimited.",
        related_contract_context=[{"clause_text": "Liability is unlimited."}],
    )

    assessment = aggregator.aggregate_contract_risk([finding], use_llm=False)

    assert assessment["overall_status"] == "POTENTIAL_RISK"
    assert assessment["evidence"][0]["text"] == "Liability is unlimited."


def test_insufficient_evidence_is_preserved_when_no_positive_finding_exists():
    assessment = aggregator.aggregate_contract_risk(
        [{
            "clause_index": 0,
            "clause_text": "The clause is ordinary.",
            "risk": False,
            "risk_status": "INSUFFICIENT_EVIDENCE",
            "reason": "No exact evidence was available.",
        }],
        use_llm=False,
    )

    assert assessment["overall_status"] == "INSUFFICIENT_EVIDENCE"
    assert assessment["overall_risk"] is None


def test_openrouter_can_safely_synthesize_contract_assessment(monkeypatch):
    monkeypatch.setattr(
        aggregator,
        "call_ollama",
        lambda prompt: json.dumps(
            {
                "overall_risk": "LOW",
                "reason": "The validated finding is limited in scope.",
                "recommendations": ["Review the liability wording."],
            }
        ),
    )

    assessment = aggregator.aggregate_contract_risk([_positive_finding()])

    assert assessment["synthesis_provider"] == "ollama"
    assert assessment["overall_risk"] == "LOW"
    assert assessment["evidence"][0]["text"] == "Liability is unlimited."


def test_api_response_exposes_contract_assessment_and_clause_findings():
    response = ContractClassificationResponse(
        filename="contract.txt",
        total_clauses=1,
        clauses=[
            {
                "clause_index": 0,
                "clause_text": "Liability is unlimited.",
                "predicted_label": "Insurance",
                "risk_status": "POTENTIAL_RISK",
                "risk": True,
                "risk_type": "Uncapped Liability",
                "evidence": "Liability is unlimited.",
            }
        ],
        contract_risk_assessment={
            "overall_status": "POTENTIAL_RISK",
            "overall_risk": "HIGH",
            "affected_clauses": [0],
        },
    )

    payload = response.model_dump() if hasattr(response, "model_dump") else response.dict()
    assert payload["contract_risk_assessment"]["overall_risk"] == "HIGH"
    assert "evidence" not in payload["clauses"][0]
