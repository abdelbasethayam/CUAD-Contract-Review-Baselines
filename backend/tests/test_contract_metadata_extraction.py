from app.core.risk.contract_metadata import extract_contract_metadata
from app.services.rag_service import _is_contract_header_metadata


def test_extracts_explicit_party_labels_and_contractual_terms_without_guessing_dates():
    segments = [
        {
            "clause_index": 0,
            "text": (
                "Road Transportation Agreement Party A (Shipper): ZTO Express Co., Ltd. "
                "Address: Building 1. Party B (Carrier): Tonglu Tongze Logistics Ltd. "
                "Address: 12 Floor."
            ),
        },
        {
            "clause_index": 2,
            "text": "Period of transportation services: this Agreement is valid for an indefinite term.",
        },
        {
            "clause_index": 12,
            "text": (
                "Any dispute arising out of this Agreement shall be subject to the jurisdiction "
                "of the People's Court where this Agreement is signed."
            ),
        },
        {
            "clause_index": 14,
            "text": "This Agreement takes effect upon the signatures and seals of both Parties in triplicate.",
        },
        {
            "clause_index": 4,
            "text": "Source: issuer F-1, 9/30/2016.",
        },
    ]

    metadata = extract_contract_metadata("transport.pdf", segments)

    assert metadata["parties"] == ["ZTO Express Co., Ltd", "Tonglu Tongze Logistics Ltd"]
    assert metadata["agreement_date"] is None  # SEC/source date is not an agreement date.
    assert metadata["effective_date"] is None
    assert "signatures and seals of both Parties" in metadata["effective_date_condition"]
    assert "indefinite term" in metadata["expiration_terms"]
    assert metadata["governing_law"] is None
    assert "People's Court" in metadata["dispute_forum"]
    assert "parties" in metadata["evidence"]


def test_party_block_is_document_metadata_not_a_substantive_clause():
    party_block = (
        "Road Transportation Agreement Party A (Shipper): ZTO Express Co., Ltd. "
        "Address: Building 1. Party B (Carrier): Tonglu Tongze Logistics Ltd. Address: 12 Floor."
    )
    assert _is_contract_header_metadata(party_block, 0) is True
    assert _is_contract_header_metadata("1. The carrier shall provide services.", 1) is False
    assert _is_contract_header_metadata(party_block, 1) is False

[executed on device: jupyter-group-digi2026-g6 (a8417900-e68e-4ee2-bbe7-fc3493ade5e1)]
