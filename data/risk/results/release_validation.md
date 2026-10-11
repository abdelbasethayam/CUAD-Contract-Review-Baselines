# Phase 2 Release Validation

**Status: PASS**
Started UTC: 2026-10-09T21:06:33.747703+00:00
Finished UTC: 2026-10-09T21:07:03.126194+00:00
Elapsed seconds: 29.378
Git HEAD: 8c373301b194081ec03d6a2198724b8edb90112e

| Check | Result | Duration (s) |
|---|---:|---:|
| compileall | PASS | 0.056 |
| evaluation_integrity | PASS | 4.335 |
| playbook_domain_validation | PASS | 0.044 |
| team_export | PASS | 0.055 |
| cross_document_scenario_build | PASS | 0.046 |
| cross_document_scenario_audit | PASS | 0.044 |
| cross_document_model_scenarios | PASS | 2.534 |
| render_cross_document_model_report | PASS | 0.037 |
| compare_cross_document_model_runs | PASS | 0.045 |
| upload_smoke_audit_current | PASS | 0.074 |
| upload_smoke_audit_batching | PASS | 0.076 |
| upload_smoke_audit_post_batching | PASS | 0.072 |
| upload_smoke_audit_txt_3pass | PASS | 0.055 |
| upload_smoke_audit_pdf | PASS | 0.046 |
| upload_smoke_audit_txt_single_pass | PASS | 0.059 |
| local_hashing_category_baseline | PASS | 9.469 |
| phase2_report | PASS | 0.117 |
| backend_tests | PASS | 12.21 |

## Interpretation

These checks validate implementation/data integrity, not custom-risk accuracy. Human-gold annotations are still absent. Review captured stdout/stderr in the JSON file for detailed counts and warnings.

## SHA-256

