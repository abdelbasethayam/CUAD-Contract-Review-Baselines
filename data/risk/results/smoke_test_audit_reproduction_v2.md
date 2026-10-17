# End-to-End Upload Smoke Test Audit

**Status:** PASS
**Interpretation:** Synthetic plumbing test only—not an accuracy benchmark.
Analysis ID: abdc407021e71b3b-d0b6e5ae9606055e
Input: /home/jovyan/CUAD-Contract-Review-Baselines/data/risk/demo_contract_for_reproduction.txt
Input SHA-256: abdc407021e71b3bd69aef03197895be5080fb2fa44550c9a0d6a7573446f8c5
Runtime seconds: 884.862
Git commit in manifest: 8c373301b194081ec03d6a2198724b8edb90112e
Code fingerprint: a1b1bf8bb6ed5d6719ca9902003976a997a9ebef7ee310713966a845b71c08f6
Playbook hash: 03c41c2bd8d560824facaf4c3b0097060b199678322e465504d5ef0aa4830793

## End-to-end outcome

| Metric | Observed |
|---|---:|
| HTTP status | 200 |
| Pipeline status | COMPLETED |
| Clauses returned | 11 |
| Clause-level findings | 30 |
| Positive clause findings | 9 |
| Positive quotes in target clause | 9 |
| Positive quotes from related clause | 0 |
| Invalid/unmapped positive quotes | 0 |
| Cross-clause status counts | {"INSUFFICIENT_EVIDENCE": 6, "POTENTIAL_RISK": 4} |
| Document status counts | {"POTENTIAL_RISK": 1, "INSUFFICIENT_EVIDENCE": 2} |
| Valid positive cross/document results | 5 |
| Overall triage | POTENTIAL_RISK / HIGH |
| Legal guidance matches | 27 across 9 searches |

## Clause classifications
- Clause 1: Renewal Term (VALID_CANDIDATE)
- Clause 2: Minimum Commitment (VALID_CANDIDATE)
- Clause 3: Cap On Liability (VALID_CANDIDATE)
- Clause 4: Uncapped Liability (VALID_CANDIDATE)
- Clause 5: Termination For Convenience (VALID_CANDIDATE)
- Clause 6: Ip Ownership Assignment (VALID_CANDIDATE)
- Clause 7: Insurance (VALID_CANDIDATE)
- Clause 8: Anti-Assignment (VALID_CANDIDATE)
- Clause 9: NO_APPLICABLE_LABEL (NO_APPLICABLE_LABEL)
- Clause 10: Governing Law (VALID_CANDIDATE)
- Clause 11: Post-Termination Services (VALID_CANDIDATE)

## Deterministic interaction candidates
- DET-SCOPE-CONFLICT
- DET-EXIT-FAILURE
- DET-REMEDY-MISMATCH
- DET-IP-CONTINUITY-GAP
- DET-EVIDENCE-GAP
- DET-PRECEDENCE-GAP
- DET-INCORPORATED-UNREAD
- DET-PRECEDENCE-OVERRIDE
- DET-DISPUTE-MECHANISM-AMBIGUITY

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
- Full response, manifest, trace and per-finding exports are under data/runs/abdc407021e71b3b-d0b6e5ae9606055e.
