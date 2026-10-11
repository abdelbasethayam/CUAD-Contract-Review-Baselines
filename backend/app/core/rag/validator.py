"""
Lightweight validation pass over segmenter.py's output.

The deterministic contract boundary layer can occasionally mis-split text
(e.g. a stray sentence fragment from a multi-line ALL-CAPS clause getting
treated as its own "clause" -- see the
"GIVING RISE TO LIABILITY." case discussed while testing on real CUAD
contracts).

This module does NOT let the LLM do segmentation itself -- that would
require it to see the whole contract at once (far beyond a small local
model's context window) and risks the model paraphrasing/dropping legal
text, which is unacceptable. Instead, each ALREADY-SPLIT chunk is checked
independently with a minimal yes/no prompt: "is this a real contract
clause, or drafting commentary / a stray fragment?" This is cheap (no
label list, no retrieved examples, no extracted features in the prompt)
and keeps the model's job narrow enough that a 1.5B local model can do it
reliably.

Location: app/core/rag/validator.py
"""

from __future__ import annotations

import json

import requests

from ..config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS, OLLAMA_MAX_RETRY_ATTEMPTS

VALIDATOR_PROMPT_TEMPLATE = """You are checking whether a text fragment extracted from a contract is a real, complete contractual clause.

A real clause states a right, obligation, restriction, definition, or other substantive contract term.
NOT a real clause: a stray sentence fragment, a drafting note/footnote/commentary about the contract, a page header or footer, or a fragment that is clearly cut off mid-thought with no standalone meaning.

Fragment:
"{text}"

Respond with ONLY a JSON object in this exact format, nothing else:
{{"is_clause": true}} or {{"is_clause": false}}
"""


def _call_ollama_validator(prompt: str) -> str:
    """Minimal Ollama call reserved for segmentation validation.

    This provider is isolated from final CUAD classification and contract-risk
    assessment.
    """
    last_error: Exception | None = None

    for attempt in range(1, OLLAMA_MAX_RETRY_ATTEMPTS + 1):
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "think": False,
                    "options": {
                        "temperature": 0,
                        # Respect the configured Ollama server / GPU placement.
                        # num_gpu=0 forced every clause validation onto the CPU.
                        "use_mmap": True,
                        "num_ctx": 512,  # prompt is tiny, no need for 4096 here
                    },
                },
                timeout=OLLAMA_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return str(response.json()["response"])
        except Exception as exc:
            last_error = exc
            if attempt < OLLAMA_MAX_RETRY_ATTEMPTS:
                continue

    raise RuntimeError(
        f"Ollama validator call failed after {OLLAMA_MAX_RETRY_ATTEMPTS} attempts."
    ) from last_error


def is_real_clause(clause_text: str, fail_open: bool = True) -> bool:
    """Ask the local model whether this fragment is a real contract clause.

    fail_open: if the model call fails or returns something unparseable,
    default to True (treat it as a real clause) rather than silently
    dropping content the regex segmenter already thought was worth
    keeping. Set False if you'd rather fail closed (drop on any doubt).
    """
    prompt = VALIDATOR_PROMPT_TEMPLATE.format(text=clause_text)

    try:
        raw_response = _call_ollama_validator(prompt)
    except RuntimeError:
        return fail_open

    try:
        parsed = json.loads(raw_response)
        return bool(parsed.get("is_clause", fail_open))
    except (json.JSONDecodeError, AttributeError):
        # Fallback: look for "true"/"false" literally in the raw text.
        lowered = raw_response.lower()
        if "true" in lowered and "false" not in lowered:
            return True
        if "false" in lowered and "true" not in lowered:
            return False
        return fail_open