- data/risk/EVALUATION_INTEGRITY_REPORT.json: f21076f7ef121103bcb3451f5eb7ce222b120d6fcd08b79762d31e611a35c02a
- data/risk/results/phase2_reproducible_report.json: d5e68661e51cce0ea65f5dfcd11b3c7197afcd05a91a846552e32f1a14159650
- data/risk/results/local_hashing_cuad_index_manifest.json: c299acabf364e3e1d8bec192e7032d645b01865daa5d01ed5d47894393cae29e
- data/risk/results/local_hashing_index_manifest.json: ab5f81305f77e638b656a294becd675e66a32c0d98db26aa6a6e7e3094c688f9
- data/risk/results/legal_knowledge_retrieval_validation.json: 3e14f8f94bf1a60d1b57cf8c0a6aeffeab4a2e90052338605a474ea07fdc0cf0
- data/risk/results/smoke_upload_api_result.json: bfbe62136d6b030bf0e07360d508708658e5d13ec8bf5fd9b40ee852d788bd53
- data/risk/results/smoke_test_audit.json: c0dce11ff848c84eba6f30644ef8013d98b736d1e90032125e62964603cbf51c
- data/risk/results/smoke_upload_api_current_20261009.json: 4f505a3590be9a206d9376d73269b6f8fc78495ca5c3476d7fdeb269ad7b13cf
- data/risk/results/smoke_test_audit_current.json: 3e835422af859ca5a231e3b17adc37c86079448eaf06207d0c7dcf74c6da7e73
- data/risk/results/smoke_upload_api_batching_20261009.json: 2a36817d69f72a7deb77ab405a4f16a2873503ece996bd07fe1186f1f9d6b485
- data/risk/results/smoke_test_audit_batching.json: 0cdee8d8a4c10e7cd5ad0cc95c85ffa0b5bfcda8d9b3b2533e9772748829e774
- data/risk/results/smoke_upload_api_post_batching_20261009.json: d6b0733e2568a120448280c13f1fdce4b19bdf59162cb94f7d0e84d5cc76b832
- data/risk/results/smoke_test_audit_post_batching.json: b97ede5b69ed06e45efea9fd1a3ca4ad25e440bda7f12fc6a769d138f3a732cd
- data/risk/results/smoke_upload_api_fast_result.json: 4472e6e4d897b288d4eaffda6fc05c5727f492e7f01a36d48dd2838f01de0dea
- data/risk/results/smoke_test_audit_fast.json: 0923351ae03da2f37d86ad280af610c1c6ca5c60ddb42cfdebcb22246ba55d4e
- data/risk/results/smoke_upload_api_pdf_result.json: 04c7c8260550c38d8f8c172f6a236c94e64f839295fdd90cb0894fc28cab1294
- data/risk/results/smoke_test_audit_pdf.json: 781229f96f17687bec0140d2fcb7c49640e7efe14d7919a66294ac4f6e916134
- data/risk/results/local_hashing_cuad_retrieval_baseline.json: d17cea8099573c76d0159d0d80ee9341907eed1ada4d9a48a44772acf12f5160
- data/risk/results/cross_document_scenario_audit.json: 54a6cabfe46b3d6806e21f419a5f19766a35c48ca7ed9eebadc067bd8004b86a
- data/risk/evaluation/cross_document_v1/scenario_matrix.jsonl: 3f97fabbe7882d943d51fadfcaf76b5e3c3ad84d48f687437d14e112f213acbc
- data/risk/evaluation/cross_document_v1/manifest.json: ca5cfbc510c7ef7fbd65664de69ac2a788a69d89f2dbcb13c8932f1ea18593cb
- data/risk/results/cross_document_model_scenarios.jsonl: 32e530d1c9de04aa3811fdd17129e957d2fa31e07840da500b2085d4e9f8582c
- data/risk/results/cross_document_model_scenarios.csv: 963e784aefd56295154ebbf9a58d8a1b0d3e154c65dbd74e99449f52fae00dfe
- data/risk/results/cross_document_model_scenarios_summary.json: ee810f0bfba2074ad4a28d45144e1f8205933bee469dde02001ce31b44c5b8d2
- data/risk/results/cross_document_model_scenarios_summary.md: d4a5f5ae66372233d9221f177e43431e1b845c84e02b3f305cc5ec02afadb908
- data/risk/results/cross_document_model_scenario_comparison.json: 3ca3fcdfa27d55a5a9e7aae6f431c857b7966e617e535e69136a4f634560ded6
- data/risk/results/cross_document_model_scenario_comparison.md: 97ea3502d57d2348b218111f8e1a637ed6310052f6dfb44ab704140615292144
- scripts/risk/compare_cross_document_model_runs.py: 0f775ed4acd03a94157975357917b2e6dbf4b62185e974ed06d067138163af22
- scripts/risk/render_cross_document_model_report.py: aaedd2b0603d01e6fce90334fadb54add88d077566924159e1e5250b418ab12a
- data/risk/team_export/export_manifest.json: 82a7bcc9fae2fada9ccba622e4926cb1b0c0facc8d13e00924af22fd809fac78
- data/risk/silver/silver_annotations_final_v5_qwen3_gemma3_20261007.csv: 12c618b4617225b9462616edaa553af23c7ac6b2a2e9527e6c0840e9b7d9230f
- data/risk/silver/silver_annotations_final_v5_qwen3_gemma3_20261007.jsonl: e81c096b0f6517b6d1f72cee08208e7f4269bb1285bf48f1853efbfd440d62ca
- data/risk/commercial_clause_risk_playbook.json: e677e1d1e88deb1f9c2cb30c0cd994b1b6835cda593804c807941a11c5e04440
- backend/data/legal_knowledge/risk_taxonomy.json: ebf0dea3cfcc97bb53e488265d8ef507339ba587fc660f3f942822d50ce0d218
- scripts/risk/smoke_upload_api.py: 3ddbf7b6986702ee131f69db16eb6d18517a32fb8e8da90a030570372b4953d5
- backend/app/core/risk/contract_checks.py: 860fb72c34c0bf9d8eecdc7247fe13d85b050821039f517346b820b17494a7a9
- scripts/risk/run_cross_document_model_scenarios.py: 9a1dd5014179cdadf882a81d50d802cb1835c723bcfe1274fc3f51138a93993f
- scripts/risk/build_cross_document_scenario_suite.py: a8102d1863c5b8968ba37abe401b2821eaa2e169d0e2f349418e0abc2d128d46
- scripts/risk/audit_cross_document_scenario_suite.py: 3bdd4d4421e26ce5c837e79d999860339d590d911f07f3954962fde8f3c20f3d
- scripts/risk/report_phase2_experiment.py: ab059b452c9b9e5abe24fbf3cf593c853ad3cbf03364730f1bebb9a7fcd4a256
- scripts/risk/run_release_checks.py: 130c29d8c34b55ccc8cf529c260699c49e5fd7274e572d243be50018a87c4dd5
- docs/PHASE2_PAPER_DRAFT.md: 08679fc94a0d2d0519a127bb3b1f3debe7dec72e63396072fb9d31aa69a3acf5
- docs/PHASE2_REPRODUCIBILITY.md: 29f7d9a455d8d4c87ec1681cb0ba64a2bb67508d52ed4e50473b4206d6302abc
- docs/PHASE2_CLAIM_EVIDENCE_MATRIX.md: 5e341e9fa377d29789cfac96a8f88d976bd08bd8a120be0be52d61a4e11a702a
- docs/PHASE2_LOGICAL_MODEL.md: cb0afc854bc1f40b6ef82d772cb8c953d53dee6253512ea427b44219f05c4926
- data/risk/GOLD_STATUS.md: c092b49b6be89f41334d46c5334c35b455a0d8ea10ca4f5f4c92dc0791cd12a5
- backend/tests/test_contract_checks_batching.py: 510c238521e8a1ed74fc32580dc861b2e7a9dcdcfe8a245ff318f93a696d8411
