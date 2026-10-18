from app.services.rag_service import _is_numbered_structural_clause


def test_numbered_final_clause_with_signature_tail_survives_model_validator():
    text = (
        "15.Any different interpretation of this Agreement by both Parties is subject to "
        "final interpretation by Party A. Party A: ZTO Express Co., Ltd. "
        "Party B:Tonglu Tongze Logistics Ltd. Company seal: /s/ ZTO Express Co., Ltd. "
        "Company seal: /s/ Tonglu Tongze Logistics Ltd. Date: December 22, 2014"
    )
    metadata = {"marker_kind": "TOP_LEVEL", "is_signature_metadata": False}
    assert _is_numbered_structural_clause(text, metadata) is True


def test_unmarked_signature_block_does_not_get_clause_override():
    text = "Party A: Name. Party B: Name. Company seal: /s/ A. Company seal: /s/ B."
    assert _is_numbered_structural_clause(text, {"marker_kind": "NONE"}) is False


def test_numbered_fragment_without_top_level_structure_does_not_get_override():
    assert _is_numbered_structural_clause("15. text", {"marker_kind": "NONE"}) is False
