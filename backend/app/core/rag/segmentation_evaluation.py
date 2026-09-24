"""Isolated A/B/C evaluation prototype for contract segmentation.

This module provides three comparable representations:

* ``regex``: the current pdfplumber and deterministic segmenter;
* ``docling``: Docling's ordered document items and paragraph/heading
  boundaries, without applying the production regex splitter;
* ``hybrid``: Docling's ordered, page-aware blocks followed by deterministic
  boundary rules.

Docling is an optional evaluation dependency.  Keeping the import inside the
  Docling adapter means the production application remains installable and
  unchanged when Docling is not installed.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .segmenter import (
    _looks_like_all_caps_title,
    extract_page_layers,
    is_definition,
    split_into_clauses,
)


STRUCTURAL_MARKER_RE = re.compile(
    r"^\s*(?P<marker>(?:section|article)\s+(?:\d+(?:\.\d+)*|[ivxlcdm]+)\.?|"
    r"\d+(?:\.\d+)+\.?|\d{1,3}\.\s*|\((?:[a-z]|[ivx]{1,6})\))\s+",
    re.IGNORECASE,
)
INLINE_MARKER_RE = re.compile(
    r"(?<![\w.])(?:section|article)\s+(?:\d+(?:\.\d+)*|[ivxlcdm]+)\.?\s+|"
    r"(?<![\w.])\d+(?:\.\d+)+\.?\s+|(?<![\w.])\d{1,3}\.\s+|"
    r"(?<!\w)\((?:[a-z]|[ivx]{1,6})\)\s+",
    re.IGNORECASE,
)
COMPACT_NUMBERED_MARKER_RE = re.compile(r"(?<![\w.])(?P<marker>\d{1,3}\.)(?=[A-Z(\"\u201c])")


@dataclass
class ClauseRecord:
    """Normalized clause output shared by all evaluation approaches."""

    clause_id: str
    clause_number: str | None
    heading: str | None
    text: str
    page_start: int | None
    page_end: int | None
    source: str
    validation: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceBlock:
    text: str
    page_start: int | None
    page_end: int | None
    label: str = "text"
    order: int = 0


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u00a0", " ")).strip()


def _marker(text: str) -> str | None:
    match = STRUCTURAL_MARKER_RE.match(text)
    return match.group("marker").strip() if match else None


def _heading(text: str, label: str = "") -> str | None:
    normalized = _clean_text(text)
    label = label.lower()
    if "heading" in label or "title" in label or _looks_like_all_caps_title(normalized):
        return normalized
    return None


def _page_for_offset(page_spans: list[tuple[int, int, int]], offset: int) -> int | None:
    for start, end, page in page_spans:
        if start <= offset < end:
            return page
    if page_spans and offset >= page_spans[-1][0]:
        return page_spans[-1][2]
    return None


def _records_from_text_pages(pages: list[str], source: str) -> list[ClauseRecord]:
    """Build Regex records and retain approximate page provenance."""
    flattened_parts: list[str] = []
    spans: list[tuple[int, int, int]] = []
    cursor = 0
    for page_number, page in enumerate(pages, start=1):
        page = page.strip()
        if not page:
            continue
        start = cursor
        flattened_parts.append(page)
        cursor += len(page)
        spans.append((start, cursor, page_number))
        flattened_parts.append("\n\n")
        cursor += 2
    flattened = "".join(flattened_parts)
    clauses = split_into_clauses(flattened)
    records: list[ClauseRecord] = []
    search_from = 0
    for index, clause in enumerate(clauses, start=1):
        position = flattened.find(clause[: min(120, len(clause))], search_from)
        if position < 0:
            position = search_from
        end = position + len(clause)
        page_start = _page_for_offset(spans, position)
        page_end = _page_for_offset(spans, max(position, end - 1))
        marker = _marker(clause)
        records.append(
            ClauseRecord(
                clause_id=f"{source}-{index:04d}",
                clause_number=marker,
                heading=_heading(clause),
                text=clause,
                page_start=page_start,
                page_end=page_end,
                source=source,
                validation={
                    "is_definition": is_definition(clause),
                    "has_structural_marker": marker is not None,
                },
            )
        )
        search_from = min(len(flattened), max(position + 1, end))
    return records


def regex_records(file_path: Path) -> list[ClauseRecord]:
    layers = extract_page_layers(file_path)
    return _records_from_text_pages(layers["cleaned_pages"], "regex")


def _docling_page_numbers(item: Any) -> tuple[int | None, int | None]:
    pages: list[int] = []
    for provenance in getattr(item, "prov", []) or []:
        page = getattr(provenance, "page_no", None)
        if page is not None:
            pages.append(int(page))
    return (min(pages), max(pages)) if pages else (None, None)


def _docling_label(item: Any) -> str:
    label = getattr(item, "label", "text")
    return str(getattr(label, "value", label))


def _docling_item_text(item: Any) -> str:
    text = getattr(item, "text", None)
    if text:
        return _clean_text(str(text))
    exporter = getattr(item, "export_to_markdown", None)
    if callable(exporter):
        return _clean_text(str(exporter()))
    return ""


def docling_blocks(file_path: Path) -> list[SourceBlock]:
    """Convert Docling's ordered document items to page-aware blocks."""
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except ImportError as exc:  # pragma: no cover - exercised by CLI/runtime
        raise RuntimeError(
            "Docling is not installed. Install evaluation/requirements-docling.txt "
            "in the evaluation environment."
        ) from exc

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = False
    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        },
    )
    result = converter.convert(str(file_path))
    document = result.document
    blocks: list[SourceBlock] = []
    items: Iterable[Any] = getattr(document, "texts", []) or []
    for order, item in enumerate(items):
        text = _docling_item_text(item)
        if not text:
            continue
        page_start, page_end = _docling_page_numbers(item)
        blocks.append(SourceBlock(text, page_start, page_end, _docling_label(item), order))

    # Tables are included as structured blocks when the Docling version exposes
    # them separately.  They remain one block so downstream evaluation can
    # measure whether table content was retained without inventing row clauses.
    for order, item in enumerate(getattr(document, "tables", []) or [], start=len(blocks)):
        text = _docling_item_text(item)
        if text:
            page_start, page_end = _docling_page_numbers(item)
            blocks.append(SourceBlock(text, page_start, page_end, "table", order))
    return sorted(blocks, key=lambda block: block.order)


