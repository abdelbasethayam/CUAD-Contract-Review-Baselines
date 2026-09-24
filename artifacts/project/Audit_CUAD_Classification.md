# CUAD Classification Audit

## Role of CUAD

CUAD supplies the substantive clause-type label space and indexed training
examples. It does not supply risk labels. The runtime label list is loaded from
the train long CSV after excluding metadata, yielding `36` labels.

## Classification flow

```text
uploaded clause text
    -> Cohere search_query vector
    -> Qdrant cuad_train Top-5
    -> unique valid labels from retrieved payloads
    -> legal-information regex features
    -> Ollama prompt with only candidate labels
    -> JSON clause_type response
    -> VALID_CANDIDATE / UNKNOWN / MALFORMED_RESPONSE / OUT_OF_CANDIDATE
```

Retrieval and classification are separate: retrieval supplies evidence and
candidate labels; Ollama selects a label or abstains. The parser rejects a
label that is not both a known CUAD label and present in the retrieved
candidate set. The normalized prediction becomes `UNKNOWN` for malformed or
out-of-candidate responses.

## Prompt/features

The prompt includes the clause, retrieved examples and scores, candidate label
list, label definitions, and deterministic legal information such as concepts,
actions, rights, obligations, restrictions, conditions, dates, monetary values,
percentages, and numeric values. The Ollama request uses JSON output,
temperature `0`, CPU mode, mmap, and context size `4096`.

No classification confidence score or acceptance threshold is implemented.
Retrieved scores are exposed as evidence only.

