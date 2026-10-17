# LLM-as-judge diagnostics — Phase 2

- Status: COMPLETED
- Scenario cases: 39
- Judge records: 78
- This is a machine-assessed rubric diagnostic, **not** human gold, validated judge reliability, or legal-risk accuracy.

## Per-model summary

| Model | Completed | Claim supported (true/false) | Interaction supported (true/false) | Uncertainty appropriate (true/false) | All quotes exact |
|---|---:|---|---|---|---:|
| qwen3:8b | 39/39 | 32/0 | 22/0 | 32/0 | 16/16 |
| llama3.1:8b | 39/39 | 26/0 | 19/0 | 18/0 | 16/16 |

## Descriptive pairwise agreement

| Rubric field | Comparable scenarios | Agreement |
|---|---:|---:|
| claim_supported | 26 | 26/26 |
| interaction_supported | 12 | 12/12 |
| uncertainty_appropriate | 18 | 18/18 |

## Disagreements and concerns

### DOC-1-INCOMPLETE
- qwen3:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=[]; rationale=The observed status is supported by multiple clauses referencing missing documents, which creates uncertainty and potential gaps in enforceability.
- llama3.1:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=["Appendix C not provided", "Order Form not attached", "Schedule 4 not included"]; rationale=Multiple clauses reference external documents that are missing from the review package, creating uncertainty and potential gaps in enforceability.

### DOC-1-POSITIVE
- qwen3:8b: status=COMPLETED; supported=True; interaction=None; uncertainty=True; exact quotes=True; concerns=[]; rationale=The clause explicitly states that online terms and policies may be updated at any time without being attached, which supports the claim that these terms are not fixed or reviewable.
- llama3.1:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=["The contract incorporates external terms and policies that are not fixed or attached, which may be updated at any time, making them unreadable or unreviewable."]; rationale=The contract explicitly states that the online terms and policies may be updated at any time, which could make them unreadable or unreviewable.

### DOC-2-CONTROL
- qwen3:8b: status=COMPLETED; supported=True; interaction=None; uncertainty=True; exact quotes=False; concerns=[]; rationale=The observed status 'INSUFFICIENT_EVIDENCE' is appropriate as the definitions and order-of-precedence clauses are not explicitly checked for narrowing or reversing a protective substantive clause.
- llama3.1:8b: status=COMPLETED; supported=None; interaction=None; uncertainty=True; exact quotes=False; concerns=["insufficient evidence to determine if there is a conflict or reversal"]; rationale=The definitions and order-of-precedence clauses are not explicitly checked for narrowing or reversing a protective substantive clause.

### DOC-2-POSITIVE
- qwen3:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=[]; rationale=The order of precedence clause and the governing law clause both reference an unattached Order Form, supporting the claim that the dispute resolution mechanism is ambiguous.
- llama3.1:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=["The order of precedence clause allows Supplier's online terms to override the signed Agreement, and the governing law and dispute procedure are delegated to an unattached Order Form, creating ambiguity."]; rationale=The contract explicitly states that the online terms prevail over the signed Agreement in a conflict, and the governing law and dispute procedure are delegated to an unattached Order Form.

### DOC-3-INCOMPLETE
- qwen3:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=[]; rationale=The observed status is supported by clauses referencing missing governing law and dispute mechanisms.
- llama3.1:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=["Governing law not specified", "Forum and dispute mechanism not provided"]; rationale=Governing law, forum, and dispute mechanism are missing or inconsistent due to the absence of referenced documents.

### DOC-3-POSITIVE
- qwen3:8b: status=COMPLETED; supported=True; interaction=None; uncertainty=True; exact quotes=True; concerns=[]; rationale=The clause explicitly states that the governing law is in an unattached Order Form, supporting the claim that the exact dispute resolution mechanism is unknown.
- llama3.1:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=["The governing law, forum, and dispute procedure are delegated to an Order Form that is not attached, making it impossible to determine the exact dispute resolution mechanism for this contract."]; rationale=The contract explicitly states that the governing law, forum, and dispute procedure are delegated to an unattached Order Form.

### X-1-CONTROL
- qwen3:8b: status=COMPLETED; supported=None; interaction=None; uncertainty=None; exact quotes=False; concerns=[]; rationale=The observed status 'INSUFFICIENT_EVIDENCE' is appropriate as no usable model answer was returned.
- llama3.1:8b: status=COMPLETED; supported=None; interaction=None; uncertainty=None; exact quotes=False; concerns=["no usable model answer was returned"]; rationale=No usable model answer was returned.

### X-1-POSITIVE
- qwen3:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=[]; rationale=The liability cap clause and the liquidated damages clause both reference the cap and its exceptions, supporting the claim of overlap and ambiguity.
- llama3.1:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=["The clause on liability cap states that other liability heads are capped, creating overlap with uncapped heads like liquidated damages, which are explicitly outside the cap."]; rationale=The contract explicitly states that other liability heads are capped, creating overlap with uncapped heads like liquidated damages.

### X-10-INCOMPLETE
- qwen3:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=[]; rationale=The observed status is supported by clauses referencing missing indemnification and liability cap documents.
- llama3.1:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=["Liability cap not provided", "Indemnification exhibit not supplied"]; rationale=Indemnification is referenced in an exhibit that is not supplied, and the liability cap is also missing, creating a potential for uncapped indemnification.

