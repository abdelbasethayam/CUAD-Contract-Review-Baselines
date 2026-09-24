"""Optional, safe OpenRouter connectivity check.

This script never prints the API key or model reasoning. With no key it exits
without making a network request.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import (  # noqa: E402
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    openrouter_config_status,
)
from app.core.rag.generator import call_openrouter  # noqa: E402


def main() -> int:
    status = openrouter_config_status()
    print("HTTP success/failure: not attempted" if not OPENROUTER_API_KEY else "HTTP success/failure: pending")
    print(f"model: {status['model']}")
    if not OPENROUTER_API_KEY:
        print("response received: no")
        print("error: OPENROUTER_API_KEY is not configured; connectivity check skipped")
        return 0

    try:
        response = call_openrouter(
            'Return exactly this JSON object and nothing else: {"connectivity":true}'
        )
    except Exception as exc:
        print("HTTP success/failure: failure")
        print("response received: no")
        print(f"error: {exc}")
        return 1

    print("HTTP success/failure: success")
    print(f"response received: {'yes' if bool(response.strip()) else 'no'}")
    return 0 if response.strip() else 1


if __name__ == "__main__":
    raise SystemExit(main())
