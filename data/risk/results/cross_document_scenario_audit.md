# Cross-Clause / Document-Level Scenario Audit

Status: PASS

- Synthetic scenarios: 39
- Checks covered: 13 (10 cross-clause + 3 document-level)
- Scenario classes: {'positive': 13, 'control': 13, 'incomplete': 13}
- Expected behavior distribution: {'POTENTIAL_RISK': 14, 'NO_RISK': 13, 'INSUFFICIENT_EVIDENCE': 12}

## Invariants

- [x] all_13_cross_document_checks_covered
- [x] all_expected_39_scenarios_present
- [x] three_scenario_types_have_13_cases_each
- [x] all_scenarios_have_canonical_domains
- [x] all_expected_evidence_anchors_exist
- [x] all_fixture_hashes_match
- [x] all_fixture_files_exist
- [x] synthetic_non_gold_label_is_explicit
- [x] playbook_hash_matches_manifest
- [x] manifest_case_count_matches

## Interpretation

This is a synthetic fixture-integrity/coverage audit. It verifies that each cross-clause/document check has positive, protected-control and incomplete-context stimuli with the recorded text anchors. It does not prove the LLM makes the expected decision, does not estimate generalization, and is not human gold.

## Hashes

- Playbook: e677e1d1e88deb1f9c2cb30c0cd994b1b6835cda593804c807941a11c5e04440
- Taxonomy: ebf0dea3cfcc97bb53e488265d8ef507339ba587fc660f3f942822d50ce0d218
- Scenario matrix: 3f97fabbe7882d943d51fadfcaf76b5e3c3ad84d48f687437d14e112f213acbc
