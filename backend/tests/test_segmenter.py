from __future__ import annotations

from pathlib import Path

from app.core.rag.segmenter import (
    _strip_page_furniture,
    is_definition,
    is_footnote,
    split_into_clauses,
)


def test_inline_definitions_are_separate() -> None:
    text = (
        '1. DEFINITIONS 1.1 "Affiliate" means a related entity with control. '
        '1.2 "Application Platform" means the hosted software and services. '
        '1.3 "Cardholder Data" means payment-card information handled under law.'
    )
    clauses = split_into_clauses(text)
    definitions = [clause for clause in clauses if is_definition(clause)]
    assert len(definitions) == 3
    assert [clause.split()[0] for clause in definitions] == ["1.1", "1.2", "1.3"]


def test_numbered_clauses_split_at_line_starts() -> None:
    text = """2.1 Term. This is a sufficiently long legal provision for the term.
2.2 Renewal. This is another sufficiently long legal provision for renewal.
2.3 Termination. This is a third sufficiently long legal provision for termination."""
    clauses = split_into_clauses(text)
    assert len(clauses) == 3
    assert [clause.split()[0] for clause in clauses] == ["2.1", "2.2", "2.3"]


def test_compact_numbered_clauses_split_after_sentence_boundaries() -> None:
    text = (
        "1.Party A shall provide the services described in this agreement. "
        "2.Period of service is indefinite. 3.Freight is paid monthly."
    )
    clauses = split_into_clauses(text)
    assert len(clauses) == 3
    assert [clause.split()[0] for clause in clauses] == ["1.", "2.", "3."]


def test_inline_enumeration_splits_when_context_is_explicit() -> None:
    text = (
        "The following applies: (a) The first obligation is sufficiently detailed "
        "for a contract. (b) The second obligation is also sufficiently detailed "
        "for a contract. (c) The third obligation is also sufficiently detailed "
        "for a contract."
    )
    clauses = split_into_clauses(text)
    assert len(clauses) == 3
    assert [clause[:3] for clause in clauses] == ["(a)", "(b)", "(c)"]


def test_drafting_footnote_is_removed_without_removing_next_clause() -> None:
    text = """2.1 Term. This is a valid clause with enough legal text to keep.
1 This form is fairly generic and is drafting commentary.
2.2 Renewal. This is another valid clause with enough legal text to keep."""
    clauses = split_into_clauses(text)
    assert len(clauses) == 2
    assert all(not is_footnote(clause) for clause in clauses)
    assert all("fairly generic" not in clause for clause in clauses)


def test_repeated_page_edge_furniture_is_removed() -> None:
    pages = [
        "The Information is made available for general informational purposes only.\n"
        "2.1 Term. This is a clause on page one.\nPage 1 of 3",
        "The Information is made available for general informational purposes only.\n"
        "2.2 Renewal. This is a clause on page two.\nPage 2 of 3",
        "The Information is made available for general informational purposes only.\n"
        "2.3 Termination. This is a clause on page three.\nPage 3 of 3",
    ]
    cleaned = _strip_page_furniture(pages)
    assert all("Information is made available" not in page for page in cleaned)
    assert all("Page " not in page for page in cleaned)
    assert "2.1 Term" in cleaned[0]


def test_all_caps_heading_stays_with_following_substantive_text() -> None:
    clauses = split_into_clauses(
        "CONFIDENTIALITY\nThe Receiving Party shall protect Confidential Information "
        "and use it only for the permitted purpose described here."
    )
    assert len(clauses) == 1
    assert clauses[0].startswith("CONFIDENTIALITY The Receiving Party")


def test_long_unstructured_text_uses_fallback() -> None:
    sentence = "The provider shall maintain commercially reasonable safeguards and notify the client."
    clauses = split_into_clauses(" ".join([sentence] * 80))
    assert len(clauses) > 1
    assert max(map(len, clauses)) <= 3000


def test_normal_prose_is_not_over_split() -> None:
    text = (
        "The parties agree that the service will be provided in accordance with this Agreement. "
        "The provider will maintain reasonable security controls and notify the client of material incidents."
    )
    clauses = split_into_clauses(text)
    assert len(clauses) == 1
    assert "there are 2 parties" not in clauses[0]


def test_extract_text_txt_preserves_supported_path(tmp_path: Path) -> None:
    from app.core.rag.segmenter import extract_text

    source = tmp_path / "contract.txt"
    source.write_text("2.1 Term. This is a legal clause with enough text.", encoding="utf-8")
    assert "2.1 Term" in extract_text(source)
