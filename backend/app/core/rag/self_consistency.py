"""Self-consistency voting over multiple low-temperature samples.

Useful when the thinking model flips between two close labels. Keeps the
majority vote among valid candidate labels.
"""
from __future__ import annotations

from collections import Counter
from typing import Callable


def majority_vote(
    samples: list[str | None],
    *,
    allowed: set[str] | None = None,
) -> tuple[str | None, dict[str, int]]:
    counts: Counter[str] = Counter()
    for s in samples:
        if not s:
            continue
        if allowed is not None and s not in allowed and s.lower() not in {a.lower() for a in allowed}:
            continue
        counts[s] += 1
    if not counts:
        return None, {}
    best, _ = counts.most_common(1)[0]
    return best, dict(counts)


def sample_labels(
    generate_fn: Callable[[], str | None],
    n: int = 3,
) -> list[str | None]:
    """Call generate_fn n times; generate_fn should return a label or None."""
    n = max(1, int(n))
    return [generate_fn() for _ in range(n)]
