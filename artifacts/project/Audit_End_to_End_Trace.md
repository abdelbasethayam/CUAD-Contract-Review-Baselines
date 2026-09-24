# End-to-End Trace

## Trace input

The repository contains
`ZtoExpressCaymanInc_20160930_F-1_EX-10.10_9752871_EX-10.10_Transportation Agreement.pdf`.
A read-only local execution used this PDF with `CONTRACT_PARSER=regex` so it
did not require unavailable Docling components.

## Observed trace

```text
ZTO PDF
  -> pdfplumber fallback
  -> 4 parser blocks, pages 1-4, 8,987 extracted block characters
  -> clause_segmenter
  -> 16 top-level ClauseNode values
  -> 16 node texts, lengths 113-3,913, mean 560.56
  -> one signature-metadata node identified
  -> validator stage in service
  -> Cohere search_query embedding
  -> cuad_train Qdrant Top-5
  -> candidate-constrained Ollama CUAD label
  -> legal_knowledge category-filtered Top-3
  -> deterministic risk indicators
  -> constrained Ollama risk result
  -> ClauseResult list
  -> JSON/SSE API
  -> React frontend
```

The execution did not call Cohere or Ollama as part of this audit, so actual
runtime vectors, retrieval scores, model responses, latency, and final risk
outputs for this trace are NOT VERIFIED. The parser and segmenter values above
are RUNTIME observations.

Existing ZTO diagnostic artifacts separately report a Docling/Ollama run with
46 blocks, 16 top-level clauses, Top-K 5, and 12 selected clauses, but that
artifact is explicitly leakage-affected and is historical evidence rather than
a fresh execution in this audit.

