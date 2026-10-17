from app.core.risk.deterministic_rules import RULE_ENGINE_VERSION, evaluate_playbook_rules
from app.core.risk.knowledge_base import load_risk_knowledge
from app.core.risk.risk_detector import build_risk_prompt, detect_legal_indicators
from app.core.risk.risk_playbook import load_playbook


def _matches(text, label="UNKNOWN"):
    return evaluate_playbook_rules(
        clause_text=text,
        clause_index=3,
        clause_type=label,
        playbook=load_playbook(),
    )


def _ids(findings):
    return {item["check_id"] for item in findings}


def test_rules_run_independently_of_cuad_clause_label():
    text = "The Supplier's liability is expressly uncapped under this Agreement."
    outputs = [_ids(_matches(text, label)) for label in ("Insurance", "Intellectual Property", "UNKNOWN")]
    assert all("PR-UNCAPPED-LIABILITY" in ids for ids in outputs)
    assert outputs[0] == outputs[1] == outputs[2]


def test_uncapped_indemnity_rule_returns_exact_uploaded_text():
    text = "Indemnification obligations are expressly excluded from the aggregate liability cap."
    finding = next(x for x in _matches(text) if x["check_id"] == "PR-INDEMNITY-OUTSIDE-CAP")
    assert finding["evidence"] in text
    assert finding["risk_status"] == "POTENTIAL_RISK"
    assert finding["provenance"]["source"] == "DETERMINISTIC_PLAYBOOK_RULE"
    assert finding["provenance"]["rule_engine_version"] == RULE_ENGINE_VERSION


def test_liquidated_damages_outside_cap_is_a_playbook_trigger():
    text = "Liquidated damages are expressly outside the aggregate liability cap."
    assert "PR-LIQUIDATED-DAMAGES-OUTSIDE-CAP" in _ids(_matches(text))


def test_immediate_termination_rule_is_label_independent():
    text = "Supplier may terminate this Agreement immediately for any breach."
    assert "PR-IMMEDIATE-TERMINATION-NO-NOTICE" in _ids(_matches(text, "Payment Terms"))


def test_broad_ip_license_rule_does_not_need_ip_classifier_label():
    text = "Customer receives a worldwide, irrevocable license to use the software."
    assert "PR-BROAD-IP-LICENSE" in _ids(_matches(text, "Insurance"))


def test_full_remaining_term_fees_rule_triggers():
    text = "If Customer terminates for convenience, Customer remains liable for all fees for the entire remaining term and all minimum commitments."
    assert "PR-EARLY-EXIT-FULL-TERM-FEES" in _ids(_matches(text, "Termination"))


def test_absolute_assignment_prohibition_triggers():
    text = "Customer may not assign this Agreement under any circumstances."
    assert "PR-ABSOLUTE-ASSIGNMENT-PROHIBITION" in _ids(_matches(text, "UNKNOWN"))


def test_protective_cap_language_does_not_trigger_uncapped_rules():
    text = "All liability, including indemnification and liquidated damages, is subject to the aggregate liability cap."
    ids = _ids(_matches(text))
    assert "PR-UNCAPPED-LIABILITY" not in ids
    assert "PR-INDEMNITY-OUTSIDE-CAP" not in ids
    assert "PR-LIQUIDATED-DAMAGES-OUTSIDE-CAP" not in ids


def test_limited_nonexclusive_license_is_not_a_broad_license_trigger():
    text = "Customer receives a non-exclusive license limited to internal use for three years."
    assert "PR-BROAD-IP-LICENSE" not in _ids(_matches(text, "Unknown"))


def test_qualified_notice_and_cure_do_not_trigger_immediate_termination():
    text = "Supplier may terminate only after written notice and a 30-day cure period."
    assert "PR-IMMEDIATE-TERMINATION-NO-NOTICE" not in _ids(_matches(text, "Termination"))


def test_negated_uncapped_liability_wording_does_not_trigger():
    text = "The parties agree liability is not unlimited and remains subject to the aggregate cap."
    assert "PR-UNCAPPED-LIABILITY" not in _ids(_matches(text))


def test_no_trigger_is_not_relabelled_no_risk():
    assert _matches("The Supplier shall provide the monthly service report.") == []


def test_risk_indicators_scan_across_categories_not_only_predicted_label():
    indicators = detect_legal_indicators(
        "The customer receives a perpetual worldwide license to the software.",
        "Insurance",
    )
    assert "broad license scope" in indicators["matched_indicators"]
    assert indicators["indicator_scope"] == "ALL_RISK_CATEGORIES_NOT_GATED_BY_CUAD_LABEL"