### X-10-POSITIVE
- qwen3:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=[]; rationale=The liability cap clause and the indemnification clause both reference the uncapped nature of indemnification, supporting the claim of unbounded liability.
- llama3.1:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=["Indemnification obligations are explicitly stated to be uncapped and outside the liability cap, which may leave the liability exposure unbounded."]; rationale=The contract explicitly states that indemnification obligations are uncapped and outside the liability cap.

### X-3-CONTROL
- qwen3:8b: status=COMPLETED; supported=None; interaction=None; uncertainty=None; exact quotes=False; concerns=[]; rationale=The observed status 'INSUFFICIENT_EVIDENCE' is appropriate as no usable model answer was returned.
- llama3.1:8b: status=COMPLETED; supported=None; interaction=None; uncertainty=None; exact quotes=False; concerns=["no usable model answer was returned"]; rationale=No usable model answer was returned.

### X-4-CONTROL
- qwen3:8b: status=COMPLETED; supported=None; interaction=None; uncertainty=None; exact quotes=False; concerns=[]; rationale=The observed status 'INSUFFICIENT_EVIDENCE' is appropriate as no usable model answer was returned.
- llama3.1:8b: status=COMPLETED; supported=None; interaction=None; uncertainty=None; exact quotes=False; concerns=["no usable model answer was returned"]; rationale=No usable model answer was returned.

### X-4-POSITIVE
- qwen3:8b: status=COMPLETED; supported=True; interaction=None; uncertainty=True; exact quotes=True; concerns=[]; rationale=The termination clause explicitly states the financial obligations upon termination, supporting the claim of potential financial exposure.
- llama3.1:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=["Termination for convenience triggers full minimum commitment and fees for the remaining term, which could result in significant financial exposure."]; rationale=The contract explicitly states that termination for convenience triggers full minimum commitment and fees for the remaining term.

### X-5-POSITIVE
- qwen3:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=[]; rationale=The assignment and change-of-control clauses reference different consent standards for the same event, supporting the claim of inconsistency.
- llama3.1:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=["The anti-assignment clause and change-of-control clause impose materially different consent standards for the same corporate event (change of control)."]; rationale=

### X-7-POSITIVE
- qwen3:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=[]; rationale=The IP assignment and critical software clauses reference each other, supporting the claim of unclear continuing rights.
- llama3.1:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=["IP assignment leaves the other party's license without a clear source of continuing rights, especially for business-critical software."]; rationale=The contract explicitly states that the license grant only covers Supplier-owned materials and does not clearly grant Customer continued rights in its assigned deliverables.

### X-8-INCOMPLETE
- qwen3:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=[]; rationale=The observed status is supported by clauses referencing missing technology schedule and service continuity appendix.
- llama3.1:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=["Technology schedule not provided", "Service continuity appendix not included"]; rationale=The license clause references a missing technology schedule, and the source code escrow clause references a missing service continuity appendix, indicating a lack of post-termination support for critical software.

### X-8-POSITIVE
- qwen3:8b: status=COMPLETED; supported=True; interaction=None; uncertainty=True; exact quotes=True; concerns=[]; rationale=The critical software clause explicitly states the lack of support, supporting the claim of risk.
- llama3.1:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=["There is a business-critical software license with no escrow, continuity, or post-termination support."]; rationale=The contract explicitly states that there is no source code escrow, continuity commitment, or post-termination support for the business-critical software.

### X-9-POSITIVE
- qwen3:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=[]; rationale=The liability cap and insurance clauses reference each other, supporting the claim of exposure above stated coverage.
- llama3.1:8b: status=COMPLETED; supported=True; interaction=True; uncertainty=True; exact quotes=True; concerns=["The liability cap of $100,000 is less than the required insurance limits of $50,000, leaving exposure above stated coverage."]; rationale=The contract explicitly states that the liability cap is $100,000, while the required insurance limits are $50,000.

## Provenance

- Input SHA-256: `f3ab268d9d6550ea6d40ceec4291c9de367a39aed9ee88f06b7401aa6d910d81`
- Prompt SHA-256 (control/qwen3:8b): `50f70f9b888e23f39eda6a770ee50d839d7eb3657106e1b56ec494a5b74b0576`
- Prompt SHA-256 (control/llama3.1:8b): `50f70f9b888e23f39eda6a770ee50d839d7eb3657106e1b56ec494a5b74b0576`
- Prompt SHA-256 (incomplete/qwen3:8b): `2b28f44d35d013d57744b9c6259afba7ae90fee63f144af9d467ea5f0b1c1ed9`
- Prompt SHA-256 (incomplete/llama3.1:8b): `2b28f44d35d013d57744b9c6259afba7ae90fee63f144af9d467ea5f0b1c1ed9`
- Prompt SHA-256 (positive/qwen3:8b): `b2135deee41f5afff46f62bca789b126d8139b41ed921e23ec89c05ce71388f9`
- Prompt SHA-256 (positive/llama3.1:8b): `b2135deee41f5afff46f62bca789b126d8139b41ed921e23ec89c05ce71388f9`
