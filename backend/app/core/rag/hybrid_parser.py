"""Optional Docling extraction used by the production hybrid parser.

Docling is intentionally optional.  Callers should catch ``ImportError`` or
runtime conversion errors and use the pdfplumber fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
from pathlib import Path


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocumentBlock:
    """One ordered, page-aware element from the document parser."""

    text: str
    page_start: int
    page_end: int
    kind: str = "text"
    order: int = 0
    label: str | None = None
    parent_ref: str | None = None
    indent: float | None = None


@dataclass
class ParsedDocument:
    """Structured parser output consumed by the clause segmenter."""

    blocks: list[DocumentBlock] = field(default_factory=list)
    parser: str = "unknown"
    fallback_reason: str | None = None


def _text(item: object) -> str:
    value = getattr(item, "text", None)
    if value:
        return " ".join(str(value).split())
    exporter = getattr(item, "export_to_markdown", None)
    if callable(exporter):
        return " ".join(str(exporter()).split())
    return ""


def _pages(item: object) -> list[int]:
    result: list[int] = []
    for provenance in getattr(item, "prov", []) or []:
        page_number = getattr(provenance, "page_no", None)
        if page_number is not None:
            result.append(int(page_number))
    return result


def _docling_label(item: object) -> str | None:
    value = getattr(item, "label", None)
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _docling_parent_ref(item: object) -> str | None:
    parent = getattr(item, "parent", None)
    value = getattr(parent, "cref", None)
    return str(value) if value else None


def _docling_indent(item: object) -> float | None:
    provenance = next(iter(getattr(item, "prov", []) or []), None)
    bbox = getattr(provenance, "bbox", None)
    left = getattr(bbox, "l", None)
    return float(left) if left is not None else None


def _docling_document(file_path: Path) -> ParsedDocument:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions()
    options.do_ocr = False
    options.do_table_structure = True
    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=options),
        },
    )
    document = converter.convert(str(file_path)).document
    blocks: list[DocumentBlock] = []
    items = list(getattr(document, "texts", []) or [])
    tables = list(getattr(document, "tables", []) or [])
    for order, item in enumerate(items + tables):
        value = _text(item)
        pages = _pages(item)
        if value and pages:
            label = "table" if order >= len(items) else "text"
            blocks.append(DocumentBlock(
                value,
                min(pages),
                max(pages),
                label,
                order,
                _docling_label(item),
                _docling_parent_ref(item),
                _docling_indent(item),
            ))
    return ParsedDocument(sorted(blocks, key=lambda block: block.order), "docling")


def _pdfplumber_document(file_path: Path, reason: str | None = None) -> ParsedDocument:
    import pdfplumber

    blocks: list[DocumentBlock] = []
    with pdfplumber.open(file_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                blocks.append(DocumentBlock(text, page_number, page_number, "fallback", page_number))
    return ParsedDocument(blocks, "pdfplumber-fallback", reason)


def parse_document(file_path: Path) -> ParsedDocument:
    """Parse PDF structure with Docling and use an explicit local fallback."""
    if file_path.suffix.lower() == ".txt":
        return ParsedDocument(
            [DocumentBlock(file_path.read_text(encoding="utf-8", errors="ignore"), 1, 1, "text", 0)],
            "text",
        )
    if file_path.suffix.lower() != ".pdf":
        raise ValueError(f"Unsupported file type: {file_path.suffix}")
    mode = os.getenv("CONTRACT_PARSER", "hybrid").strip().lower()
    if mode not in {"hybrid", "docling", "regex"}:
        raise ValueError("CONTRACT_PARSER must be hybrid, docling, or regex")
    if mode == "regex":
        return _pdfplumber_document(file_path, "CONTRACT_PARSER=regex")
    try:
        parsed = _docling_document(file_path)
        if parsed.blocks:
            return parsed
        raise RuntimeError("Docling returned no structured document blocks")
    except Exception as exc:
        if mode == "docling":
            raise RuntimeError(
                "Docling parser requested but unavailable or unable to parse the PDF."
            ) from exc
        LOGGER.warning("Docling parsing failed for %s; using pdfplumber fallback: %s", file_path, exc)
        return _pdfplumber_document(file_path, str(exc))


def extract_docling_pages(file_path: Path) -> list[str]:
    """Return Docling's ordered text grouped by source page.

    Tables are retained as blocks, but their rows are not treated as clauses;
    deterministic segmentation remains responsible for legal boundaries.
    """
    parsed = _docling_document(file_path)
    if not parsed.blocks:
        return []
    last_page = max(block.page_end for block in parsed.blocks)
    pages = [[] for _ in range(last_page)]
    for block in parsed.blocks:
        pages[block.page_start - 1].append(block.text)
    return ["\n".join(page) for page in pages]
