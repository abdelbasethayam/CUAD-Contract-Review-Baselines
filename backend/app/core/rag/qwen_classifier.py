"""Qwen clause classifier: shortlist -> multiple-choice prompt -> letter
probabilities -> score-level fusion with the retrieval vote.

* Model answers with one letter; probabilities from first-token log-probs
  (Ollama >= 0.12), with text-parse fallback.
* Shortlist from hybrid retrieval (~96% gold-in-shortlist vs ~84% dense top-5).
* Final label = argmax alpha*log p_qwen + (1-alpha)*log p_knn - beta*log prior
"""
from __future__ import annotations

import json
import math
import string
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from .hybrid_retrieval import Hit, HybridIndex

LETTERS = string.ascii_uppercase
EPS = 1e-4

# Improved MCQ prompt: function-first, evidence as non-authoritative,
# explicit disambiguation cues, strict single-letter output.
PROMPT_TEMPLATE = """You are a senior commercial-contracts analyst performing CUAD clause typing.

Task: Choose exactly ONE category letter. Base the decision on the clause's MAIN legal function (what it grants, restricts, requires, limits, terminates, or allocates)—not on isolated keywords.

Method:
1. Read the clause and state its primary function mentally.
2. Compare that function to each category definition.
3. Treat labeled examples as evidence from other contracts only; do not copy a label merely because wording overlaps.
4. Prefer the more specific category when two options both seem plausible.
5. Common confusions:
   - Cap On Liability = monetary ceiling; Uncapped Liability = no ceiling / unlimited.
   - Non-Compete = ban on competing activity; Exclusivity = sole dealing with a counterparty.
   - License Grant = permission to use; Ip Ownership Assignment = transfer of ownership.
   - Termination For Convenience = end for any reason; Notice Period To Terminate Renewal = opt out of auto-renewal only.

Categories:
{options}

Labeled examples from other contracts (least → most similar; evidence only):
{examples}

Clause to classify:
"{clause}"

Output rules:
- Reply with exactly one letter ({letter_range}).
- No punctuation, no explanation, no label name—only the letter."""


@dataclass
class OllamaSettings:
    url: str = "http://localhost:11434"
    model: str = "qwen2.5:7b"
    num_ctx: int = 8192
    seed: int = 42
    timeout: int = 300
    retries: int = 3
    top_logprobs: int = 20


def _clip(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit].rstrip() + " ..."


def select_evidence(
    hits: list[Hit], candidates: list[str], per_label: int = 1, top_labels_extra: int = 3
) -> list[Hit]:
    chosen: list[Hit] = []
    for rank, label in enumerate(candidates):
        quota = per_label + (1 if rank < top_labels_extra else 0)
        taken = 0
        for hit in hits:
            if hit.label == label:
                chosen.append(hit)
                taken += 1
                if taken >= quota:
                    break
    chosen.sort(key=lambda h: h.rrf)
    return chosen


def build_mcq_prompt(
    clause_text: str,
    candidates: list[str],
    definitions: dict[str, str],
    evidence: list[Hit],
    example_chars: int = 600,
    clause_chars: int = 2500,
) -> str:
    options = "\n".join(
        f"{LETTERS[i]}. {label}: {definitions.get(label, '').strip()}".rstrip(": ")
        for i, label in enumerate(candidates)
    )
    examples = "\n\n".join(
        f'[Label: {hit.label}]\n"{_clip(hit.text, example_chars)}"'
        for hit in evidence
    ) or "None"
    n = len(candidates)
    letter_range = ", ".join(LETTERS[:n]) if n else "A"
    return PROMPT_TEMPLATE.format(
        options=options,
        examples=examples,
        clause=_clip(clause_text, clause_chars),
        letter_range=letter_range,
    )


def _normalise_token(token: str) -> str:
    return token.strip().strip(".:)(*\"'").upper()


def letter_probabilities(response: dict, n_options: int) -> tuple[dict[str, float], str]:
    valid = set(LETTERS[:n_options])
    logprobs = response.get("logprobs") or []
    if logprobs:
        first = logprobs[0]
        entries = list(first.get("top_logprobs") or [])
        entries.append({"token": first.get("token", ""), "logprob": first.get("logprob")})
        mass: dict[str, float] = {}
        seen: set[tuple[str, float]] = set()
        for entry in entries:
            if not entry:
                continue
            tok = _normalise_token(str(entry.get("token") or ""))
            lp = entry.get("logprob")
            if tok not in valid or lp is None:
                continue
            key = (tok, float(lp))
            if key in seen:
                continue
            seen.add(key)
            mass[tok] = mass.get(tok, 0.0) + math.exp(float(lp))
        total = sum(mass.values())
        if total > 0:
            return {k: v / total for k, v in mass.items()}, "logprobs"

    text = (response.get("response") or "").strip().upper()
    for ch in text:
        if ch in valid:
            return {ch: 1.0}, "text"
    return {}, "empty"


