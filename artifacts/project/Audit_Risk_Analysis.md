# Risk Analysis Audit

## Active flow

```text
CUAD predicted label + clause text
        -> classification status gate
        -> mapped legal category
        -> legal_knowledge Qdrant Top-3 guidance
        -> deterministic regex indicators
        -> constrained Ollama risk assessment
        -> strict response validation
        -> typed ClauseResult risk fields
```

Risk is a combination of clause text, the CUAD label as a category router,
retrieved legal guidance, deterministic rules, and Ollama reasoning. CUAD
labels themselves are not risk labels.

## Inputs and rules

`risk_detector.py` contains indicator regexes for Limitation of Liability,
Indemnification, Termination, Intellectual Property, Confidentiality, Payment,
Force Majeure, Dispute Resolution, Insurance, Warranties, and Assignment.
Indicators include uncapped wording, damages exclusions, indemnity scope,
termination mechanics, IP ownership/license scope, confidentiality ambiguity,
payment ambiguity, force majeure notice/mitigation, ADR mechanics, insurance
coverage, warranty scope, and assignment/change-of-control language.

The detector also has deterministic guards for clear capped liability, limited
IP licenses, clear IP assignments, clear IP ownership, and a strong broad-IP
license fallback.

## Ollama model and validation

The current backend environment resolves the risk model to `llama3.2:3b` at
`http://127.0.0.1:11434`, with timeout `60` seconds and up to `3` retries.
The prompt requires JSON, a boolean `risk`, a human-review reason, and exact
contract evidence. The parser rejects non-boolean risk values. Positive risk
requires a non-empty reason and evidence that is a contiguous substring of the
clause. Sources are constrained to retrieved guidance. A positive model result
without matched deterministic indicators is converted to no risk.

## Typed output

`ClauseResult` exposes `risk`, `risk_type`, `risk_status`, `risk_level`,
`rule_id`, `rule`, `matched_indicators`, `risk_rules`, `reason`, `evidence`,
`source`, and `legal_knowledge`. Statuses are `POTENTIAL_RISK`, `NO_RISK`,
`UNAVAILABLE`, `SKIPPED`, and `ERROR`.

`risk_level` has a schema type but no calibrated severity assignment is present:
potential risks currently use no concrete HIGH/MEDIUM/LOW value. A numeric risk
score, confidence score, weighted rule score, and threshold are NOT VERIFIED /
not implemented.

