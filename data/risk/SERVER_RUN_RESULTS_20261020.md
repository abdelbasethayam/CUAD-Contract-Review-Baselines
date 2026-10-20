# Server run-result snapshot (2026-10-20)

This snapshot records the 30 `result.json` outputs present in `data/runs/` on the project server when the snapshot was created. The archive contains one result JSON per run, stored as `<run-id>/result.json`.

## Files

- `server_run_results_20261020.tar.gz` — archived result JSON files (original JSON files total about 34.8 MiB before compression).
- `server_run_results_manifest_20261020.json` — run IDs, filenames, clause counts, file sizes, server file timestamps, and SHA-256 hashes.

## Verify

From the repository root, extract to a temporary directory:

```bash
mkdir -p /tmp/server-run-results
tar -xzf data/risk/server_run_results_20261020.tar.gz -C /tmp/server-run-results
python scripts/risk/verify_server_run_results.py /tmp/server-run-results data/risk/server_run_results_manifest_20261020.json
```

These are recorded outputs from the server, so teammates can compare their results with the exact saved server JSON. A matching output is not guaranteed across model versions, runtime configurations, or nondeterministic inference. This snapshot intentionally excludes original uploaded PDFs/text, embeddings, traces, and other run artifacts; some source documents were public SEC exhibits, while synthetic test fixtures are represented only through their generated result JSON. Treat results as research/demo evidence, not legal advice or validated legal-risk accuracy.
