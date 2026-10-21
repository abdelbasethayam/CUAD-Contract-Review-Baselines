"""Ollama / OpenAI-compatible client for Qwen3 Thinking models.

Qwen3-4B-Thinking-2507 emits internal reasoning (often in <think>...</think>)
before the final answer. Classification must parse the *final* JSON only.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import requests

from ..config import (
    CHAT_PROVIDER,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_CHAT_MODEL,
    OPENROUTER_TIMEOUT_SECONDS,
    OLLAMA_MAX_RETRY_ATTEMPTS,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    OLLAMA_URL,
    CLASSIFIER_THINK,
)

logger = logging.getLogger(__name__)

_THINK_BLOCK = re.compile(
    r"<think>(.*?)</think>",
    re.IGNORECASE | re.DOTALL,
)
_JSON_OBJECT = re.compile(r"\{[^{}]*\}", re.DOTALL)


def strip_thinking(text: str) -> str:
    """Remove thinking blocks; return residual text (hopefully JSON)."""
    if not text:
        return ""
    cleaned = _THINK_BLOCK.sub("", text).strip()
    # Some stacks use plain "Thinking:" prefixes without tags
    if cleaned.lower().startswith("thinking"):
        parts = re.split(r"\n\s*\n", cleaned, maxsplit=1)
        if len(parts) == 2:
            cleaned = parts[1].strip()
    return cleaned


def extract_json_object(text: str) -> dict[str, Any] | None:
    residual = strip_thinking(text)
    try:
        obj = json.loads(residual)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    # Last JSON-looking object in the string
    matches = list(_JSON_OBJECT.finditer(residual))
    for match in reversed(matches):
        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def call_thinking_ollama(
    prompt: str,
    *,
    model: str | None = None,
    temperature: float = 0.1,
    num_ctx: int = 8192,
    think: bool | None = None,
    max_tokens: int | None = None,
) -> str:
    """Call the configured local or hosted model and return its raw text."""
    selected = model or OLLAMA_MODEL
    if CHAT_PROVIDER == "openrouter":
        if not OPENROUTER_API_KEY:
            raise RuntimeError("CHAT_PROVIDER=openrouter requires OPENROUTER_API_KEY.")
        response = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "X-Title": "CUAD Contract Review Demo",
            },
            json={
                "model": OPENROUTER_CHAT_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": int(max_tokens or 700),
                "response_format": {"type": "json_object"},
            },
            timeout=OPENROUTER_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        choices = response.json().get("choices") or []
        content = (choices[0].get("message") or {}).get("content") if choices else None
        if isinstance(content, str) and content.strip():
            return content
        raise RuntimeError("OpenRouter returned an empty model response.")

    last_error: Exception | None = None

    for attempt in range(1, OLLAMA_MAX_RETRY_ATTEMPTS + 1):
        try:
            response = requests.post(
                f"{OLLAMA_URL.rstrip('/')}/api/generate",
                json={
                    "model": selected,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "think": CLASSIFIER_THINK if think is None else bool(think),
                    "options": {
                        "temperature": temperature,
                        "num_ctx": num_ctx,
                        **({"num_predict": int(max_tokens)} if max_tokens else {}),
                    },
                },
                timeout=OLLAMA_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            content = response.json().get("response")
            if isinstance(content, str) and content.strip():
                return content
            raise RuntimeError("Empty Ollama response")
        except Exception as exc:
            last_error = exc
            logger.error(
                "thinking ollama failed attempt=%s model=%s err=%s",
                attempt,
                selected,
                str(exc)[:400],
            )
            if attempt < OLLAMA_MAX_RETRY_ATTEMPTS:
                time.sleep(2 ** (attempt - 1))

    raise RuntimeError(
        f"Ollama thinking call failed after {OLLAMA_MAX_RETRY_ATTEMPTS} attempts "
        f"for model '{selected}'"
    ) from last_error


def classify_with_thinking(
    prompt: str,
    *,
    model: str | None = None,
) -> tuple[str | None, str]:
    """Return (clause_type or None, raw_response)."""
    raw = call_thinking_ollama(prompt, model=model)
    obj = extract_json_object(raw)
    if not obj:
        return None, raw
    label = obj.get("clause_type")
    if isinstance(label, str) and label.strip():
        return label.strip(), raw
    return None, raw
