from app.core.risk.contract_assessor import _prompt, build_contract_evidence
from app.core.risk.evidence_compressor import compress_cuad_evidence


def _examples():
    return [
        {"source_id": "a", "clause_type": "Insurance", "score": 0.72, "clause_text": "Maintain insurance coverage."},
        {"source_id": "a", "clause_type": "Insurance", "score": 0.71, "clause_text": "Maintain insurance coverage."},
        {"source_id": "b", "clause_type": "Insurance", "score": 0.70, "clause_text": "Maintain   insurance\ncoverage."},
        {"source_id": "c", "clause_type": "Insurance", "score": 0.69, "clause_text": "The supplier shall maintain insurance coverage."},
        {"source_id": "d", "clause_type": "Insurance", "score": 0.68, "clause_text": "The parties shall maintain insurance coverage."},
    ]


def test_compressor_removes_exact_source_and_near_duplicates_and_caps_at_two():
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


def test_contract_text_and_clause_id_remain_separate_from_cuad_evidence():
    contract_text = "The supplier shall maintain insurance."
    evidence = build_contract_evidence([
        {
            "clause_index": 6,
            "clause_text": contract_text,
            "predicted_label": "Insurance",
            "retrieved_examples": _examples(),
        }
    ])

    item = evidence["classified_clauses"][0]
    assert item["clause_id"] == 6
    assert item["contract_text"] == contract_text
    assert len(item["supporting_evidence"]) <= 2
    assert "retrieval_evidence" not in item


def test_compact_risk_prompt_does_not_include_raw_retrieval_dump():
    evidence = build_contract_evidence([
        {
            "clause_index": 6,
            "clause_text": "The supplier shall maintain insurance.",
            "predicted_label": "Insurance",
            "retrieved_examples": _examples(),
        }
    ])
    prompt = _prompt(evidence, [], [])

    assert "COMPACT CONTRACT RISK CONTEXT" in prompt
    assert prompt.count("Maintain insurance coverage.") <= 1
    assert "retrieval_evidence" not in prompt
    assert '"clause_text"' not in prompt
