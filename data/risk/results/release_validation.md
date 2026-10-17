# Phase 2 Release Validation

**Status: PASS**
Started UTC: 2026-10-17T18:08:21.019934+00:00
Finished UTC: 2026-10-17T18:08:52.863557+00:00
Elapsed seconds: 31.844
Git HEAD: c92bae36aedfd424e3a9487622eff4f0379d2089

| Check | Result | Duration (s) |
|---|---:|---:|
| compileall | PASS | 0.05 |
| evaluation_integrity | PASS | 3.885 |
| playbook_domain_validation | PASS | 0.045 |
| team_export | PASS | 0.055 |
| cross_document_scenario_build | PASS | 0.048 |
| cross_document_scenario_audit | PASS | 0.047 |
| cross_document_model_scenarios | PASS | 2.554 |
| render_cross_document_model_report | PASS | 0.031 |
| compare_cross_document_model_runs | PASS | 0.039 |
| upload_smoke_audit_current | PASS | 0.067 |
| upload_smoke_audit_batching | PASS | 0.071 |
| upload_smoke_audit_post_batching | PASS | 0.067 |
| upload_smoke_audit_txt_3pass | PASS | 0.06 |
| upload_smoke_audit_pdf | PASS | 0.056 |
| upload_smoke_audit_txt_single_pass | PASS | 0.059 |
| local_hashing_category_baseline | PASS | 9.253 |
| phase2_report | PASS | 0.14 |
| backend_tests | PASS | 15.316 |

## Interpretation

These checks validate implementation/data integrity, not custom-risk accuracy. Human-gold annotations are still absent. Review captured stdout/stderr in the JSON file for detailed counts and warnings.

## SHA-256

