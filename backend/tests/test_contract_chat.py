import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
from scripts.risk.evaluate_contract_chat_demo import _evaluate_question, _fact_attributed_to_entity

from app.main import app
from app.api.routes import query


def test_contract_chat_validates_analysis_id_and_question():
    client = TestClient(app)
    response = client.post("/query/contract", json={
        "analysis_id": "../etc/passwd",
        "question": "What does this say?",
    })
    assert response.status_code == 400

    response = client.post("/query/contract", json={
        "analysis_id": "0123456789abcdef-0123456789abcdef",
        "question": "",
    })
    assert response.status_code == 422


def test_contract_chat_verifies_exact_quote_before_returning_citation(monkeypatch, tmp_path):
    analysis_id = "0123456789abcdef-0123456789abcdef"
    run_root = tmp_path / analysis_id
    run_root.mkdir()
    clause_text = "Either party may terminate this Agreement upon thirty days written notice."
    stored = {
        "analysis_id": analysis_id,
        "filename": "demo.txt",
        "contract_metadata": {"name": "Demo"},
        "clauses": [{
            "clause_index": 1,
            "clause_text": clause_text,
            "predicted_label": "Termination For Convenience",
            "risk_status": "POTENTIAL_RISK",
            "risk_findings": [],
        }],
        "contract_risk_assessment": {"status": "POTENTIAL_RISK"},
    }
    (run_root / "result.json").write_text(json.dumps(stored), encoding="utf-8")
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(
        query,
        "_call_local_chat",
        lambda *args, **kwargs: json.dumps({
            "answer": "Either party can terminate on thirty days written notice.",
            "insufficient_evidence": False,
            "citations": [{
                "clause_index": 1,
                "quote": clause_text,
                "reason": "This is the termination provision.",
            }],
            "follow_up_questions": ["Are there termination fees?"],
        }),
    )

    response = TestClient(app).post("/query/contract", json={
        "analysis_id": analysis_id,
        "question": "How can a party terminate this agreement?",
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["citations"][0]["clause_index"] == 1
    assert data["citations"][0]["quote"] == clause_text
    assert data["insufficient_evidence"] is False
    assert data["follow_up_questions"] == ["Are there termination fees?"]


def test_contract_chat_rejects_unverifiable_quote(monkeypatch, tmp_path):
    analysis_id = "0123456789abcdef-0123456789abcdef"
    run_root = tmp_path / analysis_id
    run_root.mkdir()
    (run_root / "result.json").write_text(json.dumps({
        "analysis_id": analysis_id,
        "clauses": [{
            "clause_index": 4,
            "clause_text": "The Supplier aggregate liability is capped at the fees paid during the Term.",
        }],
        "contract_risk_assessment": {},
    }), encoding="utf-8")
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(query, "_call_local_chat", lambda *args, **kwargs: json.dumps({
        "answer": "This contract has unlimited liability.",
        "insufficient_evidence": False,
        "citations": [{
            "clause_index": 4,
            "quote": "This fabricated text does not appear in the source.",
            "reason": "fake",
        }],
        "follow_up_questions": [],
    }))

    response = TestClient(app).post("/query/contract", json={
        "analysis_id": analysis_id,
        "question": "What liability does this contract define?",
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["insufficient_evidence"] is True
    assert data["model"] == "SOURCE_EXCERPTS"
    assert "couldn't verify" in data["answer"]
    # The fabricated claim is never shown, but the contract's own wording is.
    assert "unlimited" not in data["answer"].lower()
    assert "fabricated" not in json.dumps(data["citations"])
    assert data["citations"] and data["citations"][0]["clause_index"] == 4
    assert data["citations"][0]["quote"] in "The Supplier aggregate liability is capped at the fees paid during the Term."


def test_metrics_endpoint_never_returns_annotation_queue_metrics(monkeypatch, tmp_path):
    monkeypatch.setattr(query, "PROJECT_ROOT", tmp_path)
    response = TestClient(app).get("/query/phase2-metrics")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["evaluation_mode"] == "PLAYBOOK_RULE_CONFORMANCE"
    assert data["rule_validation"]["status"] == "NOT_RUN"
    assert data["classification_index_isolation"]["status"] == "NOT_RUN"
    assert data["production_release_readiness"]["status"] == "BLOCKED"
    assert data["production_release_readiness"]["production_release_allowed"] is False
    assert "gold" not in json.dumps(data).lower()
    assert "silver" not in json.dumps(data).lower()
    assert "legal-risk accuracy" in data["warning"]


def test_demo_endpoint_ignores_non_demo_saved_runs_and_builds_reproducible_fixture(monkeypatch, tmp_path):
    original_fixture = Path(query.PROJECT_ROOT) / "data" / "risk" / "demo_contract_for_reproduction.txt"
    fixture_path = tmp_path / "data" / "risk" / "demo_contract_for_reproduction.txt"
    fixture_path.parent.mkdir(parents=True)
    fixture_path.write_bytes(original_fixture.read_bytes())
    fixture_hash = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    runs_root = tmp_path / "runs"

    # Even a same-filename result must not replace the curated demo unless it was
    # generated by this deterministic endpoint and matches the checked-in fixture.
    old_run = runs_root / "fedcba9876543210-fedcba9876543210"
    old_run.mkdir(parents=True)
    (old_run / "result.json").write_text(json.dumps({
        "analysis_id": old_run.name,
        "filename": fixture_path.name,
        "contract_metadata": {"document_hash": fixture_hash},
        "clauses": [{"clause_index": i, "clause_text": "Old model-generated result."} for i in range(8)],
        "contract_risk_assessment": {},
    }), encoding="utf-8")

    monkeypatch.setattr(query, "RUNS_DIR", runs_root)
    monkeypatch.setattr(query, "PROJECT_ROOT", tmp_path)
    response = TestClient(app).get("/query/demo-analysis")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["demo_mode"] is True
    assert data["filename"] == fixture_path.name
    assert data["analysis_id"] != old_run.name
    assert data["total_clauses"] == 11
    assert data["contract_metadata"]["document_hash"] == fixture_hash
    assert "illustrative" in data["notice"].lower()
    assert all(clause["clause_text"] != "Old model-generated result." for clause in data["clauses"])

def test_contract_chat_retrieval_expands_legal_synonyms_and_prioritizes_risk_findings():
    clauses = [
        {"clause_index": 1, "predicted_label": "Payment Terms", "clause_text": "Invoices are payable within thirty days."},
        {"clause_index": 2, "predicted_label": "Cap On Liability", "clause_text": "Supplier's aggregate liability shall not exceed fees paid in the previous one month."},
        {"clause_index": 3, "predicted_label": "Termination", "clause_text": "Supplier may terminate immediately for any breach.", "risk_findings": [
            {"risk_status": "POTENTIAL_RISK", "risk_type": "Unequal termination rights", "why_flagged": "Immediate termination is one-sided."}
        ]},
        {"clause_index": 4, "predicted_label": "Insurance", "clause_text": "No minimum policy limits are stated.", "risk_findings": [
            {"risk_status": "INSUFFICIENT_EVIDENCE", "risk_type": "Minimum policy limits unclear", "why_flagged": "The contract does not state a minimum coverage amount."}
        ]},
    ]
    selected = query._select_clauses(clauses, "How is supplier liability capped?")
    assert selected[0]["clause_index"] == 2

    selected = query._select_clauses(clauses, "What are the main risks?")
    assert selected[0]["clause_index"] == 3

    selected = query._select_clauses(clauses, "Which findings still need more evidence?")
    assert selected[0]["clause_index"] == 4


def test_contract_chat_fails_closed_when_contract_question_has_no_verified_citation(monkeypatch, tmp_path):
    analysis_id = "0123456789abcdef-0123456789abcdef"
    run_root = tmp_path / analysis_id
    run_root.mkdir()
    (run_root / "result.json").write_text(json.dumps({
        "analysis_id": analysis_id,
        "clauses": [{"clause_index": 1, "clause_text": "Supplier may terminate with notice.", "predicted_label": "Termination"}],
        "contract_risk_assessment": {},
    }), encoding="utf-8")
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(query, "_call_local_chat", lambda *args, **kwargs: json.dumps({
        "answer": "The customer has a 30-day termination right.",
        "insufficient_evidence": False,
        "citations": [],
        "follow_up_questions": [],
    }))
    response = TestClient(app).post("/query/contract", json={
        "analysis_id": analysis_id,
        "question": "What termination rights does the customer have?",
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["insufficient_evidence"] is True
    assert data["model"] == "SOURCE_EXCERPTS"
    assert "30-day" not in data["answer"]
    assert "couldn't verify" in data["answer"]
    assert data["citations"][0]["quote"] == "Supplier may terminate with notice."


def test_contract_chat_returns_verified_extractive_fallback_when_local_model_is_unavailable(monkeypatch, tmp_path):
    analysis_id = "0123456789abcdef-0123456789abcdef"
    run_root = tmp_path / analysis_id
    run_root.mkdir()
    source = "Supplier may terminate this Agreement immediately for any breach after written notice."
    (run_root / "result.json").write_text(json.dumps({
        "analysis_id": analysis_id,
        "filename": "fallback.txt",
        "clauses": [{"clause_index": 5, "heading": "Termination", "predicted_label": "Termination", "clause_text": source}],
        "contract_risk_assessment": {},
    }), encoding="utf-8")
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)
    def unavailable(*args, **kwargs):
        raise RuntimeError("Ollama offline")
    monkeypatch.setattr(query, "_call_local_chat", unavailable)
    response = TestClient(app).post("/query/contract", json={
        "analysis_id": analysis_id,
        "question": "What termination rights are stated?",
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["model"] == "EXTRACTIVE_FALLBACK"
    assert data["insufficient_evidence"] is True
    assert data["citations"][0]["clause_index"] == 5
    assert data["citations"][0]["quote"] in source
    assert "have not generated an interpretation" in data["answer"]


def test_demo_analysis_generates_reproducible_walkthrough_without_prior_upload(monkeypatch, tmp_path):
    original_fixture = Path(query.PROJECT_ROOT) / "data" / "risk" / "demo_contract_for_reproduction.txt"
    fixture_path = tmp_path / "data" / "risk" / "demo_contract_for_reproduction.txt"
    fixture_path.parent.mkdir(parents=True)
    fixture_path.write_bytes(original_fixture.read_bytes())
    runs_root = tmp_path / "runs"
    monkeypatch.setattr(query, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(query, "RUNS_DIR", runs_root)

    response = TestClient(app).get("/query/demo-analysis")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["demo_mode"] is True
    assert data["total_clauses"] == 11
    assert data["analysis_id"]
    assert "illustrative" in data["notice"].lower()
    assert data["contract_metadata"]["document_hash"] == hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    assert len([finding for clause in data["clauses"] for finding in clause["risk_findings"]]) >= 8
    saved = runs_root / data["analysis_id"] / "result.json"
    assert saved.is_file()
    stored = json.loads(saved.read_text(encoding="utf-8"))
    assert stored["demo_mode"] is True
    assert stored["analysis_id"] == data["analysis_id"]
    assert "contract_risk_json" in data["downloads"]
    assert "clauses_csv" in data["downloads"]
    assert "manifest_json" in data["downloads"]


def test_demo_contract_endpoint_downloads_repository_fixture(monkeypatch, tmp_path):
    original_fixture = Path(query.PROJECT_ROOT) / "data" / "risk" / "demo_contract_for_reproduction.txt"
    fixture_path = tmp_path / "data" / "risk" / "demo_contract_for_reproduction.txt"
    fixture_path.parent.mkdir(parents=True)
    fixture_path.write_bytes(original_fixture.read_bytes())
    monkeypatch.setattr(query, "PROJECT_ROOT", tmp_path)
    response = TestClient(app).get("/query/demo-contract")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert response.content == fixture_path.read_bytes()

def test_contract_chat_parses_string_false_without_treating_it_as_truthy(monkeypatch, tmp_path):
    analysis_id = "0123456789abcdef-0123456789abcdef"
    run_root = tmp_path / analysis_id
    run_root.mkdir()
    clause_text = "Supplier shall maintain commercially reasonable insurance coverage during the Term."
    (run_root / "result.json").write_text(json.dumps({
        "analysis_id": analysis_id,
        "clauses": [{"clause_index": 7, "clause_text": clause_text, "predicted_label": "Insurance"}],
        "contract_risk_assessment": {},
    }), encoding="utf-8")
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(query, "_call_local_chat", lambda *args, **kwargs: json.dumps({
        "answer": "The supplier must maintain insurance during the agreement term.",
        "insufficient_evidence": "false",
        "citations": [{"clause_index": 7, "quote": clause_text, "reason": "Insurance obligation."}],
        "follow_up_questions": [],
    }))
    response = TestClient(app).post("/query/contract", json={
        "analysis_id": analysis_id,
        "question": "What insurance must the supplier maintain?",
    })
    assert response.status_code == 200, response.text
    assert response.json()["insufficient_evidence"] is False
    assert response.json()["citations"][0]["quote"] == clause_text

def test_contract_chat_abstains_if_any_citation_is_unverifiable(monkeypatch, tmp_path):
    analysis_id = "0123456789abcdef-0123456789abcdef"
    run_root = tmp_path / analysis_id
    run_root.mkdir()
    source = "Supplier shall maintain commercially reasonable insurance coverage during the Term."
    (run_root / "result.json").write_text(json.dumps({
        "analysis_id": analysis_id,
        "clauses": [{"clause_index": 7, "clause_text": source, "predicted_label": "Insurance"}],
        "contract_risk_assessment": {},
    }), encoding="utf-8")
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(query, "_call_local_chat", lambda *args, **kwargs: json.dumps({
        "answer": "The supplier must maintain insurance with a $10 million minimum limit.",
        "insufficient_evidence": False,
        "citations": [
            {"clause_index": 7, "quote": source, "reason": "Insurance obligation."},
            {"clause_index": 7, "quote": "The supplier must maintain $10 million coverage.", "reason": "Invented limit."},
        ],
        "follow_up_questions": [],
    }))
    response = TestClient(app).post("/query/contract", json={
        "analysis_id": analysis_id,
        "question": "What insurance limit must the supplier maintain?",
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["insufficient_evidence"] is True
    assert "couldn't verify" in data["answer"]
    assert "$10 million" not in data["answer"]
    assert len(data["citations"]) == 1
    assert data["citations"][0]["quote"] == source


def test_contract_chat_answers_product_help_without_model_or_contract_claims(monkeypatch, tmp_path):
    analysis_id = "0123456789abcdef-0123456789abcdef"
    run_root = tmp_path / analysis_id
    run_root.mkdir()
    (run_root / "result.json").write_text(json.dumps({
        "analysis_id": analysis_id,
        "clauses": [{"clause_index": 1, "clause_text": "Supplier may terminate with notice.", "predicted_label": "Termination"}],
        "contract_risk_assessment": {},
    }), encoding="utf-8")
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)

    def model_must_not_be_called(*args, **kwargs):
        raise AssertionError("Product-help intent should not depend on Ollama.")

    monkeypatch.setattr(query, "_call_local_chat", model_must_not_be_called)
    response = TestClient(app).post("/query/contract", json={
        "analysis_id": analysis_id,
        "question": "What can you do with this contract?",
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["model"] == "DETERMINISTIC_HELP"
    assert data["insufficient_evidence"] is False
    assert data["citations"] == []
    assert "summarize the agreement" in data["answer"]
    assert "not legal advice" in data["disclaimer"]

def test_demo_retrieval_selects_the_expected_sections_for_recording_questions():
    fixture = Path(query.PROJECT_ROOT) / "data" / "risk" / "demo_contract_for_reproduction.txt"
    fixture_hash = hashlib.sha256(fixture.read_bytes()).hexdigest()
    demo_id = "0123456789abcdef-0123456789abcdef"
    result = query._build_synthetic_demo_result(fixture, fixture_hash, demo_id)
    clauses = result["clauses"]

    cases = [
        ("How does the supplier liability cap compare with the customer's cap?", 3),
        ("What termination rights does each party have?", 5),
        ("Can the vendor cancel the agreement?", 5),
        ("Can we determine the governing law from this agreement alone?", 10),
        ("What insurance limits are required?", 7),
        ("What happens to customer data after termination?", 11),
        # These are the exact suggested-question button labels in ChatPanel.jsx.
        ("Who can terminate this agreement, and on what notice?", 5),
        ("How do the two parties' liability caps compare?", 3),
        ("Which law governs, and where would disputes be heard?", 10),
        ("What happens to our data when the contract ends?", 11),
    ]
    for question, expected_clause in cases:
        selected = query._select_clauses(clauses, question)
        assert selected, question
        assert selected[0]["clause_index"] == expected_clause, (
            f"{question!r} should prioritize clause {expected_clause}, "
            f"got {[item['clause_index'] for item in selected[:4]]}"
        )

def test_live_demo_evaluator_rejects_swapped_party_cap_assignments():
    correct = (
        "customer's cap is ten times the fees, while supplier's cap is limited "
        "to fees paid by customer in the previous one month"
    )
    swapped = (
        "supplier's cap is ten times the fees, while customer's cap is limited "
        "to fees paid in the previous one month"
    )
    assert _fact_attributed_to_entity(correct, "customer", ["ten times", "10 times"])
    assert _fact_attributed_to_entity(correct, "supplier", ["one month", "monthly"])
    assert not _fact_attributed_to_entity(swapped, "customer", ["ten times", "10 times"])
    assert not _fact_attributed_to_entity(swapped, "supplier", ["one month", "monthly"])

def test_clause_number_references_retrieve_the_named_provisions():
    clauses = [
        {"clause_index": 1, "heading": "Term", "clause_text": "The initial term is one year."},
        {"clause_index": 3, "heading": "Limitation of Liability", "clause_text": "Supplier liability is capped at one month of fees."},
        {"clause_index": 4, "heading": "Indemnification", "clause_text": "Customer shall indemnify Supplier for claims."},
        {"clause_index": 10, "heading": "Governing Law", "clause_text": "The applicable Order Form specifies governing law."},
    ]
    selected = query._select_clauses(clauses, "Explain clause 3.")
    assert selected[0]["clause_index"] == 3

    selected = query._select_clauses(clauses, "Compare clauses 3 and 4.")
    assert [item["clause_index"] for item in selected[:2]] == [3, 4]

    assert query._select_clauses(clauses, "Explain clause 99.") == []


def test_contract_chat_does_not_send_unrelated_questions_to_the_model(monkeypatch, tmp_path):
    analysis_id = "0123456789abcdef-0123456789abcdef"
    run_root = tmp_path / analysis_id
    run_root.mkdir()
    (run_root / "result.json").write_text(json.dumps({
        "analysis_id": analysis_id,
        "clauses": [
            {"clause_index": 1, "heading": "Term", "clause_text": "The initial term is one year."},
            {"clause_index": 3, "heading": "Liability", "clause_text": "Supplier liability is capped at one month of fees."},
        ],
        "contract_risk_assessment": {},
    }), encoding="utf-8")
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)

    def model_must_not_be_called(*args, **kwargs):
        raise AssertionError("Irrelevant queries must abstain before calling the model.")

    monkeypatch.setattr(query, "_call_local_chat", model_must_not_be_called)
    response = TestClient(app).post("/query/contract", json={
        "analysis_id": analysis_id,
        "question": "Who won the football world cup in 1998?",
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["model"] == "RETRIEVAL_ABSTENTION"
    assert data["insufficient_evidence"] is True
    assert data["citations"] == []
    assert "won't guess" in data["answer"]


def test_contract_chat_answers_supported_explicit_clause_question(monkeypatch, tmp_path):
    analysis_id = "0123456789abcdef-0123456789abcdef"
    run_root = tmp_path / analysis_id
    run_root.mkdir()
    source = "Supplier's aggregate liability shall not exceed the fees paid by Customer in the previous one month."
    (run_root / "result.json").write_text(json.dumps({
        "analysis_id": analysis_id,
        "clauses": [
            {"clause_index": 3, "heading": "Limitation of Liability", "clause_text": source},
            {"clause_index": 5, "heading": "Termination", "clause_text": "Supplier may terminate immediately for any breach."},
        ],
        "contract_risk_assessment": {},
    }), encoding="utf-8")
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(query, "_call_local_chat", lambda *args, **kwargs: json.dumps({
        "answer": "Clause 3 caps the supplier's aggregate liability at fees paid in the previous one month.",
        "insufficient_evidence": False,
        "citations": [{"clause_index": 3, "quote": source, "reason": "Exact liability cap."}],
        "follow_up_questions": [],
    }))
    response = TestClient(app).post("/query/contract", json={
        "analysis_id": analysis_id,
        "question": "Explain clause 3.",
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["insufficient_evidence"] is False
    assert data["citations"][0]["clause_index"] == 3

def test_party_identity_question_uses_verified_metadata_evidence_without_model(monkeypatch, tmp_path):
    analysis_id = "0123456789abcdef-0123456789abcdef"
    run_root = tmp_path / analysis_id
    run_root.mkdir()
    evidence = 'This Agreement is entered into by Northstar Analytics Ltd. ("Customer") and VendorCo Ltd. ("Supplier").'
    (run_root / "result.json").write_text(json.dumps({
        "analysis_id": analysis_id,
        "contract_metadata": {
            "parties": ['Northstar Analytics Ltd. ("Customer")', 'VendorCo Ltd. ("Supplier")'],
            "evidence": {"parties": evidence},
        },
        # The opening party block is intentionally absent from the segmented clauses.
        "clauses": [
            {"clause_index": 1, "heading": "Term", "clause_text": "The initial term is one year."},
        ],
        "contract_risk_assessment": {},
    }), encoding="utf-8")
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)

    def model_must_not_be_called(*args, **kwargs):
        raise AssertionError("A verified party-metadata lookup should not require a model call.")

    monkeypatch.setattr(query, "_call_local_chat", model_must_not_be_called)
    response = TestClient(app).post("/query/contract", json={
        "analysis_id": analysis_id,
        "question": "Who are the parties to this contract?",
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["model"] == "DETERMINISTIC_PARTY_LOOKUP"
    assert data["insufficient_evidence"] is False
    assert "Northstar Analytics Ltd." in data["answer"]
    assert "VendorCo Ltd." in data["answer"]
    assert data["citations"][0]["source_type"] == "contract_metadata"
    assert data["citations"][0]["quote"] == evidence


def test_simple_clause_question_returns_heading_and_exact_source_without_model(monkeypatch, tmp_path):
    analysis_id = "0123456789abcdef-0123456789abcdef"
    run_root = tmp_path / analysis_id
    run_root.mkdir()
    source = (
        'This Agreement is entered into by Northstar Analytics Ltd. ("Customer") and VendorCo Ltd. ("Supplier"). '
        "The initial term is one year and automatically renews for successive one-year periods unless either party "
        "gives written notice at least 120 days before the end of the then-current term."
    )
    (run_root / "result.json").write_text(json.dumps({
        "analysis_id": analysis_id,
        "clauses": [{
            "clause_index": 1,
            "heading": "1. PARTIES AND TERM",
            "clause_text": source,
        }],
        "contract_risk_assessment": {},
    }), encoding="utf-8")
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)

    def model_must_not_be_called(*args, **kwargs):
        raise AssertionError("A direct clause lookup should not depend on model citation formatting.")

    monkeypatch.setattr(query, "_call_local_chat", model_must_not_be_called)
    response = TestClient(app).post("/query/contract", json={
        "analysis_id": analysis_id,
        "question": "What is clause 1 about?",
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["model"] == "DETERMINISTIC_CLAUSE_LOOKUP"
    assert data["insufficient_evidence"] is False
    assert "identifies the contracting parties" in data["answer"]
    assert data["citations"][0]["clause_index"] == 1
    assert data["citations"][0]["quote"] == source


def test_citation_verification_accepts_typographic_variants_but_returns_exact_source():
    source = "Supplier’s aggregate liability shall not exceed “fees paid” during the Term."
    proposed_quote = """Supplier's aggregate liability shall not exceed "fees paid" during the Term."""
    citations = query._verified_citations(
        [{"clause_index": 3, "quote": proposed_quote, "reason": "Liability cap."}],
        {3: source},
    )
    assert len(citations) == 1
    assert citations[0]["quote"] == source
    assert query._has_unverified_citation(
        [{"clause_index": 3, "quote": proposed_quote, "reason": "Liability cap."}],
        {3: source},
    ) is False


def test_chatbot_semantic_evaluator_checks_all_required_concepts_and_clause_citations():
    spec = {
        "id": "indemnity_cap",
        "question": "Does indemnity fall under the aggregate liability cap?",
        "must_cite_terms": ["indemnification obligations", "aggregate liability shall not exceed", "Customer shall indemnify"],
        "must_cite_clause_indices": [3, 4],
        "must_answer_one_of": [["ambiguous", "unclear"], ["aggregate liability caps", "aggregate caps"]],
        "must_answer_all": [["indemnification", "indemnity"]],
        "must_answer_relations": [],
    }
    clauses = {
        3: "Except for indemnification obligations, liability is limited. Customer aggregate liability shall not exceed ten times fees.",
        4: "Customer shall indemnify Supplier for claims.",
    }
    good = {
        "answer": "The interaction is ambiguous: indemnification obligations are excepted in one sentence, but the aggregate liability caps are stated separately.",
        "insufficient_evidence": False,
        "citations": [
            {"clause_index": 3, "quote": "Except for indemnification obligations, liability is limited. Customer aggregate liability shall not exceed ten times fees."},
            {"clause_index": 4, "quote": "Customer shall indemnify Supplier for claims."},
        ],
    }
    assert _evaluate_question(spec, good, clauses)["passed"] is True

    missing_clause = {**good, "citations": good["citations"][:1]}
    result = _evaluate_question(spec, missing_clause, clauses)
    assert result["checks"]["required_clause_citations_present"] is False
    assert result["passed"] is False

    incomplete_answer = {**good, "answer": "The issue is ambiguous and the aggregate liability caps are stated separately."}
    result = _evaluate_question(spec, incomplete_answer, clauses)
    assert result["checks"]["answer_contains_all_required_concepts"] is False
    assert result["passed"] is False



def _store_run(tmp_path, clauses, metadata=None):
    analysis_id = "0123456789abcdef-0123456789abcdef"
    run_root = tmp_path / analysis_id
    run_root.mkdir()
    (run_root / "result.json").write_text(json.dumps({
        "analysis_id": analysis_id,
        "filename": "c.txt",
        "contract_metadata": metadata or {},
        "clauses": clauses,
        "contract_risk_assessment": {},
    }), encoding="utf-8")
    return analysis_id


def test_source_quote_tolerates_case_quote_marks_and_gaps_but_not_new_words():
    source = 'Customer shall pay the \u201cFees\u201d within thirty days.\nSupplier may suspend service for non-payment.'
    assert query._find_source_quote(source, 'Customer shall pay the "Fees" within thirty days.') == source.split("\n")[0]
    assert query._find_source_quote(source, "customer  shall pay the fees within thirty days") == source.split("\n")[0]
    assert query._find_source_quote(source, "Customer shall pay ... suspend service for non-payment")
    assert query._find_source_quote(source, "Customer shall pay the Fees within sixty days.") is None
    assert query._find_source_quote(source, "too short") is None


def test_chat_retries_once_when_first_quotes_do_not_match(monkeypatch, tmp_path):
    source = "Supplier may terminate this Agreement immediately for any breach."
    analysis_id = _store_run(tmp_path, [{"clause_index": 5, "heading": "Termination", "predicted_label": "Termination", "clause_text": source}])
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)
    calls = []

    def flaky(messages, *args, **kwargs):
        calls.append(messages)
        quote = "Supplier can end the Agreement at once for breach." if len(calls) == 1 else source
        return json.dumps({
            "answer": "The supplier can terminate immediately for breach.",
            "insufficient_evidence": False,
            "citations": [{"clause_index": 5, "quote": quote, "reason": "Termination right."}],
            "follow_up_questions": [],
        })

    monkeypatch.setattr(query, "_call_local_chat", flaky)
    data = TestClient(app).post("/query/contract", json={"analysis_id": analysis_id, "question": "Who can terminate?"}).json()
    assert len(calls) == 2
    assert data["insufficient_evidence"] is False
    assert data["model"] != "SOURCE_EXCERPTS"
    assert data["citations"][0]["quote"] == source


def test_chat_answers_parties_when_extracted_names_carry_a_role(monkeypatch, tmp_path):
    analysis_id = _store_run(
        tmp_path,
        [{"clause_index": 1, "heading": "PARTIES AND TERM", "predicted_label": "Contract Term",
          "clause_text": '1. PARTIES AND TERM\nThis Agreement is entered into by Northstar Analytics Ltd. ("Customer") and VendorCo Ltd. ("Supplier"). The initial term is one year.'}],
        {"parties": ["Northstar Analytics Ltd. (Customer)", "VendorCo Ltd. (Supplier)"]},
    )
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)

    def model_must_not_be_called(*args, **kwargs):
        raise AssertionError("Parties are answered from metadata.")

    monkeypatch.setattr(query, "_call_local_chat", model_must_not_be_called)
    client = TestClient(app)
    for question in ("What are the parties of this contract?", "Who are the parties?", "who is this agreement between"):
        data = client.post("/query/contract", json={"analysis_id": analysis_id, "question": question}).json()
        assert data["model"] == "DETERMINISTIC_PARTY_LOOKUP", question
        assert data["insufficient_evidence"] is False, question
        assert "Northstar Analytics Ltd. (Customer)" in data["answer"]
        assert len(data["citations"]) == 1
        assert data["citations"][0]["clause_index"] == 1
        assert "VendorCo Ltd." in data["citations"][0]["quote"]


def test_parties_questions_are_answered_from_metadata_even_when_phrased_loosely(monkeypatch, tmp_path):
    analysis_id = "0123456789abcdef-0123456789abcdef"
    run_root = tmp_path / analysis_id
    run_root.mkdir()
    (run_root / "result.json").write_text(json.dumps({
        "analysis_id": analysis_id,
        "contract_metadata": {"parties": ["Northstar Analytics Ltd. (Customer)", "VendorCo Ltd. (Supplier)"]},
        "clauses": [{
            "clause_index": 1,
            "heading": "PARTIES AND TERM",
            "clause_text": 'This Agreement is entered into by Northstar Analytics Ltd. ("Customer") and VendorCo Ltd. ("Supplier").',
        }],
        "contract_risk_assessment": {},
    }), encoding="utf-8")
    monkeypatch.setattr(query, "RUNS_DIR", tmp_path)

    def model_must_not_be_called(*args, **kwargs):
        raise AssertionError("Party identity is answered from metadata without the model.")

    monkeypatch.setattr(query, "_call_local_chat", model_must_not_be_called)
    for phrasing in ("who are the parties?", "What is the contract parties", "what are this contract's parties", "name the parties"):
        data = TestClient(app).post("/query/contract", json={"analysis_id": analysis_id, "question": phrasing}).json()
        assert data["insufficient_evidence"] is False, phrasing
        assert "Northstar Analytics" in data["answer"] and "VendorCo" in data["answer"], phrasing
        assert data["citations"] and "VendorCo Ltd." in data["citations"][0]["quote"], phrasing

    # A question about the parties' duties is not an identity question and must still go to the model.
    monkeypatch.setattr(query, "_call_local_chat", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))
    data = TestClient(app).post("/query/contract", json={"analysis_id": analysis_id, "question": "What are the parties' obligations?"}).json()
    assert data["model"] != "DETERMINISTIC_PARTY_LOOKUP"
