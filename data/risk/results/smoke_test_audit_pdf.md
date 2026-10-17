# End-to-End Upload Smoke Test Audit

**Status:** PASS
**Interpretation:** Synthetic plumbing test only—not an accuracy benchmark.
Analysis ID: db10b978019252fc-460547d488bfb3a2
Input: /home/jovyan/CUAD-Contract-Review-Baselines/test_contract.pdf
Input SHA-256: db10b978019252fc65bf8680b63afbc54df198ef894f417113c3da391cff4fa4
Runtime seconds: 82.978
Git commit in manifest: 8c373301b194081ec03d6a2198724b8edb90112e
Code fingerprint: 9702b273cab8ef010eeca0c17e1c952120a065a604eff59b99c82c47caa0ce51
Playbook hash: 03c41c2bd8d560824facaf4c3b0097060b199678322e465504d5ef0aa4830793

## End-to-end outcome

| Metric | Observed |
|---|---:|
| HTTP status | 200 |
| Pipeline status | COMPLETED |
| Clauses returned | 2 |
| Clause-level findings | 0 |
| Positive clause findings | 0 |
| Positive quotes in target clause | 0 |
| Positive quotes from related clause | 0 |
| Invalid/unmapped positive quotes | 0 |
| Cross-clause status counts | {"INSUFFICIENT_EVIDENCE": 10} |
| Document status counts | {"INSUFFICIENT_EVIDENCE": 3} |
| Valid positive cross/document results | 0 |
| Overall triage | INSUFFICIENT_EVIDENCE / None |
| Legal guidance matches | 0 across 0 searches |

## Clause classifications
- Clause 0: NO_APPLICABLE_LABEL (NO_APPLICABLE_LABEL)
- Clause 1: NO_APPLICABLE_LABEL (NO_APPLICABLE_LABEL)

## Deterministic interaction candidates
- None recorded in this run.

## Validation
- [x] http_200
- [x] run_completed
- [x] source_hash_matches_manifest
- [x] all_clause_positive_findings_have_valid_evidence
- [x] all_cross_document_positive_findings_have_valid_evidence
- [x] run_has_core_artifacts

## Limitations observed

- The contract fixture is invented and intentionally contains test stimuli. This is not measured legal-risk accuracy.
- Model-silver and synthetic fixtures do not replace human adjudication.
- New runs identify whether exact evidence came from the target clause or a related clause; the source clause ID is preserved.
- If legal-guidance matches are zero, check that the local Qdrant collection has been populated with the legal knowledge ingestion command before launching the API. This report captures the actual result for this run and does not retroactively change it.
- Full response, manifest, trace and per-finding exports are under data/runs/db10b978019252fc-460547d488bfb3a2.