- data/risk/EVALUATION_INTEGRITY_REPORT.json: f21076f7ef121103bcb3451f5eb7ce222b120d6fcd08b79762d31e611a35c02a
- data/risk/results/phase2_reproducible_report.json: e107a3d2aab80f2f0a711f4b54574d82db6ff4aabf429badee495e3cee053ba4
- data/risk/results/local_hashing_cuad_index_manifest.json: 09825e5dfe041f350f224bbd14ded171938d936c27682e4b5733644cd3392881
- data/risk/results/local_hashing_index_manifest.json: 73b350d66045082fdda9bbfb7653374fda75bbaf3e635a4efd25c0c5b494bf51
- data/risk/results/legal_knowledge_retrieval_validation.json: 3e14f8f94bf1a60d1b57cf8c0a6aeffeab4a2e90052338605a474ea07fdc0cf0
- data/risk/results/smoke_upload_api_result.json: bfbe62136d6b030bf0e07360d508708658e5d13ec8bf5fd9b40ee852d788bd53
- data/risk/results/smoke_test_audit.json: e47c92d12861d142493fc37e051c3e819a58a36694bb96934976aa7ce0f3b942
- data/risk/results/smoke_upload_api_current_20261009.json: 4f505a3590be9a206d9376d73269b6f8fc78495ca5c3476d7fdeb269ad7b13cf
- data/risk/results/smoke_test_audit_current.json: 183f0f4fe0b59e0a1e2bebfd15e3ff831bc6055ba8f577a35fc8060cbcaa2d68
- data/risk/results/smoke_upload_api_batching_20261009.json: 2a36817d69f72a7deb77ab405a4f16a2873503ece996bd07fe1186f1f9d6b485
- data/risk/results/smoke_test_audit_batching.json: 3408f7e1e61365f5b6303192aabf45cc9498a9856fe390ae237dd8cb2aa56475
- data/risk/results/smoke_upload_api_post_batching_20261009.json: d6b0733e2568a120448280c13f1fdce4b19bdf59162cb94f7d0e84d5cc76b832
- data/risk/results/smoke_test_audit_post_batching.json: df720e96de861124e8ef36e8f98d99702ed13ef10ac6d71340dd750b2fc795c0
- data/risk/results/smoke_upload_api_fast_result.json: 4472e6e4d897b288d4eaffda6fc05c5727f492e7f01a36d48dd2838f01de0dea
- data/risk/results/smoke_test_audit_fast.json: c3d8909a984352304ce7572913249ea35cac98add17e069b84d1383cc79527f6
- data/risk/results/smoke_upload_api_pdf_result.json: 04c7c8260550c38d8f8c172f6a236c94e64f839295fdd90cb0894fc28cab1294
- data/risk/results/smoke_test_audit_pdf.json: 45f386d4458e094ae2358da4421a1432830ef680c6f780db849330e8c6e5faa5
- data/risk/results/local_hashing_cuad_retrieval_baseline.json: 1726e2b11b6fed510e89d444579a54cf23875d818ff02814587a3274fad2f709
- data/risk/results/cross_document_scenario_audit.json: df1b430ab89bea2e6e3edc404e484afdba71cb1447b44350f9063d5ada4482a5
- data/risk/evaluation/cross_document_v1/scenario_matrix.jsonl: 3f97fabbe7882d943d51fadfcaf76b5e3c3ad84d48f687437d14e112f213acbc
- data/risk/evaluation/cross_document_v1/manifest.json: ac1256829296ba191462fd73092e59f73ff36f12231716089abecbe7445e8fd2
- data/risk/results/cross_document_model_scenarios.jsonl: 2fe8250ad8f4c9e298f781f30938aa0d53f6288de1bb51e3eb23c53bdb80f91a
- data/risk/results/cross_document_model_scenarios.csv: 47136360d5d9e3fd54b8efbb3d0f737cd00b08b62a8eab7978fa48b9014e6aed
- data/risk/results/cross_document_model_scenarios_summary.json: ac5d73a1f27a5931a2d1aa774c4940383e7e7d1128bbd3f6d57906df97c085e0
- data/risk/results/cross_document_model_scenarios_summary.md: 35a2e04722525295de37c62f6dacba22e1645f3b5d6a06f8a61681848b8d7d65
- data/risk/results/cross_document_model_scenario_comparison.json: a3519cdd2b8dd9b4cc9841080579a03cad669526e17e9824d2ffdec8bce08eb7
- data/risk/results/cross_document_model_scenario_comparison.md: 2d448ed0020e4ed8a05819574a86911029fc463eb45848621ee6f3905ffa91cd
- data/risk/results/metamorphic_diagnostics.json: 57b99e142fe60589d8f828857ffb806d76e1592df4cee38b82cf7354ac868885
- data/risk/results/metamorphic_diagnostics.md: bcd8d1f8c47f4e98ae919b14223274ecd35e27d73d77fdb31ac4bcc84c534cf6
- data/risk/results/llm_judge_diagnostics.json: 56a49b64cbdd72e17cda03fa277c44c91d7232bbd36df92a0d26e3037bbfd9f1
- data/risk/results/llm_judge_diagnostics.md: 55423d38212f4cae1d6422fec8d038dbfdd47b7ed30f15531d9b23c3d0369f2c
- scripts/risk/run_metamorphic_diagnostics.py: 8f017943079e27d7e8965880e976ebf6058b72069f7c9bd35c4354190dd2d79d
- scripts/risk/run_llm_judge_diagnostics.py: f7b54ec8212e2c5efaae1d76769ffe08757747dc2cc2a49678ac21c30dcb8a90
- scripts/risk/compare_cross_document_model_runs.py: 0f775ed4acd03a94157975357917b2e6dbf4b62185e974ed06d067138163af22
- scripts/risk/render_cross_document_model_report.py: aaedd2b0603d01e6fce90334fadb54add88d077566924159e1e5250b418ab12a
- data/risk/team_export/export_manifest.json: d09e74020651021582de6af1bbc48ddbe3f67b2437cd97f5aa8714d99dc63895
- data/risk/silver/silver_annotations_final_v5_qwen3_gemma3_20261007.csv: 12c618b4617225b9462616edaa553af23c7ac6b2a2e9527e6c0840e9b7d9230f
- data/risk/silver/silver_annotations_final_v5_qwen3_gemma3_20261007.jsonl: e81c096b0f6517b6d1f72cee08208e7f4269bb1285bf48f1853efbfd440d62ca
- data/risk/commercial_clause_risk_playbook.json: e677e1d1e88deb1f9c2cb30c0cd994b1b6835cda593804c807941a11c5e04440
- backend/data/legal_knowledge/risk_taxonomy.json: ebf0dea3cfcc97bb53e488265d8ef507339ba587fc660f3f942822d50ce0d218
- scripts/risk/smoke_upload_api.py: 3ddbf7b6986702ee131f69db16eb6d18517a32fb8e8da90a030570372b4953d5
- backend/app/core/risk/contract_checks.py: 860fb72c34c0bf9d8eecdc7247fe13d85b050821039f517346b820b17494a7a9
- scripts/risk/run_cross_document_model_scenarios.py: 9a1dd5014179cdadf882a81d50d802cb1835c723bcfe1274fc3f51138a93993f
- scripts/risk/build_cross_document_scenario_suite.py: a8102d1863c5b8968ba37abe401b2821eaa2e169d0e2f349418e0abc2d128d46
- scripts/risk/audit_cross_document_scenario_suite.py: 3bdd4d4421e26ce5c837e79d999860339d590d911f07f3954962fde8f3c20f3d
- scripts/risk/report_phase2_experiment.py: e15be10a8e424c9306f3f465b83d5b6ef8653029d2398eea84ae9f160a56c634
- scripts/risk/run_release_checks.py: cbf0a1a265acb09d9fce41de12720caff1ddc3250c72b0607ab04667b8b9bfc2
- docs/PHASE2_PAPER_DRAFT.md: 628ed6aee284e93fd37230a4948057978d5ad12ed95fa7f59f9a38be24badfff
- docs/PHASE2_REPRODUCIBILITY.md: 29f7d9a455d8d4c87ec1681cb0ba64a2bb67508d52ed4e50473b4206d6302abc
- docs/PHASE2_CLAIM_EVIDENCE_MATRIX.md: 5e341e9fa377d29789cfac96a8f88d976bd08bd8a120be0be52d61a4e11a702a
- docs/PHASE2_LOGICAL_MODEL.md: cb0afc854bc1f40b6ef82d772cb8c953d53dee6253512ea427b44219f05c4926
- data/risk/GOLD_STATUS.md: c092b49b6be89f41334d46c5334c35b455a0d8ea10ca4f5f4c92dc0791cd12a5
- backend/tests/test_contract_checks_batching.py: 510c238521e8a1ed74fc32580dc861b2e7a9dcdcfe8a245ff318f93a696d8411
