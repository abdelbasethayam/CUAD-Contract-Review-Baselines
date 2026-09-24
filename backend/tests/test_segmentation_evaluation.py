from __future__ import annotations

from app.core.rag.segmentation_evaluation import (
    COMPACT_NUMBERED_MARKER_RE,
    SourceBlock,
    _heading,
    _marker,
    _metrics,
    _records_from_blocks,
)


def test_structural_markers_cover_top_level_nested_and_parenthesized_items():
    assert _marker("1. Main obligation") == "1."
    assert _marker("1.2 Nested obligation") == "1.2"
    assert _marker("(a) First item") == "(a)"
    assert _marker("Article IV. Definitions") == "Article IV."


def test_non_structural_prose_is_not_mistaken_for_a_clause_number():
    assert _marker("There are 2 parties to this agreement.") is None
    assert _heading("CONFIDENTIALITY") == "CONFIDENTIALITY"
    assert _heading("The receiving party shall protect information.") is None


def test_block_records_preserve_page_provenance_and_definition_metadata():
    records = _records_from_blocks(
        [
            SourceBlock("DEFINITIONS", 1, 1, "section_header", 0),
            SourceBlock('1.1 "Affiliate" means a related entity.', 1, 1, "paragraph", 1),
            SourceBlock("1.2 Term. This obligation continues after termination.", 1, 2, "paragraph", 2),
        ],
        "docling",
    )
    assert len(records) == 2
    assert records[0].clause_number == "1.1"
    assert records[0].validation["is_definition"] is True
    assert records[1].page_start == 1
    assert records[1].page_end == 2


def test_metrics_report_page_spans_and_suspicious_lengths():
    records = _records_from_blocks(
        [
            SourceBlock("1. Term. " + "x" * 140, 1, 2, "paragraph", 0),
            SourceBlock("2. Short.", 2, 2, "paragraph", 1),
        ],
        "hybrid",
    )
    metrics = _metrics(records, 0.25)
    assert metrics["page_spanning_clauses"] == 1
    assert metrics["short_clauses_under_120_chars"] == 1
    assert metrics["elapsed_seconds"] == 0.25


def test_hybrid_candidate_can_repair_compact_numbering_without_changing_baseline():
    text = "1.Party A shall perform the services described here. 2.Period is indefinite."
    normalized = COMPACT_NUMBERED_MARKER_RE.sub(
        lambda match: f"{match.group('marker')} ", text
    )
    assert normalized.startswith("1. Party")
    assert "2. Period" in normalized


def test_table_blocks_are_retained_as_structured_records():
    records = _records_from_blocks(
        [SourceBlock("Rate | Route | Effective date", 2, 2, "table", 0)],
        "docling",
    )
    assert len(records) == 1
    assert records[0].validation["label"] == "table"
