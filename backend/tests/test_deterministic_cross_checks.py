from app.core.risk.deterministic_cross_checks import run_deterministic_cross_checks


def test_explicit_unread_online_terms_and_precedence_become_review_candidates():
    clauses = [
        {
            "clause_index": 4,
            "predicted_label": "Governing Law",
            "clause_text": (
                "The Services are subject to Supplier's online terms and the policies "
                "referenced on Supplier's website, each of which may be updated from "
                "time to time. If an Order Form conflicts with this Agreement or online "
                "terms, Supplier's online terms prevail. No fixed version is attached."
            ),
        },
        {
            "clause_index": 5,
            "predicted_label": "Governing Law",
            "clause_text": (
                "This Agreement is governed by the laws specified in the applicable "
                "Order Form. Each Order Form may designate a different forum and "
                "dispute procedure."
            ),
        },
    ]

    signals = run_deterministic_cross_checks(clauses)
    by_id = {item["id"]: item for item in signals}

    assert "DET-INCORPORATED-UNREAD" in by_id
    assert "DET-PRECEDENCE-OVERRIDE" in by_id
    assert "DET-DISPUTE-MECHANISM-AMBIGUITY" in by_id
    for signal_id in (
        "DET-INCORPORATED-UNREAD",
        "DET-PRECEDENCE-OVERRIDE",
        "DET-DISPUTE-MECHANISM-AMBIGUITY",
    ):
        signal = by_id[signal_id]
        assert signal["candidate"] is True
        assert signal["evidence"]
        assert all(item["quote"] for item in signal["evidence"])
