# Phase 2 Release Artifact Notes

The branch `phase2/reproducible-release-20261010` contains the Phase 2 source code, tests, paper/reproducibility documents, playbook/taxonomy, human annotation queue template, machine-silver outputs, scenario matrix/model results, smoke-test responses/audits, release validation report, and retrieval baseline reports.

Two derived/packaging files are intentionally not stored in this branch:

1. **The 41 MB release ZIP** `phase2_reproducible_release_20261009.zip` was generated on the remote evaluation server. The GitHub API upload of this binary exceeded the connector's payload/transport limit. Its expected byte count and SHA-256 are retained in `phase2_reproducible_release_20261009.manifest.json`; that hash describes the server-generated archive, not a file available in this branch.
2. **The >100 MB derived expert-presence JSONL** `data/risk/external/cuad_expert_test.jsonl` is excluded as an oversized single Git file. Its preparation script and manifest are in the repository so it can be regenerated from the source data.

To regenerate these derived artifacts, first inspect the command options and provenance:

```bash
python scripts/risk/prepare_cuad_expert_eval.py --help
python scripts/risk/package_phase2_release.py
```

The committed manifest explicitly records that the ZIP and large JSONL are not present in this branch. Do not interpret the machine-silver or synthetic scenario labels as human gold.
