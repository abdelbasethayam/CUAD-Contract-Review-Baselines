# PDF Parsing and Clause Segmentation Evaluation

## Executive summary

The production RAG service now uses the hybrid parser mode by default. Docling
is optional; when it is unavailable or fails, extraction falls back to
`pdfplumber` plus the deterministic segmenter. No CUAD, Cohere, Qdrant, Ollama,
risk, API, or frontend interfaces were changed.

The required representative document is:

`ZtoExpressCaymanInc_20160930_F-1_EX-10.10_9752871_EX-10.10_Transportation Agreement.pdf`

The current baseline has a material layout/formatting failure on this file:
compact numbered markers such as `1.Party`, `3.Freight`, and `4.Transportation`
are not recognized as boundaries. The baseline therefore merges many numbered
clauses and subclauses across page breaks. This is a parsing/normalization
problem as well as a boundary-rule problem; it is not evidence that a paid LLM
is needed.

Docling is isolated behind an optional adapter in
`backend/app/core/rag/hybrid_parser.py`; the evaluation adapter remains in
`backend/app/core/rag/segmentation_evaluation.py`. It was not installed in
the available environment, so benchmark measurements for Docling and hybrid
are explicitly reported as unavailable. No Docling accuracy or performance
result is claimed.

**Decision:** apply Hybrid with a safe Regex fallback. The benchmark evidence
does not prove Docling improves accuracy yet, so the fallback remains the
reliable production path until the optional parser is installed and manually
validated on the same document.

## Current architecture

The production path is:

`PDF upload -> Docling page/structure extraction when available -> deterministic
cleanup and clause splitting -> pdfplumber fallback if needed -> clause
validation -> Cohere embeddings -> Qdrant/CUAD classification -> risk analysis
-> API/frontend response`

Clauses currently flow downstream as plain strings. The public extraction API
is unchanged: `extract_text(Path) -> str` and
`split_into_clauses(str) -> list[str]`. The evaluation prototype adds a
normalized, page-aware record without changing that contract:

`clause_id`, `clause_number`, `heading`, `text`, `page_start`, `page_end`,
`source`, and validation metadata.

## Problems identified

The target contract demonstrates or is capable of exposing these cases:

- top-level numbers without a space after the period (`1.Party`);
- multiple numbered clauses on the same extracted line;
- nested items such as `(a)` through `(i)`;
- clauses continuing across page boundaries;
- headings and paragraph text emitted as one physical line;
- tables and form-like blocks where row order is not equivalent to paragraph
  order;
- definitions, which need to remain intact and are not CUAD clause types;
- page furniture and drafting footnotes, which can contaminate a clause when
  extracted as ordinary text;
- loss of layout information when page text is flattened.

The existing implementation already handles several conservative cases:
line/inline `1.1`-style markers, explicit parenthesized enumerations,
repeated edge furniture, page numbers, likely drafting notes, definitions, and
oversized-clause fallback. These behaviors are covered by the existing
segmenter tests and the isolated evaluation tests.

## Approaches

### A — current Regex/page-text baseline

`pdfplumber` extracts text per page. Cleanup removes repeated page-edge
furniture and likely footnote blocks. Deterministic rules identify numbering,
headings, definitions, and parenthesized enumerations. The result is flattened
for the unchanged downstream pipeline.

Strengths: free, local, fast to deploy, deterministic, already integrated, and
easy to test. Weaknesses: it cannot reliably reconstruct reading order or table
structure after PDF text extraction has lost coordinates; numbering variants
and same-line boundaries require continual rule maintenance.

### B — Docling-only candidate

The isolated adapter asks Docling for ordered document text items, labels,
page provenance, and table items. Its output is normalized into the evaluation
record format. It does not call a paid API or an LLM.

Potential strengths: document structure, reading order, page provenance, and
table awareness. Potential weaknesses: larger install/runtime footprint,
version-sensitive APIs, layout-specific errors, and the possibility that
Docling paragraph boundaries do not match legal clause boundaries.

### C — hybrid candidate

Docling owns PDF parsing, ordering, page provenance, and structure labels.
Deterministic logic owns clause-marker detection, definition handling,
validation, footer/footnote filtering, and fallback behavior. The adapter is
isolated and does not enter production automatically.

