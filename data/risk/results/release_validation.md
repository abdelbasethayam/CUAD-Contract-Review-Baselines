# Phase 2 Release Validation

**Status: PASS**
Started UTC: 2026-10-11T01:02:37.304096+00:00
Finished UTC: 2026-10-11T01:03:08.351178+00:00
Elapsed seconds: 31.047
Git HEAD: 630350a5d9010004f1c7653ba48d48a3a09c0924

| Check | Result | Duration (s) |
|---|---:|---:|
| compileall | PASS | 0.051 |
| evaluation_integrity | PASS | 2.972 |
| playbook_domain_validation | PASS | 0.043 |
| team_export | PASS | 0.055 |
| cross_document_scenario_build | PASS | 0.046 |
| cross_document_scenario_audit | PASS | 0.046 |
| cross_document_model_scenarios | PASS | 2.512 |
| render_cross_document_model_report | PASS | 0.038 |
| compare_cross_document_model_runs | PASS | 0.045 |
| upload_smoke_audit_current | PASS | 0.072 |
| upload_smoke_audit_batching | PASS | 0.073 |
| upload_smoke_audit_post_batching | PASS | 0.069 |
| upload_smoke_audit_txt_3pass | PASS | 0.058 |
| upload_smoke_audit_pdf | PASS | 0.054 |
| upload_smoke_audit_txt_single_pass | PASS | 0.059 |
| local_hashing_category_baseline | PASS | 9.189 |
| phase2_report | PASS | 0.121 |
| backend_tests | PASS | 15.542 |

## Interpretation

These checks validate implementation/data integrity, not custom-risk accuracy. Human-gold annotations are still absent. Review captured stdout/stderr in the JSON file for detailed counts and warnings.

## SHA-256

- data/risk/EVALUATION_INTEGRITY_REPORT.json: 22c888f4febc428e4f4878314134726558984fb59271993ac28ca69fd73b464a
- data/risk/results/phase2_reproducible_report.json: bf694de4e74a250e434dd0c6dc3ee576a70a86a14eacbb806141f7c2a3559984
- data/risk/results/local_hashing_cuad_index_manifest.json: c299acabf364e3e1d8bec192e7032d645b01865daa5d01ed5d47894393cae29e
- data/risk/results/local_hashing_index_manifest.json: ab5f81305f77e638b656a294becd675e66a32c0d98db26aa6a6e7e3094c688f9
- data/risk/results/legal_knowledge_retrieval_validation.json: 3e14f8f94bf1a60d1b57cf8c0a6aeffeab4a2e90052338605a474ea07fdc0cf0
- data/risk/results/smoke_upload_api_result.json: bfbe62136d6b030bf0e07360d508708658e5d13ec8bf5fd9b40ee852d788bd53
- data/risk/results/smoke_test_audit.json: 0659116be612bf20b6fba63e4cb9c580341189d10f6543bb86eb6cdaaf27de03
- data/risk/results/smoke_upload_api_current_20261009.json: 4f505a3590be9a206d9376d73269b6f8fc78495ca5c3476d7fdeb269ad7b13cf
- data/risk/results/smoke_test_audit_current.json: 61b11483758f1c9a870a548b5363965e9d8d4df43c306adcd3ec9314a9192cbf
- data/risk/results/smoke_upload_api_batching_20261009.json: 2a36817d69f72a7deb77ab405a4f16a2873503ece996bd07fe1186f1f9d6b485
- data/risk/results/smoke_test_audit_batching.json: 0ecd6134ea51112676d198a653b5449cc7d92d5bf4878cae3781eef96ca81f3a
- data/risk/results/smoke_upload_api_post_batching_20261009.json: d6b0733e2568a120448280c13f1fdce4b19bdf59162cb94f7d0e84d5cc76b832
- data/risk/results/smoke_test_audit_post_batching.json: 97bdd3d04ad223757922c9635d5051f8c6cb7e0558f87ea3d9ec40efb304247a
- data/risk/results/smoke_upload_api_fast_result.json: 4472e6e4d897b288d4eaffda6fc05c5727f492e7f01a36d48dd2838f01de0dea
- data/risk/results/smoke_test_audit_fast.json: 151d03156413e2a55629824876b8c29f6021542deab867e1304d56bfa166b698
- data/risk/results/smoke_upload_api_pdf_result.json: 04c7c8260550c38d8f8c172f6a236c94e64f839295fdd90cb0894fc28cab1294
- data/risk/results/smoke_test_audit_pdf.json: f3f514aa899c8fb2ca6665fa8b52560958a7a4df45b1a5d4b917039c9496a780
- data/risk/results/local_hashing_cuad_retrieval_baseline.json: 36f83e7dfacf0d62c408ad77a800d1d380281c071bce2aa4b047fc0d3810d9c1
- data/risk/results/cross_document_scenario_audit.json: 3bf9d640c3a53d352f171e0650711e61e33d274928b0761c76b3b037f9627ed8
- data/risk/evaluation/cross_document_v1/scenario_matrix.jsonl: 3f97fabbe7882d943d51fadfcaf76b5e3c3ad84d48f687437d14e112f213acbc
- data/risk/evaluation/cross_document_v1/manifest.json: 64b99ca4dfd3c99e08f943391a5550cefec3a0e5b51f8e265b5ade6ab8a15737
- data/risk/results/cross_document_model_scenarios.jsonl: fd4bba65bec0f12367bf97f1c5d7c32a2de541e6bda6e4b347e52a1e403c968f
- data/risk/results/cross_document_model_scenarios.csv: 02cd18acd70d7a85dfb31d87d16811460c36d745cfee86640b4039b4c5b06200
- data/risk/results/cross_document_model_scenarios_summary.json: f1cb5618234e26765a0ab163ec3968864c3f9f2175fb8c5191e9d855d175dcc6
- data/risk/results/cross_document_model_scenarios_summary.md: 4e446fd15d517064437525845859debb861d8345ea4b129ff59d57abfa8e42d9
- data/risk/results/cross_document_model_scenario_comparison.json: 1d02cf196852f8a9962a988c7d3346559ec3320eb3f4108c9b3f521c7559a797
- data/risk/results/cross_document_model_scenario_comparison.md: b99a83d16a8286f741b0045cca985a4b52ae5f8ed2efcb35b3a9e43e91906373
- scripts/risk/compare_cross_document_model_runs.py: 0f775ed4acd03a94157975357917b2e6dbf4b62185e974ed06d067138163af22
- scripts/risk/render_cross_document_model_report.py: aaedd2b0603d01e6fce90334fadb54add88d077566924159e1e5250b418ab12a
- data/risk/team_export/export_manifest.json: bab78a035a40428b4f544432650f655b43d234e852778d50dd9a165bfb4b4155
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