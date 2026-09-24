"""Contract-aware segmentation over structured parser blocks."""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from pathlib import Path

from .hybrid_parser import DocumentBlock, ParsedDocument, parse_document
from .segmenter import (
    _is_page_number_line,
    _looks_like_all_caps_title,
    _normalize_header_key,
    _normalize_line,
    _split_line_at_markers,
    _marker_for_text,
    is_definition,
)


LOGGER = logging.getLogger(__name__)


SIGNATURE_RE = re.compile(
    r"\b(?:party\s+[ab]|company\s+seal|signature|signed|name|title|date)\s*:",
    re.IGNORECASE,
)


@dataclass
class ClauseNode:
    clause_id: str
    clause_number: str | None
    heading: str | None
    text: str
    page_start: int | None
    page_end: int | None
    parser: str
    parent_clause: str | None = None
    depth: int = 0
    source_blocks: list[int] = field(default_factory=list)
    children: list["ClauseNode"] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class BoundaryDiagnostic:
    source_block: int
    page_start: int
    page_end: int
    character_offset: int
    marker: str | None
    marker_type: str
    previous_context: str
    next_context: str
    decision: str
    reason: str


@dataclass
class _ClauseAccumulator:
    text_parts: list[str] = field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    source_blocks: list[int] = field(default_factory=list)
    source_kinds: list[str] = field(default_factory=list)

    def append(self, text: str, block: DocumentBlock) -> None:
        if text:
            self.text_parts.append(text)
        self.page_start = block.page_start if self.page_start is None else min(self.page_start, block.page_start)
        self.page_end = block.page_end if self.page_end is None else max(self.page_end, block.page_end)
        if block.order not in self.source_blocks:
            self.source_blocks.append(block.order)
        if block.kind not in self.source_kinds:
            self.source_kinds.append(block.kind)

    @property
    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.text_parts)).strip()


def _is_signature(text: str) -> bool:
    matches = len(SIGNATURE_RE.findall(text))
    return matches >= 2 and len(text) < 800


def _marker_kind(marker: str | None) -> str:
    """Classify a marker without treating every parenthesis as a root."""
    if not marker:
        return "NONE"
    normalized = marker.strip()
    if re.fullmatch(r"\d+\.", normalized):
        return "TOP_LEVEL"
    if re.fullmatch(r"\d+(?:\.\d+)+\.?", normalized):
        return "NESTED_NUMBER"
    if re.fullmatch(r"\d+\s*\((?:[a-z]|[ivx]{1,6})\)", normalized, re.IGNORECASE):
        return "COMPOUND_CHILD"
    if re.fullmatch(r"\((?:i|v|x)+\)", normalized, re.IGNORECASE):
        return "ROMAN_CHILD"
    if re.fullmatch(r"\([a-z]\)", normalized, re.IGNORECASE):
        return "LETTER_CHILD"
    if normalized.lower().startswith(("section", "article")):
        return "SECTION"
    return "MARKER"


def _normalized_marker(marker: str | None) -> str | None:
    return marker.strip() if marker else None


def _compose_child_id(parent: ClauseNode, marker: str) -> str:
    """Give context-free subsection markers a stable, context-aware ID."""
    if parent.clause_id.endswith(".") and marker.startswith("("):
        return f"{parent.clause_id[:-1]}{marker}"
    return f"{parent.clause_id}{marker}"


def _parent_for_marker(
    marker: str | None,
    path: list[ClauseNode],
    by_id: dict[str, ClauseNode],
) -> ClauseNode | None:
    """Resolve a marker against the active structural path.

    Plain ``(a)``/``(b)`` markers are intentionally resolved from context:
    letters are siblings under the nearest numbered clause, while Roman
    markers are siblings under the nearest letter (or numbered clause when no
    letter is active). Explicit compound and dotted-number markers are looked
    up directly, so they remain deterministic even when a block is reordered.
    """
    if not marker:
        return path[-1] if path else None
    kind = _marker_kind(marker)
    if kind == "TOP_LEVEL" or kind == "SECTION":
        return None
    if kind == "COMPOUND_CHILD":
        match = re.match(r"^(\d+)\s*\(", marker)
        return by_id.get(f"{match.group(1)}.") if match else None
    if kind == "NESTED_NUMBER":
        number = marker.rstrip(".")
        parent_number = number.rsplit(".", 1)[0]
        return by_id.get(parent_number) or by_id.get(f"{parent_number}.")
    if kind == "ROMAN_CHILD":
        for node in reversed(path):
            if _marker_kind(node.clause_number) == "LETTER_CHILD":
                return node
        for node in reversed(path):
            if _marker_kind(node.clause_number) in {
                "TOP_LEVEL", "NESTED_NUMBER", "COMPOUND_CHILD", "SECTION", "NONE"
            }:
                return node
        return path[-1] if path else None
    if kind == "LETTER_CHILD":
        for node in reversed(path):
            if _marker_kind(node.clause_number) in {
                "TOP_LEVEL", "NESTED_NUMBER", "COMPOUND_CHILD", "SECTION", "NONE"
            }:
                return node
        return path[-1] if path else None
    return path[-1] if path else None


