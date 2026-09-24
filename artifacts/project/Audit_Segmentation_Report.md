# Segmentation and Chunking Audit

## Production implementation

The active service calls `clause_segmenter.segment_document()`, not the legacy
flat `split_into_clauses()` function. `hybrid_parser.parse_document()` selects
Docling when available and falls back to pdfplumber in `hybrid` mode. TXT files
are read directly.

The clause segmenter preserves ordered parser blocks and detects numbered,
dotted, section/article, compound-parenthesis, letter, and Roman markers. It
removes page numbers and repeated page furniture, tracks page ranges, retains
tables as blocks, recognizes definitions, detects signature metadata, and
validates the resulting tree. The validator then asks Ollama whether each
candidate is a real clause; its failure mode is fail-open.

## Configured thresholds

| Parameter | Value | Source |
|---|---:|---|
| legacy minimum clause length | 40 characters | `segmenter.py` |
| legacy oversized fallback threshold | 3,000 characters | `segmenter.py` |
| legacy header/footer page fraction | 0.5 | `segmenter.py` |
| legal-KB chunk size | 1,200 characters | `ingest.py` |
| legal-KB overlap | 150 characters | `ingest.py` |
| runtime clause overlap | NOT CONFIGURED | structural clause segmentation, not sliding-window chunking |

There is no token-based chunk size in the production clause segmenter. Page
tracking and section/parent tracking are metadata fields on `ClauseNode`.

## Measured artifacts and trace

The persisted Cooley diagnostic artifact reports 22 pages, 120 clauses, 20
definitions, 20 headings, raw/cleaned characters of 80,806/72,663, and clause
lengths from 58 to 2,444 with mean 600.3. Its Docling and hybrid rows are
NOT VERIFIED: the evaluation artifact records Docling unavailable in that
environment; the regex row is a structural proxy, not ground truth.

A read-only execution against the repository ZTO PDF with
`CONTRACT_PARSER=regex` produced:

| Metric | Value |
|---|---:|
| parser | pdfplumber-fallback |
| parser blocks | 4 |
| page range | 1–4 |
| top-level clause nodes returned to service | 16 |
| min/max/mean node length | 113 / 3,913 / 560.56 characters |
| definitions | 0 |
| signature metadata nodes | 1 |

Docling-based values for this execution are NOT VERIFIED because the current
host evaluation environment did not have Docling installed.

