from __future__ import annotations

from pathlib import Path

import pytest

from app.core.rag.clause_segmenter import (
    _build_nodes,
    _segment_blocks,
    format_diagnostics,
    segment_document,
    validate_clause_tree,
)
from app.core.rag.hybrid_parser import DocumentBlock, ParsedDocument


ZTO_PDF = (
    Path(__file__).resolve().parents[2]
    / "ZtoExpressCaymanInc_20160930_F-1_EX-10.10_9752871_EX-10.10_Transportation Agreement.pdf"
)


def test_hierarchy_preserves_compound_parentheses():
    nodes = _build_nodes(
        [
            "5. Obligations are described in this section and remain binding.",
            "5(a) Party A shall provide the required information and notices.",
            "5(b) Party B shall perform the services in accordance with the agreement.",
        ],
        [(1, 1), (1, 1), (1, 1)],
        "docling",
    )
    assert len(nodes) == 1
    assert nodes[0].clause_id == "5."
    assert [child.clause_id for child in nodes[0].children] == ["5(a)", "5(b)"]


def test_plain_letter_subsections_attach_to_numbered_parent():
    nodes = _build_nodes(
        [
            "5. Obligations are described in this section and remain binding on both parties.",
            "(a) Party A shall provide the required information and notices without delay.",
            "(b) Party B shall perform the services in accordance with the agreement.",
            "(c) The carrier shall maintain records for the duration of the agreement.",
        ],
        [(1, 1)] * 4,
        "docling",
    )
    assert [node.clause_id for node in nodes] == ["5."]
    assert [child.clause_number for child in nodes[0].children] == ["(a)", "(b)", "(c)"]
    assert [child.parent_clause for child in nodes[0].children] == ["5."] * 3
    assert validate_clause_tree(nodes) == []


def test_repeated_subsection_markers_are_scoped_to_parent():
    nodes = _build_nodes(
        [
            "5. Obligations are described in this section and remain binding on both parties.",
            "(a) Party A shall provide the required information and notices without delay.",
            "(b) Party B shall perform the services in accordance with the agreement.",
            "6. Insurance obligations are described in this section and remain binding on both parties.",
            "(a) Party A shall maintain insurance coverage throughout the agreement.",
            "(b) Party B shall provide proof of coverage upon request.",
        ],
        [(1, 1)] * 6,
        "docling",
    )
    assert [node.clause_id for node in nodes] == ["5.", "6."]
    assert [child.clause_id for child in nodes[0].children] == ["5(a)", "5(b)"]
    assert [child.clause_id for child in nodes[1].children] == ["6(a)", "6(b)"]
    assert validate_clause_tree(nodes) == []


def test_nested_roman_subsections_attach_to_letter_subsection():
    nodes = _build_nodes(
        [
            "5. Obligations are described in this section and remain binding on both parties.",
            "(a) Party A shall provide the required information and notices without delay.",
            "(i) The information must be complete and accurate when delivered.",
            "(ii) The notices must be delivered using the agreed method.",
            "(b) Party B shall perform the services in accordance with the agreement.",
        ],
        [(1, 1)] * 5,
        "docling",
    )
    root = nodes[0]
    assert [child.clause_number for child in root.children] == ["(a)", "(b)"]
    assert [child.clause_number for child in root.children[0].children] == ["(i)", "(ii)"]
    assert [child.parent_clause for child in root.children[0].children] == ["5(a)"] * 2
    assert validate_clause_tree(nodes) == []


def test_text_document_uses_text_parser_and_keeps_same_line_boundaries(tmp_path: Path):
    source = tmp_path / "contract.txt"
    source.write_text(
        "1. Party A shall provide services under this agreement. "
        "2. Party B shall pay the agreed fees and expenses.",
        encoding="utf-8",
    )
    nodes = segment_document(source)
    assert [node.clause_number for node in nodes] == ["1.", "2."]
    assert all(node.parser == "text" for node in nodes)
    assert all(node.page_start == 1 and node.page_end == 1 for node in nodes)


def test_signature_metadata_is_marked_without_being_classified():
    nodes = _build_nodes(
        ["Party A: Name: Signature: Date: Party B: Name: Signature: Date:"],
        [(3, 3)],
        "docling",
    )
    assert nodes[0].metadata["is_signature_metadata"] is True