def _marker_type(marker: str | None) -> str:
    kind = _marker_kind(marker)
    return "PAREN_CHILD" if kind in {"LETTER_CHILD", "ROMAN_CHILD"} else kind


def _normalize_block_text(block: DocumentBlock) -> str:
    """Normalize one block without merging it with neighboring blocks."""
    lines = [_normalize_line(line) for line in block.text.replace("\r", "").split("\n")]
    lines = [line for line in lines if line and not _is_page_number_line(line)]
    return "\n".join(lines).strip()


def _clean_blocks(blocks: list[DocumentBlock]) -> list[DocumentBlock]:
    """Remove obvious page furniture while preserving block identity/order."""
    normalized: list[DocumentBlock] = []
    for block in blocks:
        value = _normalize_block_text(block)
        if not value:
            continue
        normalized.append(
            DocumentBlock(
                value,
                block.page_start,
                block.page_end,
                block.kind,
                block.order,
                block.label,
                block.parent_ref,
                block.indent,
            )
        )
    edge_keys: dict[str, set[int]] = {}
    page_groups: dict[int, list[DocumentBlock]] = {}
    for block in normalized:
        page_groups.setdefault(block.page_start, []).append(block)
    for page, page_blocks in page_groups.items():
        for block in page_blocks[:2] + page_blocks[-2:]:
            key = _normalize_header_key(block.text)
            if key:
                edge_keys.setdefault(key, set()).add(page)
    repeated = {key for key, pages in edge_keys.items() if len(pages) >= 2}
    cleaned: list[DocumentBlock] = []
    for block in normalized:
        key = _normalize_header_key(block.text)
        if block.label in {"page_header", "page_footer"}:
            continue
        if key in {"acc form", "road transportation agreement"} or _is_page_number_line(block.text):
            continue
        page_blocks = page_groups.get(block.page_start, [])
        is_edge = block in page_blocks[:2] or block in page_blocks[-2:]
        if is_edge and key in repeated and len(block.text) <= 180:
            continue
        cleaned.append(block)
    return cleaned


def _implicit_numbered_marker(
    block: DocumentBlock,
    text: str,
    next_number: int,
    group_bases: dict[str, float],
    body_indent: float | None,
    saw_numbered_clause: bool,
) -> str | None:
    """Recover compact list numbers Docling stores outside ``item.text``.

    Docling retains list-item groups and source geometry for the ZTO PDF, but
    its ``TextItem.text`` omits the compact labels (``1.Party``, ``2.Period``).
    Only an unmarked block at the base indentation of a known list/body is
    promoted. Indented blocks and ordinary preamble text are left untouched.
    """
    if block.kind == "table" or _marker_for_text(text):
        return None
    indent = block.indent
    if indent is None:
        return None
    group = block.parent_ref
    if block.label == "list_item" and group:
        base = group_bases.setdefault(group, indent)
        is_base_item = indent <= base + 2.0
    else:
        is_base_item = (
            saw_numbered_clause
            and body_indent is not None
            and indent <= body_indent + 2.0
        )
    return f"{next_number}." if is_base_item else None


def _accumulators_from_clauses(
    clauses: list[str], pages: list[tuple[int | None, int | None]]
) -> list[_ClauseAccumulator]:
    result: list[_ClauseAccumulator] = []
    for index, text in enumerate(clauses, start=1):
        page_start, page_end = pages[index - 1] if index - 1 < len(pages) else (None, None)
        result.append(
            _ClauseAccumulator(
                text_parts=[text],
                page_start=page_start,
                page_end=page_end,
                source_blocks=[],
            )
        )
    return result