def _records_from_blocks(blocks: list[SourceBlock], source: str) -> list[ClauseRecord]:
    records: list[ClauseRecord] = []
    pending_heading: str | None = None
    for block in blocks:
        text = _clean_text(block.text)
        if not text:
            continue
        heading = _heading(text, block.label)
        if heading and len(text) < 180:
            pending_heading = heading
            continue
        marker = _marker(text)
        record_heading = heading
        if pending_heading:
            if marker:
                record_heading = pending_heading
            else:
                text = f"{pending_heading} {text}"
            pending_heading = None
        records.append(
            ClauseRecord(
                clause_id=f"{source}-{len(records) + 1:04d}",
                clause_number=marker,
                heading=record_heading,
                text=text,
                page_start=block.page_start,
                page_end=block.page_end,
                source=source,
                validation={
                    "label": block.label,
                    "is_definition": is_definition(text),
                    "has_structural_marker": marker is not None,
                },
            )
        )
    return records


def docling_records(file_path: Path) -> list[ClauseRecord]:
    return _records_from_blocks(docling_blocks(file_path), "docling")


def hybrid_records(file_path: Path) -> list[ClauseRecord]:
    blocks = docling_blocks(file_path)
    records: list[ClauseRecord] = []
    for block in blocks:
        # Some PDFs extract legal numbering without the space after the
        # marker (for example ``1.Party``).  Keep this repair in the isolated
        # hybrid candidate so the production baseline remains unchanged.
        normalized_block = COMPACT_NUMBERED_MARKER_RE.sub(
            lambda match: f"{match.group('marker')} ", block.text
        )
        pieces = split_into_clauses(normalized_block)
        if not pieces:
            continue
        for piece in pieces:
            marker = _marker(piece)
            records.append(
                ClauseRecord(
                    clause_id=f"hybrid-{len(records) + 1:04d}",
                    clause_number=marker,
                    heading=_heading(piece, block.label),
                    text=piece,
                    page_start=block.page_start,
                    page_end=block.page_end,
                    source="hybrid",
                    validation={
                        "docling_label": block.label,
                        "is_definition": is_definition(piece),
                        "has_structural_marker": marker is not None,
                    },
                )
            )
    return records


def _metrics(records: list[ClauseRecord], elapsed_seconds: float) -> dict[str, Any]:
    texts = [record.text for record in records]
    markers = [record.clause_number for record in records if record.clause_number]
    page_spans = sum(
        1
        for record in records
        if record.page_start is not None and record.page_end is not None and record.page_end > record.page_start
    )
    return {
        "clauses": len(records),
        "definitions": sum(record.validation.get("is_definition", False) for record in records),
        "marked_clauses": len(markers),
        "page_spanning_clauses": page_spans,
        "short_clauses_under_120_chars": sum(len(text) < 120 for text in texts),
        "oversized_clauses_over_3000_chars": sum(len(text) > 3000 for text in texts),
        "header_footer_suspect_count": sum(
            any(token in text.lower() for token in ("page ", "acc form")) for text in texts
        ),
        "elapsed_seconds": round(elapsed_seconds, 3),
    }


def evaluate_file(file_path: Path, include_docling: bool = True) -> dict[str, Any]:
    approaches: dict[str, Any] = {}
    started = time.perf_counter()
    regex = regex_records(file_path)
    approaches["regex"] = {
        "metrics": _metrics(regex, time.perf_counter() - started),
        "clauses": [asdict(record) for record in regex],
    }
    if not include_docling:
        return {"file": str(file_path), "approaches": approaches}

    for name, builder in (("docling", docling_records), ("hybrid", hybrid_records)):
        started = time.perf_counter()
        try:
            records = builder(file_path)
            approaches[name] = {
                "metrics": _metrics(records, time.perf_counter() - started),
                "clauses": [asdict(record) for record in records],
            }
        except Exception as exc:
            approaches[name] = {"available": False, "error": str(exc)}
    return {"file": str(file_path), "approaches": approaches}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/segmentation/evaluation.json"))
    parser.add_argument("--without-docling", action="store_true")
    args = parser.parse_args()
    report = {
        "methodology": {
            "ground_truth": "none; metrics are structural proxies and require manual review",
            "approaches": ["regex", "docling", "hybrid"],
        },
        "files": [evaluate_file(path, not args.without_docling) for path in args.files],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