def call_letter_model(prompt: str, n_options: int, cfg: OllamaSettings):
    last_error: Exception | None = None
    for attempt in range(1, cfg.retries + 1):
        try:
            resp = requests.post(
                f"{cfg.url.rstrip('/')}/api/generate",
                json={
                    "model": cfg.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0,
                        "seed": cfg.seed,
                        "num_ctx": cfg.num_ctx,
                        "num_predict": 4,
                    },
                    "logprobs": cfg.top_logprobs,
                },
                timeout=cfg.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            probs, source = letter_probabilities(data, n_options)
            if probs:
                return probs, source, data.get("response") or ""
            raise RuntimeError("No letter probabilities in Ollama response")
        except Exception as exc:
            last_error = exc
            if attempt < cfg.retries:
                time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"letter model failed: {last_error}") from last_error


def score_candidates(
    clause_text: str,
    candidates: list[str],
    definitions: dict[str, str],
    hits: list[Hit],
    cfg: OllamaSettings,
    permutations: int = 1,
) -> dict:
    """Average letter probabilities over option-order permutations."""
    permutations = max(1, int(permutations))
    totals = {label: 0.0 for label in candidates}
    sources: list[str] = []
    raws: list[str] = []
    used = 0
    for perm in range(permutations):
        order = candidates[perm:] + candidates[:perm] if perm else list(candidates)
        evidence = select_evidence(hits, order)
        prompt = build_mcq_prompt(clause_text, order, definitions, evidence)
        probs, source, raw = call_letter_model(prompt, len(order), cfg)
        sources.append(source)
        raws.append(raw)
        if not probs:
            continue
        used += 1
        for letter, p in probs.items():
            if letter in LETTERS[: len(order)]:
                totals[order[LETTERS.index(letter)]] += p
    if used == 0:
        return {"p_qwen": None, "sources": sources, "raw": raws}
    return {
        "p_qwen": {label: totals[label] / used for label in candidates},
        "sources": sources,
        "raw": raws,
    }


def fuse(
    candidates: list[str],
    p_knn: dict[str, float],
    p_qwen: dict[str, float] | None,
    prior: dict[str, float],
    alpha: float,
    beta: float,
) -> tuple[str, dict[str, float]]:
    scores: dict[str, float] = {}
    for label in candidates:
        knn = math.log(p_knn.get(label, 0.0) + EPS)
        if p_qwen is None:
            llm_part, weight = 0.0, 0.0
        else:
            llm_part, weight = math.log(p_qwen.get(label, 0.0) + EPS), alpha
        scores[label] = (
            weight * llm_part
            + (1.0 - weight) * knn
            - beta * math.log(max(prior.get(label, EPS), EPS))
        )
    best = max(candidates, key=lambda name: scores[name])
    return best, scores


def load_fusion_params(path: str | Path, default=(0.6, 0.0)) -> tuple[float, float]:
    path = Path(path)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return float(data["alpha"]), float(data["beta"])
    return default


def classify_clause_hybrid(
    clause_text: str,
    query_vector,
    index: HybridIndex,
    definitions: dict[str, str],
    cfg: OllamaSettings | None = None,
    alpha: float = 0.6,
    beta: float = 0.0,
    k: int = 30,
    shortlist_size: int = 8,
    permutations: int = 1,
) -> dict:
    """Hybrid shortlist + Qwen letter probs + fusion."""
    cfg = cfg or OllamaSettings()
    hits = index.search(clause_text, query_vector, k=k)
    votes = index.label_votes(hits)
    candidates = index.shortlist(hits, size=shortlist_size)
    scored = score_candidates(clause_text, candidates, definitions, hits, cfg, permutations)
    cand_knn = {c: votes.get(c, 0.0) for c in candidates}
    norm = sum(cand_knn.values()) or 1.0
    cand_knn = {c: v / norm for c, v in cand_knn.items()}
    label, scores = fuse(candidates, cand_knn, scored["p_qwen"], index.label_prior, alpha, beta)
    return {
        "predicted_label": label,
        "candidate_labels": candidates,
        "knn_votes": cand_knn,
        "qwen_probs": scored["p_qwen"],
        "fused_scores": scores,
        "retrieved_labels": [h.label for h in hits[:10]],
        "classification_source": "qwen+hybrid_fusion" if scored["p_qwen"] else "hybrid_knn_fallback",
    }