def _build_nodes(
    clauses: list[str],
    pages: list[tuple[int | None, int | None]],
    parser: str,
) -> list[ClauseNode]:
    return _build_nodes_from_accumulators(
        _accumulators_from_clauses(clauses, pages), ParsedDocument([], parser)
    )


def _build_nodes_from_accumulators(
    accumulators: list[_ClauseAccumulator], parsed: ParsedDocument
) -> list[ClauseNode]:
    nodes: list[ClauseNode] = []
    path: list[ClauseNode] = []
    by_id: dict[str, ClauseNode] = {}
    for index, accumulator in enumerate(accumulators, start=1):
        text = accumulator.text
        marker = _normalized_marker(_marker_for_text(text))
        if len(text) < 40 and marker is None:
            continue
        parent = _parent_for_marker(marker, path, by_id)
        marker_kind = _marker_kind(marker)
        if parent and marker and marker_kind in {"LETTER_CHILD", "ROMAN_CHILD"}:
            clause_id = _compose_child_id(parent, marker)
        else:
            clause_id = marker or f"clause-{index}"
        if clause_id in by_id:
            suffix = 2
            base_id = clause_id
            while f"{base_id}#{suffix}" in by_id:
                suffix += 1
            clause_id = f"{base_id}#{suffix}"
        node = ClauseNode(
            clause_id=clause_id,
            clause_number=marker,
            heading=text if _looks_like_all_caps_title(text) else None,
            text=text,
            page_start=accumulator.page_start,
            page_end=accumulator.page_end,
            parser=parsed.parser,
            parent_clause=parent.clause_id if parent else None,
            depth=parent.depth + 1 if parent else 0,
            source_blocks=list(accumulator.source_blocks),
            metadata={
                "is_definition": is_definition(text),
                "is_signature_metadata": _is_signature(text),
                "has_structural_marker": marker is not None,
                "parser_fallback_reason": parsed.fallback_reason,
                "source_kinds": list(accumulator.source_kinds),
                "marker_kind": marker_kind,
            },
        )
        if parent:
            parent.children.append(node)
        else:
            nodes.append(node)
        by_id[node.clause_id] = node
        if parent:
            path = path[: path.index(parent) + 1]
        else:
            path = []
        path.append(node)
    return nodes


def _segment_blocks(
    blocks: list[DocumentBlock], parsed: ParsedDocument
) -> tuple[list[ClauseNode], list[BoundaryDiagnostic]]:
    accumulators: list[_ClauseAccumulator] = []
    current = _ClauseAccumulator()
    diagnostics: list[BoundaryDiagnostic] = []
    group_bases: dict[str, float] = {}
    next_implicit_number = 1
    body_indent: float | None = None
    saw_numbered_clause = False

    def flush() -> None:
        nonlocal current
        if current.text:
            accumulators.append(current)
        current = _ClauseAccumulator()

    for block in _clean_blocks(sorted(blocks, key=lambda item: item.order)):
        block_text = _normalize_block_text(block)
        if not block_text:
            continue
        explicit_marker = _marker_for_text(block_text)
        implicit_marker = _implicit_numbered_marker(
            block,
            block_text,
            next_implicit_number,
            group_bases,
            body_indent,
            saw_numbered_clause,
        )
        if implicit_marker:
            block_text = f"{implicit_marker} {block_text}"
            body_indent = block.indent if body_indent is None else min(body_indent, block.indent or body_indent)
            next_implicit_number += 1
            saw_numbered_clause = True
        elif explicit_marker:
            marker_kind = _marker_kind(explicit_marker)
            if marker_kind == "TOP_LEVEL":
                explicit_number = int(explicit_marker.rstrip("."))
                next_implicit_number = max(next_implicit_number, explicit_number + 1)
                saw_numbered_clause = True
                if block.indent is not None:
                    body_indent = block.indent if body_indent is None else min(body_indent, block.indent)
        block_offset = 0
        for raw_line in block_text.splitlines():
            line = _normalize_line(raw_line)
            # A table is one structured document element. Keep its rows with
            # the active clause instead of treating cell values as clauses.
            pieces = [line] if block.kind == "table" else _split_line_at_markers(line)
            line_offset = 0
            for piece_index, piece in enumerate(pieces):
                piece_offset = line.find(piece, line_offset)
                if piece_offset < 0:
                    piece_offset = line_offset
                absolute_offset = block_offset + piece_offset
                marker = _marker_for_text(piece)
                definition_continuation = bool(
                    current.text
                    and marker
                    and marker.startswith("(")
                    and is_definition(current.text)
                )
                starts_new = not definition_continuation and (
                    piece_index > 0 or (marker is not None and bool(current.text))
                )
                if starts_new and current.text:
                    flush()
                if marker is not None and not definition_continuation:
                    diagnostics.append(
                        BoundaryDiagnostic(
                            source_block=block.order,
                            page_start=block.page_start,
                            page_end=block.page_end,
                            character_offset=absolute_offset,
                            marker=marker,
                            marker_type=_marker_type(marker),
                            previous_context=block_text[max(0, absolute_offset - 100):absolute_offset],
                            next_context=block_text[absolute_offset:absolute_offset + 160],
                            decision="START_NEW_CLAUSE",
                            reason="structural contract marker detected inside ordered block",
                        )
                    )
                elif current.text:
                    diagnostics.append(
                        BoundaryDiagnostic(
                            source_block=block.order,
                            page_start=block.page_start,
                            page_end=block.page_end,
                            character_offset=absolute_offset,
                            marker=None,
                            marker_type="NONE",
                            previous_context=current.text[-100:],
                            next_context=piece[:160],
                            decision="APPEND_TO_CURRENT_CLAUSE",
                            reason="no structural boundary detected; continuation block",
                        )
                    )
                current.append(piece, block)
                line_offset = piece_offset + len(piece)
            block_offset += len(raw_line) + 1
    flush()
    return _build_nodes_from_accumulators(accumulators, parsed), diagnostics


