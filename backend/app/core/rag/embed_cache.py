"""In-process LRU cache for query embeddings (avoids repeat Cohere calls)."""
from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from typing import Callable


class EmbeddingCache:
    def __init__(self, max_size: int = 2048) -> None:
        self.max_size = max_size
        self._data: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _key(text: str, model: str) -> str:
        h = hashlib.sha256(f"{model}||{text}".encode("utf-8")).hexdigest()
        return h

    def get(self, text: str, model: str) -> list[float] | None:
        k = self._key(text, model)
        with self._lock:
            if k not in self._data:
                return None
            self._data.move_to_end(k)
            return list(self._data[k])

    def put(self, text: str, model: str, vector: list[float]) -> None:
        k = self._key(text, model)
        with self._lock:
            self._data[k] = list(vector)
            self._data.move_to_end(k)
            while len(self._data) > self.max_size:
                self._data.popitem(last=False)


_GLOBAL_CACHE = EmbeddingCache()


def get_or_embed(
    text: str,
    model: str,
    embed_fn: Callable[[str], list[float]],
    *,
    cache: EmbeddingCache | None = None,
) -> list[float]:
    c = cache or _GLOBAL_CACHE
    hit = c.get(text, model)
    if hit is not None:
        return hit
    vec = embed_fn(text)
    c.put(text, model, vec)
    return vec
