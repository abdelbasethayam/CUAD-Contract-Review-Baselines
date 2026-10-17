# Phase 2 Release Validation

**Status: NOT RUN**

The release protocol has changed to playbook-rule conformance and classification-index isolation. The previous saved PASS record described a different check set and is not carried forward.

Run scripts/risk/run_release_checks.py with the backend stopped. The script regenerates this file and release_validation.json using the active source, rule validator, index-integrity validator, regression fixtures, upload-smoke audit and backend unit tests.

No custom risk-span annotation dataset is part of release validation. The resulting checks establish software/rule conformance and reproducibility, not legal-risk accuracy or enforceability.