def segment_document(
    file_path: Path, diagnostics: list[BoundaryDiagnostic] | None = None
) -> list[ClauseNode]:
    """Parse ordered blocks and segment them without flattening the document."""
    parsed = parse_document(file_path)
    nodes, trace = _segment_blocks(parsed.blocks, parsed)
    issues = validate_clause_tree(nodes)
    for node in nodes:
        node.metadata["validation_diagnostics"] = issues
    if issues:
        LOGGER.warning("Clause tree validation found %d issue(s): %s", len(issues), issues)
    if diagnostics is not None:
        diagnostics.extend(trace)
    return nodes


def validate_clause_tree(nodes: list[ClauseNode]) -> list[str]:
    """Return deterministic structural diagnostics before CUAD/RAG input."""
    issues: list[str] = []
    seen_text: set[str] = set()

    def visit(current_nodes: list[ClauseNode], parent: ClauseNode | None = None) -> None:
        seen_sibling_numbers: set[str] = set()
        for node in current_nodes:
            if parent is not None and node.parent_clause != parent.clause_id:
                issues.append(f"parent mismatch: {node.clause_id}")
            normalized = node.text.casefold().strip()
            if not normalized:
                issues.append(f"empty clause: {node.clause_id}")
            if normalized in seen_text:
                issues.append(f"duplicate clause text: {node.clause_id}")
            seen_text.add(normalized)
            if node.clause_number:
                sibling_key = node.clause_number.casefold()
                if sibling_key in seen_sibling_numbers:
                    issues.append(f"duplicate clause number: {node.clause_number}")
                seen_sibling_numbers.add(sibling_key)
            if len(node.text) > 12000:
                issues.append(f"suspiciously large clause: {node.clause_id}")
            if node.page_start is not None and parent is not None and parent.page_end is not None:
                if node.page_start < parent.page_start:
                    issues.append(f"page order mismatch: {node.clause_id}")
            visit(node.children, node)

    visit(nodes)
    return issues


def format_diagnostics(trace: list[BoundaryDiagnostic]) -> str:
    """Render the optional segmentation trace for debugging and regression review."""
    lines: list[str] = []
    for item in trace:
        lines.extend(
            [
                f"BLOCK {item.source_block}",
                f"PAGE {item.page_start}-{item.page_end}",
                f"OFFSET {item.character_offset}",
                f"MARKER: {item.marker!r}",
                f"TYPE: {item.marker_type}",
                f"CONTEXT: {item.previous_context!r} -> {item.next_context!r}",
                f"DECISION: {item.decision}",
                f"REASON: {item.reason}",
                "",
            ]
        )
    return "\n".join(lines)
