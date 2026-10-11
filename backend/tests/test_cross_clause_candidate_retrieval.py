from app.core.risk.contract_checks import _candidate_clauses


def test_candidate_clause_search_supplements_missing_cross_clause_pair_category():
    clauses = [
        {
            "clause_index": 4,
            "predicted_label": "Termination For Convenience",
            "clause_text": "Customer may terminate for convenience on 30 days' written notice.",
        },
        {
            "clause_index": 7,
            "predicted_label": "Anti-Assignment",
            "clause_text": "Pricing Schedule: all remaining minimum commitments continue after termination.",
        },
    ]

    selected = _candidate_clauses(
        clauses,
        ["Termination For Convenience", "Minimum Commitment"],
    )

    assert [item["clause_index"] for item in selected] == [4, 7]
    assert "minimum commitment" in selected[1]["clause_text"].lower()
