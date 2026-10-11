# Commercial Contract Risk Detection — Team Export

Source-of-truth playbook version: 1.1.

## Contents

- risk_clause_checks.csv — 101 clause-level checks.
- risk_cross_clause_checks.csv — 10 cross-clause checks.
- risk_document_checks.csv — 3 document-level checks.
- risk_playbook_exact.json — byte-for-byte copy of the source playbook.
- risk_taxonomy.json — canonical broad risk domains and guidance.
- source_registry.json — legal-knowledge source metadata.
- export_manifest.json — source/export hashes and validation counts.

## Risk-domain policy

Every check maps to one of the 10 canonical domains in risk_taxonomy.json.
The declared playbook domain is the primary review-routing/aggregation domain. A
more specific legacy label is retained as risk_subdomain. Taxonomy keyword
matches are supplementary signals and must not override an explicit domain.

## Evidence and evaluation caveat

The playbook and taxonomy are **review guidance, not contract evidence and not
human gold labels**. A positive risk finding must be supported by exact evidence
from the uploaded contract. The project still requires expert annotation and
adjudication of its 300-task gold queue before reporting human-gold accuracy for
the custom risk predicates.