This is technically justified as the next experiment because document layout
and legal clause boundaries are different problems. It is not selected as the
winner yet because its output was not available for this run.

## Methodology

The prototype evaluates the same input through `regex`, `docling`, and
`hybrid`, producing the same normalized record shape. It records clause count,
definition count, marked-clause count, page-spanning count, suspiciously short
and oversized clauses, likely header/footer contamination, and elapsed time.

The repository contains no human-labeled clause-boundary ground truth for the
ZTO document. Consequently, split/merge accuracy, reading-order accuracy,
table accuracy, and true precision/recall cannot be calculated. Structural
counts are diagnostic proxies only and must not be read as accuracy numbers.

## Results

### Target contract baseline

The checked-in evaluation artifact (`reports/segmentation/evaluation.json`)
records the Regex run for the target document as:

| Metric | Regex baseline |
|---|---:|
| Clauses emitted | 3 |
| Marked clauses detected | 0 |
| Definitions | 0 |
| Page-spanning records | 3 |
| Clauses under 120 characters | 0 |
| Clauses over 3,000 characters | 0 |

Manual inspection of the three records shows that clauses 1–5 are merged into
the first record, later numbered provisions are merged into the second and
third records, and `(a)`–`(i)` items are not separated. The page-spanning count
therefore reflects merged records, not successful multi-page segmentation.

Docling and hybrid are marked unavailable in the artifact because the optional
Docling dependency was not installed. Processing time from a different
environment or a different PDF copy must not be compared with this run.

### Synthetic behavior tests

The isolated tests cover `1.`, `1.1`, `(a)`, same-block headings, definition
metadata, page provenance, table-labeled blocks, and multi-page records. These
tests verify representation and rule behavior; they are not a substitute for
labels on the target PDF.

## Recommendation

Use the Hybrid implementation now, with `CONTRACT_PARSER=hybrid` as the
default. It keeps deterministic rules in charge of legal boundaries and does
not make the application depend on Docling being installed. Set
`CONTRACT_PARSER=regex` to force the legacy path. Set
`CONTRACT_PARSER=docling` only where Docling is installed and a hard failure is
preferred over fallback.

This is an integration improvement, not a proven accuracy improvement. The
missing Docling run and labeled/manual review are still required before making
accuracy claims.

## Migration plan after successful evaluation

1. Install the pinned optional evaluation dependencies in a separate
   environment and run the CLI on the exact target PDF.
2. Manually annotate clause starts, ends, numbering, page spans, tables,
   definitions, and headers/footers for the target and at least two additional
   layout variants.
3. Add fixture-based tests for every observed failure before changing the
   production service.
4. Keep the explicit parser mode and fallback; add a low-validation fallback
   if real-world monitoring identifies poor Docling output.
5. Convert normalized records to the existing `clause_text` strings at the
   service boundary so CUAD/RAG/risk/API/frontend behavior remains unchanged.
6. Benchmark cold start, warm processing time, memory, image-only/OCR cases,
   table-heavy pages, and dependency size before merging to master.

## Risks and limitations

- No labeled ground truth means no defensible numerical segmentation accuracy.
- Docling could not be installed or executed in this environment.
- The stored artifact contains successful Regex output and explicit Docling
  availability errors; it is not a three-way benchmark.
- `pdfplumber` and Docling can both fail on scanned PDFs without OCR.
- PDF reading order and table interpretation remain layout-dependent.
- Optional Docling versions can change object labels and provenance APIs.
- Existing uncommitted user changes, including the zero-byte
  `Cooley SaaS Agreement ACC Form.pdf`, were not modified or discarded.

## Reproduction

From the repository root, in an environment with the project dependencies:

```text
python -m app.core.rag.segmentation_evaluation \
  "ZtoExpressCaymanInc_20160930_F-1_EX-10.10_9752871_EX-10.10_Transportation Agreement.pdf" \
  --output reports/segmentation/evaluation.json
```

Use `--without-docling` for a baseline-only run. Install
`evaluation/requirements-docling.txt` separately before collecting B/C
results; those dependencies are intentionally not part of the production
requirements.
