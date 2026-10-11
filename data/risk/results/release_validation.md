# Phase 2 Release Validation

**Status: PASS**
Started UTC: 2026-10-11T01:32:52.099874+00:00
Finished UTC: 2026-10-11T01:33:22.160382+00:00
Elapsed seconds: 30.061
Git HEAD: ae90391b260146f941fd0a4d4979a25fa4ce2cd3

| Check | Result | Duration (s) |
|---|---:|---:|
| compileall | PASS | 0.05 |
| evaluation_integrity | PASS | 3.938 |
| playbook_domain_validation | PASS | 0.044 |
| team_export | PASS | 0.054 |
| cross_document_scenario_build | PASS | 0.047 |
| cross_document_scenario_audit | PASS | 0.045 |
| cross_document_model_scenarios | PASS | 2.557 |
| render_cross_document_model_report | PASS | 0.037 |
| compare_cross_document_model_runs | PASS | 0.045 |
| upload_smoke_audit_current | PASS | 0.072 |
| upload_smoke_audit_batching | PASS | 0.072 |
| upload_smoke_audit_post_batching | PASS | 0.067 |
| upload_smoke_audit_txt_3pass | PASS | 0.059 |
| upload_smoke_audit_pdf | PASS | 0.054 |
| upload_smoke_audit_txt_single_pass | PASS | 0.059 |
| local_hashing_category_baseline | PASS | 9.27 |
| phase2_report | PASS | 0.121 |
| backend_tests | PASS | 13.469 |

## Interpretation

These checks validate implementation/data integrity, not custom-risk accuracy. Human-gold annotations are still absent. Review captured stdout/stderr in the JSON file for detailed counts and warnings.

## SHA-256

