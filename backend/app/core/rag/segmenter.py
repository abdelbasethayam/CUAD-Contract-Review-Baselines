"""Page-aware PDF extraction and structure-aware contract segmentation.

The public API remains ``extract_text(Path) -> str`` and
``split_into_clauses(str) -> list[str]``. Internally, PDF pages are cleaned
before they are flattened so page furniture cannot be mistaken for contract
text and structural markers can be recognized in the middle of extracted
lines.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path



HEADER_FOOTER_MIN_PAGE_FRACTION = 0.5
MIN_CLAUSE_CHARS = 40
LONG_CLAUSE_FALLBACK_THRESHOLD = 3000

PAGE_NUMBER_RE = re.compile(
    r"^\s*(?:page\s+)?\d{1,4}(?:\s+of\s+\d{1,4})?\s*$",
    re.IGNORECASE,
)

# Structural markers are deliberately conservative about the text following
# a marker. This avoids treating ordinary prose such as "there are 2 parties"
# as a clause boundary.
NUMBERED_MARKER_RE = re.compile(
    r"(?<![\w.])(?P<marker>\d+(?:\.\d+)+\.?|\d{1,3}\.)"
    r"\s+(?=[\"\u201c\u2018'A-Z(])"
)
SECTION_MARKER_RE = re.compile(
    r"(?<!\w)(?P<marker>(?:SECTION|ARTICLE)\s+"
    r"(?:\d+(?:\.\d+)*|[IVXLCDM]+)\.?)\s+"
    r"(?=[\"\u201c\u2018'A-Z(])",
    re.IGNORECASE,
)
PAREN_MARKER_RE = re.compile(
    r"(?<!\w)(?P<marker>\((?:[a-z]|[ivx]{1,6})\))"
    r"\s+(?=[\"\u201c\u2018'A-Z(])",
    re.IGNORECASE,
)
COMPOUND_PAREN_MARKER_RE = re.compile(
    r"(?<![\w.])(?P<marker>\d+\s*\((?:[a-z]|[ivx]{1,6})\))"
    r"\s+(?=[\"\u201c\u2018'A-Z(])",
    re.IGNORECASE,
)
COMPACT_NUMBERED_MARKER_RE = re.compile(
    r"(?<![\w.])(?P<marker>\d{1,3}\.)(?=[\"\u201c\u2018'A-Z(])"
)

# Compatibility constant for code that imported the old matcher.
SECTION_HEADER_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)+\.?|\d+\.|\([a-zA-Z]\)|"
    r"(?:SECTION|ARTICLE)\s+(?:\d+(?:\.\d+)*|[IVXLCDM]+)\.?)\s+\S",
    re.IGNORECASE,
)

ALL_CAPS_HEADER_RE = re.compile(
    r"^\s*(?:[A-Z][A-Z&/\-]*\s+){0,7}[A-Z][A-Z&/\-]*\.?\s*$"
)

FOOTNOTE_LINE_RE = re.compile(r"^\s*\d{1,2}(?![.\d])\s+")
FOOTNOTE_CUES = (
    "this form",
    "this agreement gives",
    "the provider",
    "provider may",
    "the customer",
    "customer may",
    "the parties",
    "parties need",
    "would need",
    "should be",
    "should consider",
    "generally",
    "pre-approved",
    "end user data-related",
)
PAGE_FURNITURE_HINTS = {"acc form"}

DEFINITION_RE = re.compile(
    r'^\d+\.\d+\s+["\u201c].{1,260}?(?:means?|has the meaning|is an?\b|is defined as)\b',
    re.IGNORECASE,
)

INLINE_SUBITEM_RE = re.compile(r"(?=\s\((?:[a-z]|[ivx]{1,6})\)\s)", re.IGNORECASE)
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.;])\s+(?=[A-Z(\"\u201c])")


def _normalize_line(line: str) -> str:
    line = line.replace("\u00a0", " ").replace("\u200b", "")
    return re.sub(r"[ \t]+", " ", line).strip()


def _looks_like_all_caps_title(line: str) -> bool:
    stripped = _normalize_line(line)
    if not ALL_CAPS_HEADER_RE.fullmatch(stripped):
        return False
    if len(stripped) < 6 or len(stripped) > 100:
        return False
    if any(ch.isdigit() for ch in stripped):
        return False
    words = stripped.rstrip(".").split()
    return 1 <= len(words) <= 8


def _is_page_number_line(line: str) -> bool:
    return bool(PAGE_NUMBER_RE.fullmatch(_normalize_line(line)))


def _is_structural_start(line: str) -> bool:
    line = _normalize_line(line)
    if not line:
        return False
    if re.match(
        r"^(?:section|article)\s+\d+(?:\.\d+)*\s+\(",
        line,
        re.IGNORECASE,
    ):
        return False
    if COMPOUND_PAREN_MARKER_RE.match(line):
        return True
    if SECTION_HEADER_RE.match(line):
        return True
    if (
        NUMBERED_MARKER_RE.match(line)
        or COMPACT_NUMBERED_MARKER_RE.match(line)
        or PAREN_MARKER_RE.match(line)
    ):
        return True
    return _looks_like_all_caps_title(line)


def _looks_like_footnote_start(line: str, index: int = 0, total: int = 0) -> bool:
    """Identify drafting notes without treating ordinary numbered prose as one."""
    normalized = _normalize_line(line)
    match = FOOTNOTE_LINE_RE.match(normalized)
    if not match or _is_structural_start(normalized):
        return False
    body = normalized[match.end() :].lower()
    if any(cue in body for cue in FOOTNOTE_CUES):
        return True
    return bool(total and index >= max(0, int(total * 0.6)) and len(body) <= 240)


def is_footnote(text: str) -> bool:
    """Return whether text begins with a likely drafting-note footnote."""
    return _looks_like_footnote_start(text)


def is_definition(text: str) -> bool:
    """Return whether text begins with a defined-term entry."""
    return bool(DEFINITION_RE.match(_normalize_line(text)))


def _marker_for_text(text: str) -> str | None:
    """Return a leading legal marker for hierarchy and diagnostics."""
    normalized = _normalize_line(text)
    for pattern in (
        COMPOUND_PAREN_MARKER_RE,
        SECTION_MARKER_RE,
        NUMBERED_MARKER_RE,
        COMPACT_NUMBERED_MARKER_RE,
        PAREN_MARKER_RE,
    ):
        match = pattern.match(normalized)
        if match:
            marker = match.groupdict().get("marker")
            return marker.strip() if marker else match.group(0).strip()
    return None


def _normalize_header_key(line: str) -> str:
    value = _normalize_line(line).lower()
    value = re.sub(r"^page\s*\d+(?:\s*of\s*\d+)?[:\-–—]?\s*", "", value)
    value = re.sub(r"[^a-z0-9 ]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _strip_page_furniture(pages: list[str]) -> list[str]:
    """Remove repeated edge furniture using page-frequency evidence."""
    if not pages:
        return pages

    normalized_pages = [[_normalize_line(line) for line in page.splitlines()] for page in pages]
    candidates: list[tuple[int, int, str]] = []
    for page_index, lines in enumerate(normalized_pages):
        edge_indices = set(range(min(6, len(lines))))
        edge_indices.update(range(max(0, len(lines) - 6), len(lines)))
        for line_index in sorted(edge_indices):
            line = lines[line_index]
            key = _normalize_header_key(line)
            if key and not _is_page_number_line(line) and len(key) <= 180:
                candidates.append((page_index, line_index, key))

    groups: list[dict] = []
    for page_index, line_index, key in candidates:
        group = None
        for existing in groups:
            same_edge = (line_index < 6) == (existing["line_index"] < 6)
            similar = difflib.SequenceMatcher(None, key, existing["representative"]).ratio() >= 0.90
            if same_edge and similar:
                group = existing
                break
        if group is None:
            group = {
                "representative": key,
                "line_index": line_index,
                "pages": set(),
                "keys": [],
            }
            groups.append(group)
        group["pages"].add(page_index)
        group["keys"].append(key)

    threshold = max(2, int(len(pages) * HEADER_FOOTER_MIN_PAGE_FRACTION + 0.999))
    furniture_groups = [group for group in groups if len(group["pages"]) >= threshold]

    cleaned: list[str] = []
    for page_index, lines in enumerate(normalized_pages):
        kept: list[str] = []
        for line_index, line in enumerate(lines):
            if not line or _is_page_number_line(line):
                continue
            key = _normalize_header_key(line)
            if key in PAGE_FURNITURE_HINTS and (
                line_index < 6 or line_index >= max(0, len(lines) - 6)
            ):
                continue
            is_furniture = False
            if line_index < 6 or line_index >= max(0, len(lines) - 6):
                for group in furniture_groups:
                    if page_index in group["pages"] and any(
                        difflib.SequenceMatcher(None, key, candidate).ratio() >= 0.90
                        for candidate in group["keys"]
                    ):
                        is_furniture = True
                        break
            if not is_furniture:
                kept.append(line)
        cleaned.append("\n".join(kept))
    return cleaned


def _remove_footnote_blocks(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    in_footnote = False
    for index, line in enumerate(lines):
        normalized = _normalize_line(line)
        if not normalized:
            if in_footnote:
                in_footnote = False
            continue
        if _is_page_number_line(normalized):
            continue
        if in_footnote:
            if _is_structural_start(normalized) and not _looks_like_footnote_start(normalized, index, len(lines)):
                in_footnote = False
            else:
                continue
        if _looks_like_footnote_start(normalized, index, len(lines)):
            in_footnote = True
            continue
        cleaned.append(normalized)
    return cleaned


def _clean_pages(pages: list[str]) -> list[str]:
    prepared = []
    for page in pages:
        raw_lines = [_normalize_line(line) for line in page.splitlines()]
        note_numbers = {
            match.group(1)
            for line in raw_lines
            for match in [re.match(r"^\s*(\d{1,2})(?![.\d])\s+[A-Z]", line)]
            if match and _looks_like_footnote_start(line)
        }
        lines: list[str] = []
        for line in raw_lines:
            if note_numbers:
                numbers = "|".join(sorted(note_numbers, key=len, reverse=True))
                line = re.sub(
                    rf"(?<=[A-Za-z\"\u201d])(?:{numbers})(?![\d.])",
                    "",
                    line,
                )
                line = re.sub(
                    rf"(?<=[A-Za-z\"\u201d])\.(?:{numbers})(?![\d.])",
                    ".",
                    line,
                )
            lines.append(line)
        lines = _remove_footnote_blocks(lines)
        prepared.append("\n".join(lines))
    prepared = _strip_page_furniture(prepared)
    return ["\n".join(_remove_footnote_blocks(page.splitlines())) for page in prepared]


def extract_page_layers(file_path: Path) -> dict[str, list[str]]:
    """Return raw and cleaned page text for diagnostics and internal use."""
    from .hybrid_parser import parse_document

    parsed = parse_document(file_path)
    raw_pages_by_number: dict[int, list[str]] = {}
    for block in parsed.blocks:
        raw_pages_by_number.setdefault(block.page_start, []).append(block.text)
    raw_pages = [
        "\n".join(raw_pages_by_number[number])
        for number in sorted(raw_pages_by_number)
    ]
    return {"raw_pages": raw_pages, "cleaned_pages": _clean_pages(raw_pages)}


def extract_pages(file_path: Path) -> list[dict[str, object]]:
    """Extract cleaned pages while retaining page numbers internally."""
    layers = extract_page_layers(file_path)
    return [
        {"page_number": index, "text": text}
        for index, text in enumerate(layers["cleaned_pages"], start=1)
    ]


def extract_text(file_path: Path) -> str:
    """Extract cleaned text, preserving page boundaries as blank lines."""
    return "\n\n".join(str(page["text"]) for page in extract_pages(file_path) if page["text"])


def _enumeration_context(prefix: str) -> bool:
    lowered = prefix.lower()
    return bool(
        re.search(r"(?:following|as follows|include|includes|consist(?:s|ing) of)[^:\n]{0,80}:\s*$", lowered)
        or re.search(r"\([a-z]\)\s+", lowered, re.IGNORECASE)
        or lowered.rstrip().endswith(":")
    )


def _split_line_at_markers(line: str) -> list[str]:
    """Split a physical line at structural markers, including inline ones."""
    positions: set[int] = set()
    for match in NUMBERED_MARKER_RE.finditer(line):
        marker = match.group("marker")
        is_subsection = "." in marker.rstrip(".")
        prefix = line[: match.start()]
        is_cross_reference = bool(
            re.search(r"(?:section|article|clause)\s*$", prefix.rstrip(), re.IGNORECASE)
        )
        if not is_cross_reference and (
            is_subsection
            or match.start() == 0
            or _enumeration_context(prefix)
            or prefix.rstrip().endswith((".", ";", ":"))
        ):
            positions.add(match.start())
    for match in COMPACT_NUMBERED_MARKER_RE.finditer(line):
        prefix = line[: match.start()].rstrip()
        if match.start() == 0 or prefix.endswith((".", ";", ":")):
            positions.add(match.start())
    for match in COMPOUND_PAREN_MARKER_RE.finditer(line):
        prefix = line[: match.start()].rstrip()
        if match.start() == 0 or prefix.endswith((".", ";", ":")):
            positions.add(match.start())
    for match in SECTION_MARKER_RE.finditer(line):
        starts_cross_reference = bool(
            match.start() == 0
            and re.match(r"(?:section|article)\s+\d+(?:\.\d+)*\s+\(", line, re.IGNORECASE)
        )
        if not starts_cross_reference and (
            match.start() == 0 or _enumeration_context(line[: match.start()])
        ):
            positions.add(match.start())

    paren_matches = list(PAREN_MARKER_RE.finditer(line))
    if paren_matches:
        first = paren_matches[0]
        prefix = line[: first.start()]
        enum_active = (
            first.start() == 0
            or _enumeration_context(prefix)
            or bool(re.match(r"^\s*\d{1,3}\.\s*\S", prefix))
        )
        if enum_active:
            positions.update(match.start() for match in paren_matches)

    if _looks_like_all_caps_title(line):
        positions.add(0)

    if not positions:
        return [line]
    ordered = sorted(positions)
    parts: list[str] = []
    boundaries = ordered + [len(line)]
    start = 0
    for boundary in boundaries:
        part = line[start:boundary].strip()
        if part:
            parts.append(part)
        start = boundary
    return parts


def _sentence_chunk(text: str) -> list[str]:
    sentences = [part.strip() for part in SENTENCE_BOUNDARY_RE.split(text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > LONG_CLAUSE_FALLBACK_THRESHOLD:
            chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current.strip())
    return chunks or [text]


def _fallback_split_oversized(clause: str) -> list[str]:
    if len(clause) <= LONG_CLAUSE_FALLBACK_THRESHOLD:
        return [clause]
    parts = [part.strip() for part in INLINE_SUBITEM_RE.split(clause) if part.strip()]
    if len(parts) <= 1:
        parts = [clause]
    result: list[str] = []
    for part in parts:
        result.extend([part] if len(part) <= LONG_CLAUSE_FALLBACK_THRESHOLD else _sentence_chunk(part))
    return result


def split_into_clauses(raw_text: str) -> list[str]:
    """Split normalized contract text using structural markers first."""
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = _remove_footnote_blocks(text.split("\n"))

    clauses: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            value = re.sub(r"\s+", " ", " ".join(current)).strip()
            if value:
                clauses.append(value)
            current.clear()

    for raw_line in lines:
        line = _normalize_line(raw_line)
        if not line:
            flush()
            continue
        parts = _split_line_at_markers(line)
        for part_index, part in enumerate(parts):
            part = re.sub(
                r"^(\d{1,3}\.)(?=[\"\u201c\u2018'A-Z(])",
                r"\1 ",
                part,
            )
            definition_continuation = bool(
                current
                and PAREN_MARKER_RE.match(part)
                and is_definition(" ".join(current))
            )
            starts_boundary = (
                not definition_continuation
                and (part_index > 0 or _is_structural_start(part))
            )
            if starts_boundary:
                flush()
            current.append(part)
    flush()

    cleaned: list[str] = []
    pending_heading: str | None = None
    for clause in clauses:
        clause = re.sub(r"\s+", " ", clause).strip()
        if not clause or is_footnote(clause):
            continue
        if _looks_like_all_caps_title(clause) and len(clause) < MIN_CLAUSE_CHARS:
            pending_heading = clause
            continue
        if pending_heading:
            clause = f"{pending_heading} {clause}"
            pending_heading = None
        if len(clause) < MIN_CLAUSE_CHARS and not _is_structural_start(clause):
            continue
        cleaned.extend(_fallback_split_oversized(clause))

    if pending_heading and len(pending_heading) >= MIN_CLAUSE_CHARS:
        cleaned.append(pending_heading)
    return cleaned
