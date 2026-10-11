from app.core.risk.evidence_compressor import compress_cuad_evidence
from app.core.risk.risk_engine import _prompt
from app.core.risk.risk_playbook import applicable_checks, load_playbook


def _examples():
    return [
        {"source_id": "a", "clause_type": "Insurance", "score": 0.72, "clause_text": "Maintain insurance coverage."},
        {"source_id": "a", "clause_type": "Insurance", "score": 0.71, "clause_text": "Maintain insurance coverage."},
        {"source_id": "b", "clause_type": "Insurance", "score": 0.70, "clause_text": "Maintain   insurance\ncoverage."},
        {"source_id": "c", "clause_type": "Insurance", "score": 0.69, "clause_text": "The supplier shall maintain insurance coverage."},
        {"source_id": "d", "clause_type": "Insurance", "score": 0.68, "clause_text": "The parties shall maintain insurance coverage."},
    ]


def test_compressor_removes_source_and_near_duplicates_and_caps_at_two():
    compressed = compress_cuad_evidence(
        clause_id=6,
        final_label="Insurance",
        contract_text="The supplier shall maintain insurance.",
        retrieved_examples=_examples(),
    )

    assert len(compressed) == 2
    assert compressed[0]["quote"] == "Maintain insurance coverage."
    assert compressed[0]["quote"] in {item["clause_text"] for item in _examples()}
    assert "clause_text" not in compressed[0]
    assert len({item.get("source_id") for item in compressed}) == 2


def test_contract_clause_and_retrieval_evidence_remain_separate_fields():
    contract_text = "The supplier shall maintain insurance."
    clause_row = {
        "clause_index": 6,
        "clause_text": contract_text,
        "predicted_label": "Insurance",
        "retrieved_examples": _examples(),
    }
    compressed = compress_cuad_evidence(
        clause_id=clause_row["clause_index"],
        final_label=clause_row["predicted_label"],
        contract_text=clause_row["clause_text"],
        retrieved_examples=clause_row["retrieved_examples"],
    )
    clause_row["retrieved_examples"] = compressed

    assert clause_row["clause_text"] == contract_text
    assert "contract_text" not in compressed[0]
    assert "clause_text" not in compressed[0]
    assert compressed[0]["quote"] != clause_row["clause_text"]


def test_risk_prompt_uses_contract_context_not_raw_cuad_retrieval_dump():
    playbook = load_playbook()
    prompt = _prompt(
        clause_text="The supplier shall maintain insurance.",
        clause_type="Insurance",
        checks=applicable_checks(playbook, "Insurance"),
        indicators={"matched_indicators": ["insurance"]},
        context=[
            {
                "chunk_id": "contract-clause-7",
                "clause_index": 7,
                "clause_text": "Supplier must provide updated insurance certificates annually.",
            }
        ],
        playbook=playbook,
        guidance=[],
    )

    assert "CURRENT CLAUSE" in prompt
    assert "The supplier shall maintain insurance." in prompt
    assert "RELATED SAME-CONTRACT CLAUSES" in prompt
    assert "Supplier must provide updated insurance certificates annually." in prompt
    assert "Maintain insurance coverage." not in prompt
    assert "retrieval_evidence" not in prompt