- data/risk/EVALUATION_INTEGRITY_REPORT.json: f21076f7ef121103bcb3451f5eb7ce222b120d6fcd08b79762d31e611a35c02a
- data/risk/results/phase2_reproducible_report.json: 9c2e5d1c1a7c0a2db52eabf89721ad4505a3a24ab854036132b05890a76c1527
- data/risk/results/local_hashing_cuad_index_manifest.json: 468f5793a56e45ecbba26f26f7ea3e76303098d3a6e6ae32d9ca12c627dc4fc1
- data/risk/results/local_hashing_index_manifest.json: 7b0eacb52d4bfa6368dff97bf5e9d939a26303e6f32df27468515d01312645a9
- data/risk/results/legal_knowledge_retrieval_validation.json: 3e14f8f94bf1a60d1b57cf8c0a6aeffeab4a2e90052338605a474ea07fdc0cf0
- data/risk/results/smoke_upload_api_result.json: bfbe62136d6b030bf0e07360d508708658e5d13ec8bf5fd9b40ee852d788bd53
- data/risk/results/smoke_test_audit.json: 47910a6e7878d1fb1f1ed9236a4cecf5ed4a1b87d2413dc486d7088b257d76ef
- data/risk/results/smoke_upload_api_current_20261009.json: 4f505a3590be9a206d9376d73269b6f8fc78495ca5c3476d7fdeb269ad7b13cf
- data/risk/results/smoke_test_audit_current.json: d357f62dd238b14dff64d1ec138f04b2657c758a5bc42b28b8be0db29b114b38
- data/risk/results/smoke_upload_api_batching_20261009.json: 2a36817d69f72a7deb77ab405a4f16a2873503ece996bd07fe1186f1f9d6b485
- data/risk/results/smoke_test_audit_batching.json: 9f892219deb171a5facdc9eb29069221633503fc973626d7f7cf250946db8bb9
- data/risk/results/smoke_upload_api_post_batching_20261009.json: d6b0733e2568a120448280c13f1fdce4b19bdf59162cb94f7d0e84d5cc76b832
- data/risk/results/smoke_test_audit_post_batching.json: d3d4e99acc183c3293b6526237d407adcdbacd90eed6566671faaf94fd5f8ed6
- data/risk/results/smoke_upload_api_fast_result.json: 4472e6e4d897b288d4eaffda6fc05c5727f492e7f01a36d48dd2838f01de0dea
- data/risk/results/smoke_test_audit_fast.json: 68b4c138a83f912a0759e37fe35b349f4990020e59db47456d6955f3f7316bc5
- data/risk/results/smoke_upload_api_pdf_result.json: 04c7c8260550c38d8f8c172f6a236c94e64f839295fdd90cb0894fc28cab1294
- data/risk/results/smoke_test_audit_pdf.json: b67f395e4f46f6151fe9dac461d80b9726512fb2be222df1e65cc1b6b49b7a6e
- data/risk/results/local_hashing_cuad_retrieval_baseline.json: 186e75d24f090f892e7331fc1f4f0db222506bcbeded6ec03346dad6802a7b81
- data/risk/results/cross_document_scenario_audit.json: aa3f871ceb31379f132d805b78045be6919993585eafb2fc8cc10b5fe9d06c49
- data/risk/evaluation/cross_document_v1/scenario_matrix.jsonl: 3f97fabbe7882d943d51fadfcaf76b5e3c3ad84d48f687437d14e112f213acbc
- data/risk/evaluation/cross_document_v1/manifest.json: 56a2696d439b96a70430ad101413d088f6f57ca5346e8af3763a16dfd9183769
- data/risk/results/cross_document_model_scenarios.jsonl: b35d724e595b6b6b9ef5d8bdb97bad0c014796a38a51dc635963087146130ead
- data/risk/results/cross_document_model_scenarios.csv: c335d81c215698a32185ffe755408b41b15c7ad9b4565d0c3851295826844f59
- data/risk/results/cross_document_model_scenarios_summary.json: df824ce6dbff5a6ba34da55ba2d81090c456eabd306ab9579f52c8fb03f7fd4c
- data/risk/results/cross_document_model_scenarios_summary.md: c86d226fe4c79fb69f1e14d802a7a03b2f9b9883caf69e1341141b3ac30f8b76
- data/risk/results/cross_document_model_scenario_comparison.json: e2387cda4e62b10c32f5aa9affc14f95378e7ca926da2003fefaa060c900d246
- data/risk/results/cross_document_model_scenario_comparison.md: 05dcf15750b6cf64a5cfbb6e6a07fe1cccffbb1e587401170675c2fe9b8e8aad
- scripts/risk/compare_cross_document_model_runs.py: 0f775ed4acd03a94157975357917b2e6dbf4b62185e974ed06d067138163af22
- scripts/risk/render_cross_document_model_report.py: aaedd2b0603d01e6fce90334fadb54add88d077566924159e1e5250b418ab12a
- data/risk/team_export/export_manifest.json: 8bae8a403bde9c4299de70f6111c6eed389c9d16094cd37a44f4483cce1b9d42
- data/risk/silver/silver_annotations_final_v5_qwen3_gemma3_20261007.csv: 12c618b4617225b9462616edaa553af23c7ac6b2a2e9527e6c0840e9b7d9230f
- data/risk/silver/silver_annotations_final_v5_qwen3_gemma3_20261007.jsonl: e81c096b0f6517b6d1f72cee08208e7f4269bb1285bf48f1853efbfd440d62ca
- data/risk/commercial_clause_risk_playbook.json: e677e1d1e88deb1f9c2cb30c0cd994b1b6835cda593804c807941a11c5e04440
- backend/data/legal_knowledge/risk_taxonomy.json: ebf0dea3cfcc97bb53e488265d8ef507339ba587fc660f3f942822d50ce0d218
- scripts/risk/smoke_upload_api.py: 3ddbf7b6986702ee131f69db16eb6d18517a32fb8e8da90a030570372b4953d5
- backend/app/core/risk/contract_checks.py: 860fb72c34c0bf9d8eecdc7247fe13d85b050821039f517346b820b17494a7a9
- scripts/risk/run_cross_document_model_scenarios.py: 9a1dd5014179cdadf882a81d50d802cb1835c723bcfe1274fc3f51138a93993f
- scripts/risk/build_cross_document_scenario_suite.py: a8102d1863c5b8968ba37abe401b2821eaa2e169d0e2f349418e0abc2d128d46
- scripts/risk/audit_cross_document_scenario_suite.py: 3bdd4d4421e26ce5c837e79d999860339d590d911f07f3954962fde8f3c20f3d
- scripts/risk/report_phase2_experiment.py: f31d9e2089ef9385d291f8b4aabeed334e0eeb238357b7e158044e18aa245b89
- scripts/risk/run_release_checks.py: 130c29d8c34b55ccc8cf529c260699c49e5fd7274e572d243be50018a87c4dd5
- docs/PHASE2_PAPER_DRAFT.md: 08679fc94a0d2d0519a127bb3b1f3debe7dec72e63396072fb9d31aa69a3acf5
- docs/PHASE2_REPRODUCIBILITY.md: 29f7d9a455d8d4c87ec1681cb0ba64a2bb67508d52ed4e50473b4206d6302abc
- docs/PHASE2_CLAIM_EVIDENCE_MATRIX.md: 5e341e9fa377d29789cfac96a8f88d976bd08bd8a120be0be52d61a4e11a702a
- docs/PHASE2_LOGICAL_MODEL.md: cb0afc854bc1f40b6ef82d772cb8c953d53dee6253512ea427b44219f05c4926
- data/risk/GOLD_STATUS.md: c092b49b6be89f41334d46c5334c35b455a0d8ea10ca4f5f4c92dc0791cd12a5
- backend/tests/test_contract_checks_batching.py: 510c238521e8a1ed74fc32580dc861b2e7a9dcdcfe8a245ff318f93a696d8411