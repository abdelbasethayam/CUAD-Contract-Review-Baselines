import json

from app.core.risk import contract_checks, risk_engine
from app.core.risk.risk_engine import _evidence_source, _evidence_valid, _majority, _parse


def test_missing_model_passes_count_as_abstentions():
    records = [
        {"answer": "YES"},
        {"answer": "YES"},
    ]

    answer, agreement = _majority(records, expected_passes=3)

    assert answer == "YES"
    assert agreement == 0.6667


def test_missing_model_passes_prevent_false_majority():
    records = [{"answer": "YES"}]

    answer, agreement = _majority(records, expected_passes=3)

    assert answer == "DON'T KNOW"
    assert agreement == 0.3333


def test_evidence_source_is_ambiguous_when_quote_occurs_in_multiple_context_clauses():
    context = [
        {"clause_index": 4, "clause_text": "The supplier shall maintain insurance coverage."},
        {"clause_index": 7, "clause_text": "The supplier shall maintain insurance coverage."},
    ]

    source = _evidence_source(
        "The supplier shall maintain insurance coverage.",
        "Insurance requirements apply.",
        1,
        context,
    )

    assert source["evidence_source_status"] == "AMBIGUOUS"
    assert source["evidence_clause_index"] is None
    assert source["evidence_clause_candidates"] == [4, 7]


def test_evidence_source_reports_verified_target_clause():
    source = _evidence_source(
        "Liability is unlimited.",
        "Liability is unlimited.",
        3,
        [{"clause_index": 4, "clause_text": "Liability is unlimited."}],
    )

    assert source["evidence_source_status"] == "VERIFIED"
    assert source["evidence_clause_index"] == 3


def test_cross_clause_finding_abstains_when_evidence_clause_is_not_declared(monkeypatch):
    playbook = {
        "playbook_hash": "test-playbook",
        "sources": {},
        "cross_clause_checks": [{
            "id": "X-1",
            "question": "Does the agreement create a cross-clause risk?",
            "sources": [],
        }],
        "document_level_checks": [],
    }
    clauses = [
        {"clause_index": 1, "predicted_label": "Liability", "clause_text": "Liability is unlimited."},
        {"clause_index": 2, "predicted_label": "Indemnity", "clause_text": "Supplier indemnifies Customer."},
    ]
    response = {
        "cross_clause_findings": [{
            "check_id": "X-1",
            "answer": "YES",
            "status": "POTENTIAL_RISK",
            "risk_type": "Cross-clause exposure",
            "clause_ids": [1],
            "evidence": [{"clause_id": 2, "quote": "Supplier indemnifies Customer."}],
            "why_flagged": "Synthetic test.",
            "score_components": {},
        }],
        "document_findings": [],
    }
    monkeypatch.setattr(contract_checks, "call_ollama", lambda *args, **kwargs: json.dumps(response))

    cross, _ = contract_checks.analyze_contract_checks(
        clauses,
        playbook=playbook,
        passes=1,
    )

    finding = next(item for item in cross if item["check_id"] == "X-1")
    assert finding["risk_status"] == "INSUFFICIENT_EVIDENCE"
    assert {item["clause_id"] for item in finding["evidence"]} == {1, 2}
    assert all(item["quote"] in {clause["clause_text"] for clause in clauses} for item in finding["evidence"])



def test_duplicate_clause_check_ids_are_rejected_not_counted_as_votes():
    raw = json.dumps({
        "checks": [
            {"check_id": "C-1", "answer": "YES", "status": "POTENTIAL_RISK", "evidence": "exact quote"},
            {"check_id": "C-1", "answer": "NO", "status": "NO_RISK", "evidence": ""},
        ]
    })

    assert _parse(raw, {"C-1"}) == []


def test_duplicate_cross_clause_check_ids_are_rejected():
    raw = json.dumps({
        "cross_clause_findings": [
            {"check_id": "X-1", "answer": "YES", "clause_ids": [1], "evidence": []},
            {"check_id": "X-1", "answer": "NO", "clause_ids": [1], "evidence": []},
        ],
        "document_findings": [],
    })

    cross, document = contract_checks._parse(raw, {"X-1"}, set())

    assert cross == []
    assert document == []


def test_failed_clause_model_calls_leave_explicit_unresolved_check(monkeypatch):
    playbook = {
        "playbook_hash": "synthetic-playbook",
        "sources": {},
        "clause_types": {
            "General": {
                "checklist": [{
                    "id": "C-1",
                    "question": "Does this clause create a material customer exposure?",
                    "flag_if": "Yes, supported by exact contract wording",
                    "sources": [],
                    "risk_domain": "Commercial Risk",
                }]
            }
        },
        "deterministic_rules": [],
    }

    def fail_call(*args, **kwargs):
        raise RuntimeError("synthetic provider outage")

    monkeypatch.setattr(risk_engine, "call_ollama", fail_call)
    monkeypatch.setattr(risk_engine, "retrieve_legal_guidance", lambda *args, **kwargs: [])

    findings = risk_engine.analyze_clause_risk(
        clause_index=1,
        clause_text="The parties will cooperate on service delivery.",
        clause_type="General",
        query_vector=None,
        contract_clauses=[],
        playbook=playbook,
        passes=2,
    )

    finding = next(item for item in findings if item["check_id"] == "C-1")
    assert finding["risk_status"] == "INSUFFICIENT_EVIDENCE"
    assert finding["risk"] is False
    assert finding["provenance"]["passes"] == 0
    assert finding["provenance"]["expected_passes"] == 2
    assert finding["provenance"]["missing_passes"] == 2
    assert finding["severity"] is None