def test_legacy_risk_prompt_contains_no_retrieved_cuad_example_spans():
    prompt = build_risk_prompt(
        clause_text="Liability is unlimited.",
        clause_type="Insurance",
        legal_indicators={"matched_indicators": ["uncapped or unlimited liability wording"]},
        guidance=[],
        contract_context=[{"chunk_id": "uploaded-clause-4", "clause_text": "The Supplier shall indemnify the Customer."}],
        risk_taxonomy=[],
    )
    assert "CUAD retrieval evidence" not in prompt
    assert "Candidate CUAD labels" not in prompt
    assert "Example:" not in prompt


def test_playbook_rules_have_taxonomy_domains_and_unique_ids():
    playbook = load_playbook()
    rules = playbook.get("deterministic_rules") or []
    assert len(rules) >= 7
    assert len({rule["id"] for rule in rules}) == len(rules)
    taxonomy_domains = {item["risk_domain"] for item in load_risk_knowledge().get("risk_domains", [])}
    assert all(rule["risk_domain"] in taxonomy_domains for rule in rules)
    assert all(rule["pattern"] and rule["question"] for rule in rules)
    assert not any(
        any(key in rule for key in ("training_examples", "retrieved_examples", "example_clause", "silver_evidence"))
        for rule in rules
    )



def test_neither_party_has_unlimited_liability_is_a_protected_control():
    text = "Neither party has unlimited liability under this Agreement."
    assert "PR-UNCAPPED-LIABILITY" not in _ids(_matches(text))


def test_may_not_terminate_immediately_is_not_a_positive_trigger():
    text = "Customer may not terminate this Agreement immediately; written notice and the cure period apply."
    assert "PR-IMMEDIATE-TERMINATION-NO-NOTICE" not in _ids(_matches(text))


def test_explicit_no_perpetual_license_is_not_a_broad_license_trigger():
    text = "No perpetual license is granted under this Agreement."
    assert "PR-BROAD-IP-LICENSE" not in _ids(_matches(text))


def test_assignment_consent_carveout_is_not_an_absolute_prohibition():
    text = "Customer may not assign this Agreement under any circumstances without prior written consent."
    assert "PR-ABSOLUTE-ASSIGNMENT-PROHIBITION" not in _ids(_matches(text))


def test_direct_rule_finding_survives_contract_level_aggregation():
    from app.core.risk.contract_risk_engine import aggregate_clause_risks

    playbook = load_playbook()
    text = "The Supplier's liability is expressly uncapped under this Agreement."
    findings = evaluate_playbook_rules(
        clause_text=text,
        clause_index=3,
        clause_type="Insurance",
        playbook=playbook,
    )
    assessment = aggregate_clause_risks(findings, playbook)

    assert assessment["status"] == "POTENTIAL_RISK"
    assert 3 in assessment["affected_clauses"]
    assert "PR-UNCAPPED-LIABILITY" in {
        item["check_id"] for item in assessment["key_risks"]
    }
    assert assessment["confidence_status"] == "NOT_CALIBRATED_FOR_CONTRACT_LEVEL"
    # A deterministic rule trigger remains a categorical review finding; no severity is inferred.
    assert assessment["overall_risk"] == "POTENTIAL_RISK"
    assert assessment["severity_status"] == "DEPRECATED_NOT_USED"
    assert assessment["overall_score"] is None
    assert assessment["human_review_required"] is True



def test_direct_rule_survives_related_clause_retrieval_and_llm_failure(monkeypatch):
    from app.core.risk import risk_engine

    text = "The Supplier's liability is expressly uncapped under this Agreement."

    def fail_context(**kwargs):
        raise RuntimeError("synthetic retrieval outage")

    def fail_model(*args, **kwargs):
        raise RuntimeError("synthetic model outage")

    monkeypatch.setattr(risk_engine, "retrieve_related_contract_context", fail_context)
    monkeypatch.setattr(risk_engine, "call_ollama", fail_model)

    findings = risk_engine.analyze_clause_risk(
        clause_index=3,
        clause_text=text,
        clause_type="Insurance",
        query_vector=[0.1, 0.2],
        contract_clauses=[{
            "clause_index": 3,
            "clause_text": text,
            "predicted_label": "Insurance",
        }],
        cohere_client=None,
        qdrant_client=None,
        playbook=load_playbook(),
        passes=1,
    )

    finding = next(item for item in findings if item.get("check_id") == "PR-UNCAPPED-LIABILITY")
    assert finding["risk_status"] == "POTENTIAL_RISK"
    assert finding["evidence"] in text
    assert finding["provenance"]["source"] == "DETERMINISTIC_PLAYBOOK_RULE"
    assert {source.get("id") for source in finding["supporting_sources"]} >= {"P2", "P4"}
    assert all(source.get("supporting_quote_or_paraphrase") for source in finding["supporting_sources"])
