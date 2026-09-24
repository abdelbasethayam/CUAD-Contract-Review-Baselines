# Extraction and Segmentation Fix Report

## Problem

The PDF pipeline was treating the output of `pdfplumber` as ordinary line-oriented text. PDF extraction frequently placed several structural markers on one physical line, while page disclaimers, page numbers, and drafting footnotes remained mixed into the contract text. This caused definitions and neighboring provisions to be merged or contaminated.

## Root Cause

The previous segmenter only recognized numbered markers at the beginning of extracted lines. Its repeated-header detection also compared many non-edge lines with `difflib`, which was both unsafe for legal body text and extremely slow on the 22-page sample. A marker such as `1. DEFINITIONS 1.1 "Affiliate" means...` therefore did not produce a boundary before `1.1`.

## Changes

- Added page-aware extraction through `extract_page_layers()` and `extract_pages()` while preserving the existing `extract_text()` API.
- Normalized whitespace page by page and retained page boundaries until segmentation.
- Restricted repeated header/footer detection to page edges and bounded near-duplicate comparisons.
- Removed page-number-only lines and known page furniture such as `ACC FORM` when found at page edges.
- Removed drafting-note footnote blocks using contextual cues and page position, while preserving legitimate numbered clauses.
- Removed superscript-style footnote references when their corresponding footnote exists on the page.
- Added inline structural marker detection for decimal subsections, numbered sections, `Section`/`Article` markers, and contextual `(a)`/`(b)` enumerations.
- Added definition-aware handling so definition entries are separated individually and their internal enumerations are not split into unrelated clauses.
- Added cross-reference safeguards so text such as `Section 5.3 (Automatic Renewal...)` and `Section 16.100 (Notices)` is not mistaken for a new clause.
- Kept oversized-clause fallback ordering structural first, inline enumeration second, and sentence boundaries last.
- Added focused tests and an optional evaluation utility that writes page, clause, and metric artifacts.

Classifier, embeddings, Qdrant collections, prompts, Ollama, Cohere, risk detection, API schemas, and frontend behavior were not changed for this extraction fix.

## Regression Test

The real regression file was:

`Cooley SaaS Agreement ACC Form.pdf`

The new pipeline processed all 22 pages. It identified definitions `1.1` through `1.20` as separate definition entries, including the definitions that previously crossed a page boundary. It also removed the repeated informational disclaimer, page-number lines, drafting-note blocks, and the repeated `ACC FORM` footer from the segmented contract text.

Representative resulting clauses include `1.1`, `1.2`, `1.4`, `1.5`, `1.18`, `2.1`, `2.2`, `7.1`, `15.1`, and `16.14`. No resulting clause exceeded the 3,000-character oversized-clause threshold.

## Metrics

The issue description reported a previous result of only 3 clauses. Exact before length metrics were not available from that run. The committed baseline extractor was also profiled separately: its edge-cleanup pass did not complete within 90 seconds on this PDF because of the unbounded line comparison; with only that slow cleanup bypassed, it produced 121 segments, 18 recognized definitions, an average segment length of 592.3 characters, and a maximum of 2,444 characters, with visible header/footer and footnote contamination.

| Metric | Before evidence | After |
|---|---:|---:|
| Pages | 22 | 22 |
| Raw/cleaned characters | 80,827 raw baseline text | 80,806 raw / 72,663 cleaned |
| Clauses | 3 reported; 121 committed-baseline diagnostic segments | 120 |
| Average clause length | 592.3 in committed-baseline diagnostic | 600.3 |
| Largest clause | 2,444 in committed-baseline diagnostic | 2,444 |
| Definitions detected separately | 18 in committed-baseline diagnostic | 20 |
| Headings detected | not recorded | 20 |
| Header/footer contamination | Present | Repeated page disclaimer, page numbers, and edge `ACC FORM` removed |
| Oversized clauses | Not reliably measured in the reported run | None above 3,000 characters |

The clause count is not a target; it is the result of the document's detected structure and the configured fallback safeguards.

## Tests

- `pytest -q backend/tests`: **23 passed**, 2 deprecation warnings.
- `pytest -q backend/tests/test_segmenter.py`: **9 passed**.
- `python -m compileall -q backend/app`: **passed** in the Docker Python environment.
- Real-PDF evaluation utility: **completed** for the 22-page Cooley PDF.

Generated artifacts:

- `reports/extraction/extracted_pages.txt`
- `reports/extraction/cleaned_pages.txt`
- `reports/extraction/segmented_clauses.json`
- `reports/extraction/segmentation_report.md`

## Known Limitations

- Scanned or image-only PDFs still require OCR; `pdfplumber` cannot recover text that is not present as a text layer.
- Complex multi-column layouts may require layout-aware extraction beyond the current page parser.
- Tables, unusual hyphenation, and irregular numbering can still require document-specific review.
- Structural segmentation remains heuristic and does not claim universal legal-document parsing.
