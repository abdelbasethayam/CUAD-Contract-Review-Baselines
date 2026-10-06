from backend.app.core.risk.evidence_policy import legal_claim_supported, source_is_eligible
from backend.app.core.risk.risk_scoring import (
    aggregate_contract_triage,
    default_severity,
    is_jurisdiction_sensitive,
    score_finding,
)


def test_score_uses_four_0_to_5_dimensions():
    finding = {
        "score_components": {
            "exposure_magnitude": 5,
            "likelihood_uncertainty": 5,
            "scope_duration": 5,
            "control_weakness": 5,
        },
        "risk_type": "Uncapped Liability",
    }
    scored = score_finding(finding)
    assert scored["base_score"] == 20
    assert scored["final_score"] == 20
    assert scored["severity"] == "CRITICAL"


def test_score_band_mapping():
    assert default_severity(0) == "INFORMATIONAL"
    assert default_severity(4) == "LOW"
    assert default_severity(8) == "MEDIUM"
    assert default_severity(12) == "HIGH"
    assert default_severity(16) == "CRITICAL"


def test_jurisdiction_modifier_is_controlled():
    assert not is_jurisdiction_sensitive({"risk_type": "Liquidated Damages Exposure"})
    assert is_jurisdiction_sensitive({"risk_type": "Non-Compete"})


def test_control_modifier_requires_verified_cap_and_remedy():
    finding = {
        "score_components": {
            "exposure_magnitude": 3,
            "likelihood_uncertainty": 3,
            "scope_duration": 3,
            "control_weakness": 3,
        },
    }
    without_control = score_finding(finding)
    with_control = score_finding(
        finding,
        clear_bounded_control=True,
    )
    assert without_control["final_score"] == 12
    assert with_control["final_score"] == 10


def test_missing_score_component_abstains_from_severity():
    scored = score_finding(
        {
            "score_components": {
                "exposure_magnitude": 3,
                "likelihood_uncertainty": None,
                "scope_duration": 3,
                "control_weakness": 3,
            }
        }
    )
    assert scored["final_score"] is None
    assert scored["human_review_required"] is True
    assert scored["severity"] is None


def test_low_extraction_confidence_is_a_recorded_modifier():
    scored = score_finding(
        {
            "score_components": {
                "exposure_magnitude": 2,
                "likelihood_uncertainty": 2,
                "scope_duration": 2,
                "control_weakness": 2,
            }
        },
        extraction_confidence=0.70,
    )
    assert scored["modifier_total"] == 1
    assert scored["final_score"] == 9


def test_source_tier_policy_blocks_professional_practice_as_law():
    practice = {
        "source_tier": "B",
        "authority_status": "NON_BINDING_GUIDANCE",
        "jurisdiction": "US",
        "contract_type": "commercial_general",
    }
    authority = {
        "source_tier": "A",
        "authority_status": "COURT",
        "jurisdiction": "US",
        "contract_type": "commercial_general",
    }
    assert not source_is_eligible(practice, claim_kind="legal_conclusion", jurisdiction="US")
    assert source_is_eligible(authority, claim_kind="legal_conclusion", jurisdiction="US")
    assert not legal_claim_supported(
        "This provision is unenforceable.",
        [practice],
        jurisdiction="US",
    )
    assert legal_claim_supported(
        "This provision is unenforceable.",
        [authority],
        jurisdiction="US",
    )


def test_contract_triage_reports_concentration_and_escalation():
    findings = [
        {
            "risk_status": "POTENTIAL_RISK",
            "risk": True,
            "final_score": 12,
            "severity": "HIGH",
            "score_components": {"control_weakness": 4},
            "risk_domains": ["Liability Risk"],
        },
        {
            "risk_status": "POTENTIAL_RISK",
            "risk": True,
            "final_score": 12,
            "severity": "HIGH",
            "score_components": {"control_weakness": 4},
            "risk_domains": ["Liability Risk"],
        },
    ]
    result = aggregate_contract_triage(findings)
    assert result["exposure_concentration"]
    assert result["legal_review_required"] is True
    assert result["two_high_same_domain"] is True