def test_one_docling_block_splits_same_line_top_level_clauses():
    parsed = ParsedDocument(
        [
            DocumentBlock(
                "1.Party B shall provide transportation services under this agreement. "
                "2.Period of transportation is indefinite. "
                "3.Freight and payment method are agreed by the parties.",
                1,
                1,
                "text",
                17,
            )
        ],
        "docling",
    )
    nodes, trace = _segment_blocks(parsed.blocks, parsed)
    assert [node.clause_number for node in nodes] == ["1.", "2.", "3."]
    assert all(node.source_blocks == [17] for node in nodes)
    assert [item.marker for item in trace if item.decision == "START_NEW_CLAUSE"] == [
        "1.",
        "2.",
        "3.",
    ]
    assert "BLOCK 17" in format_diagnostics(trace)


def test_docling_list_structure_recovers_omitted_compact_numbers():
    parsed = ParsedDocument(
        [
            DocumentBlock(
                "Party B shall provide transportation services under this agreement.",
                1,
                1,
                "text",
                1,
                "list_item",
                "#/groups/0",
                50.0,
            ),
            DocumentBlock(
                "Period of transportation services is indefinite under this agreement.",
                1,
                1,
                "text",
                2,
                "list_item",
                "#/groups/0",
                50.0,
            ),
            DocumentBlock(
                "Freight and payment method:",
                1,
                1,
                "text",
                3,
                "list_item",
                "#/groups/0",
                50.0,
            ),
            DocumentBlock(
                "(a) Party A shall pay the agreed freight and related charges.",
                1,
                1,
                "text",
                4,
                "list_item",
                "#/groups/0",
                80.0,
            ),
        ],
        "docling",
    )
    nodes, _ = _segment_blocks(parsed.blocks, parsed)
    assert [node.clause_number for node in nodes] == ["1.", "2.", "3."]
    assert [child.clause_id for child in nodes[2].children] == ["3(a)"]


def test_continuation_block_and_table_stay_with_active_clause():
    parsed = ParsedDocument(
        [
            DocumentBlock("5. Party B shall provide transportation services", 1, 1, "text", 1),
            DocumentBlock("according to the requirements of Party A and applicable law.", 2, 2, "text", 2),
            DocumentBlock("Route | Time | Requirement\nA | 08:00 | Required", 2, 2, "table", 3),
            DocumentBlock("6. Party B shall purchase sufficient insurance coverage.", 3, 3, "text", 4),
        ],
        "docling",
    )
    nodes, _ = _segment_blocks(parsed.blocks, parsed)
    assert nodes[0].clause_number == "5."
    assert nodes[0].page_start == 1
    assert nodes[0].page_end == 2
    assert nodes[0].source_blocks == [1, 2, 3]
    assert "Route" in nodes[0].text
    assert nodes[1].clause_number == "6."


def test_newline_inside_one_block_preserves_continuation_and_boundary():
    parsed = ParsedDocument(
        [
            DocumentBlock(
                "5. Party B shall provide transportation services\n"
                "according to the requirements of Party A.\n"
                "6. Party B shall purchase sufficient insurance coverage.",
                1,
                1,
                "text",
                7,
            )
        ],
        "docling",
    )
    nodes, _ = _segment_blocks(parsed.blocks, parsed)
    assert [node.clause_number for node in nodes] == ["5.", "6."]
    assert "according to the requirements" in nodes[0].text


def test_references_are_not_structural_boundaries():
    parsed = ParsedDocument(
        [
            DocumentBlock(
                "1. The parties will comply with Section 5.2 of this Agreement "
                "and will provide notice within 30 days.",
                1,
                1,
                "text",
                1,
            )
        ],
        "docling",
    )
    nodes, _ = _segment_blocks(parsed.blocks, parsed)
    assert len(nodes) == 1
    assert "Section 5.2" in nodes[0].text


@pytest.mark.skipif(not ZTO_PDF.exists(), reason="ZTO regression PDF is not present")
def test_zto_top_level_clauses_do_not_collapse_into_three_records():
    nodes = segment_document(ZTO_PDF)
    numbers = {
        node.clause_number.rstrip(".")
        for node in nodes
        if node.clause_number and node.clause_number.rstrip(".").isdigit()
    }
    assert {str(number) for number in range(1, 16)} <= numbers
    assert len(nodes) > 3
