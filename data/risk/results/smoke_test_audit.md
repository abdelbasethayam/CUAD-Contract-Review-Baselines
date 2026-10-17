# End-to-End Upload Smoke Test Audit

**Status:** PASS
**Interpretation:** Synthetic plumbing test only—not an accuracy benchmark.
Analysis ID: 56a13430f537613f-460547d488bfb3a2
Input: /home/jovyan/CUAD-Contract-Review-Baselines/data/risk/demo_contract_smoke.txt
Input SHA-256: 56a13430f537613f4e1421b8eb993658c1d3722604c3e3afca71375054dcd25b
Runtime seconds: 423.0
Git commit in manifest: 8c373301b194081ec03d6a2198724b8edb90112e
Code fingerprint: 9702b273cab8ef010eeca0c17e1c952120a065a604eff59b99c82c47caa0ce51
Playbook hash: 03c41c2bd8d560824facaf4c3b0097060b199678322e465504d5ef0aa4830793

## End-to-end outcome

| Metric | Observed |
|---|---:|
| HTTP status | 200 |
| Pipeline status | COMPLETED |
| Clauses returned | 4 |
| Clause-level findings | 13 |
| Positive clause findings | 3 |
| Positive quotes in target clause | 3 |
| Positive quotes from related clause | 0 |
| Invalid/unmapped positive quotes | 0 |
| Cross-clause status counts | {"INSUFFICIENT_EVIDENCE": 6, "POTENTIAL_RISK": 2, "NO_RISK": 2} |
| Document status counts | {"POTENTIAL_RISK": 1, "NO_RISK": 1, "INSUFFICIENT_EVIDENCE": 1} |
| Valid positive cross/document results | 3 |
| Overall triage | POTENTIAL_RISK / MEDIUM |
| Legal guidance matches | 9 across 3 searches |

## Clause classifications
- Clause 1: Uncapped Liability (VALID_CANDIDATE)
- Clause 2: Covenant Not To Sue (VALID_CANDIDATE)
- Clause 3: Renewal Term (VALID_CANDIDATE)
- Clause 4: Irrevocable Or Perpetual License (VALID_CANDIDATE)

## Deterministic interaction candidates
- DET-INCORPORATED-UNREAD
- DET-PRECEDENCE-OVERRIDE

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
- Full response, manifest, trace and per-finding exports are under data/runs/56a13430f537613f-460547d488bfb3a2.
