#!/usr/bin/env python3
"""Run the Phase 2 component ablation matrix on one or more contracts."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MATRIX = {
    "base-open-risk": {
        "RISK_USE_PLAYBOOK": "false",
        "RISK_USE_CONTEXT": "false",
        "RISK_USE_LEGAL_GUIDANCE": "false",
        "RISK_SELF_CONSISTENCY_PASSES": "1",
        "RISK_ENABLE_CROSS_CLAUSE": "false",
        "RISK_ENABLE_DOCUMENT_CHECKS": "false",
    },
    "plus-playbook": {
        "RISK_USE_PLAYBOOK": "true",
        "RISK_USE_CONTEXT": "false",
        "RISK_USE_LEGAL_GUIDANCE": "false",
        "RISK_SELF_CONSISTENCY_PASSES": "1",
        "RISK_ENABLE_CROSS_CLAUSE": "false",
        "RISK_ENABLE_DOCUMENT_CHECKS": "false",
    },
    "plus-context": {
        "RISK_USE_PLAYBOOK": "true",
        "RISK_USE_CONTEXT": "true",
        "RISK_USE_LEGAL_GUIDANCE": "false",
        "RISK_SELF_CONSISTENCY_PASSES": "1",
        "RISK_ENABLE_CROSS_CLAUSE": "false",
        "RISK_ENABLE_DOCUMENT_CHECKS": "false",
    },
    "plus-guidance": {
        "RISK_USE_PLAYBOOK": "true",
        "RISK_USE_CONTEXT": "true",
        "RISK_USE_LEGAL_GUIDANCE": "true",
        "RISK_SELF_CONSISTENCY_PASSES": "1",
        "RISK_ENABLE_CROSS_CLAUSE": "false",
        "RISK_ENABLE_DOCUMENT_CHECKS": "false",
    },
    "plus-self-consistency": {
        "RISK_USE_PLAYBOOK": "true",
        "RISK_USE_CONTEXT": "true",
        "RISK_USE_LEGAL_GUIDANCE": "true",
        "RISK_SELF_CONSISTENCY_PASSES": "3",
        "RISK_ENABLE_CROSS_CLAUSE": "false",
        "RISK_ENABLE_DOCUMENT_CHECKS": "false",
    },
    "plus-cross-clause": {
        "RISK_USE_PLAYBOOK": "true",
        "RISK_USE_CONTEXT": "true",
        "RISK_USE_LEGAL_GUIDANCE": "true",
        "RISK_SELF_CONSISTENCY_PASSES": "3",
        "RISK_ENABLE_CROSS_CLAUSE": "true",
        "RISK_ENABLE_DOCUMENT_CHECKS": "false",
    },
    "full-risk": {
        "RISK_USE_PLAYBOOK": "true",
        "RISK_USE_CONTEXT": "true",
        "RISK_USE_LEGAL_GUIDANCE": "true",
        "RISK_SELF_CONSISTENCY_PASSES": "3",
        "RISK_ENABLE_CROSS_CLAUSE": "true",
        "RISK_ENABLE_DOCUMENT_CHECKS": "true",
    },
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--only", nargs="*", choices=sorted(MATRIX))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    configs = args.only or list(MATRIX)
    for name in configs:
        env = os.environ.copy()
        env.update(MATRIX[name])
        cmd = [sys.executable, str(ROOT / "scripts" / "run_pipeline.py"), "run", str(args.source)]
        print("\n###", name)
        print(" ".join(cmd))
        print(" ".join(f"{k}={v}" for k, v in MATRIX[name].items()))
        if not args.dry_run:
            subprocess.run(cmd, cwd=ROOT, env=env, check=True)


if __name__ == "__main__":
    main()