def test_cross_clause_positive_requires_evidence_for_every_declared_clause(monkeypatch):
    playbook = {
        "playbook_hash": "test-playbook",
        "sources": {},
        "cross_clause_checks": [{
            "id": "X-1",
            "question": "Do these clauses interact to create a risk?",
            "sources": [],
        }],
        "document_level_checks": [],
    }
    clauses = [
        {"clause_index": 1, "predicted_label": "Liability", "clause_text": "Liability is unlimited."},
        {"clause_index": 2, "predicted_label": "Indemnity", "clause_text": "Supplier indemnifies Customer."},
    ]
    response = {
        "cross_clause_findings": [{
            "check_id": "X-1",
            "answer": "YES",
            "status": "POTENTIAL_RISK",
            "risk_type": "Cross-clause exposure",
            "clause_ids": [1, 2],
            "evidence": [{"clause_id": 1, "quote": "Liability is unlimited."}],
            "why_flagged": "Synthetic test.",
            "score_components": {},
        }],
        "document_findings": [],
    }
    monkeypatch.setattr(contract_checks, "call_ollama", lambda *args, **kwargs: json.dumps(response))

    cross, _ = contract_checks.analyze_contract_checks(clauses, playbook=playbook, passes=1)

    finding = next(item for item in cross if item["check_id"] == "X-1")
    assert finding["risk_status"] == "INSUFFICIENT_EVIDENCE"
    assert {item["clause_id"] for item in finding["evidence"]} == {1, 2}
    assert all(item["quote"] in {clause["clause_text"] for clause in clauses} for item in finding["evidence"])



def test_contract_severity_is_not_reported_when_any_positive_finding_is_unscored():
    from app.core.risk.risk_scoring import aggregate_contract_triage

    triage = aggregate_contract_triage([
        {
            "risk_status": "POTENTIAL_RISK",
            "risk": True,
            "final_score": 16,
            "severity": "CRITICAL",
            "risk_domains": ["Liability Risk"],
            "score_components": {
                "exposure_magnitude": 4,
                "likelihood_uncertainty": 4,
                "scope_duration": 4,
                "control_weakness": 4,
            },
        },
        {
            "risk_status": "POTENTIAL_RISK",
            "risk": True,
            "final_score": None,
            "severity": None,
            "risk_domains": ["Commercial Risk"],
            "score_components": {},
        },
    ])

    assert triage["overall_score"] is None
    assert triage["overall_severity"] is None
    assert triage["human_review_required"] is True



def test_single_token_quote_is_not_sufficient_contract_evidence():
    assert _evidence_valid("liability", "Liability is unlimited.", []) is False
    assert _evidence_valid("Liability is unlimited.", "Liability is unlimited.", []) is True


def test_contradictory_no_answer_cannot_become_a_positive_clause_finding(monkeypatch):
    playbook = {
        "playbook_hash": "contradiction-test",
        "sources": {},
        "clause_types": {
            "General": {
                "checklist": [{
                    "id": "C-1",
                    "question": "Does the clause create uncapped liability?",
                    "flag_if": "Yes, with exact evidence",
                    "sources": [],
                    "risk_domain": "Liability Risk",
                }]
            }
        },
        "deterministic_rules": [],
    }
    response = json.dumps({
        "checks": [{
            "check_id": "C-1",
            "answer": "NO",
            "status": "POTENTIAL_RISK",
            "risk_type": "Contradictory answer",
            "evidence": "Liability is capped.",
            "why_flagged": "Synthetic contradictory output.",
            "score_components": {
                "exposure_magnitude": 3,
                "likelihood_uncertainty": 3,
                "scope_duration": 3,
                "control_weakness": 3,
            },
        }]
    })
    monkeypatch.setattr(risk_engine, "call_ollama", lambda *args, **kwargs: response)
    monkeypatch.setattr(risk_engine, "retrieve_legal_guidance", lambda *args, **kwargs: [])

    findings = risk_engine.analyze_clause_risk(
        clause_index=1,
        clause_text="Liability is capped.",
        clause_type="General",
        query_vector=None,
        contract_clauses=[],
        playbook=playbook,
        passes=1,
    )

    finding = next(item for item in findings if item["check_id"] == "C-1")
    assert finding["risk_status"] == "INSUFFICIENT_EVIDENCE"
    assert finding["risk"] is False

