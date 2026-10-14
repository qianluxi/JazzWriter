"""Semantic similarity — optional, swappable evaluation backend.

Three modes:

- ``lexical``   — the current dependency-free bigram/overlap signal (default).
- ``embedding`` — a local sentence-embedding model, if one is installed.
- ``hybrid``    — average of lexical and embedding.

The lexical path must always work with zero extra dependencies. If the
embedding backend is missing, ``embedding``/``hybrid`` degrade gracefully to
lexical rather than failing, so nothing in the pipeline breaks offline.
"""

from __future__ import annotations

import math
import os
from typing import List, Optional

from engine import textutil as tu

MODES = ("lexical", "embedding", "hybrid")

_EMBEDDER = None  # None = not tried, False = unavailable, else model


def _get_embedder():
    global _EMBEDDER
    if _EMBEDDER is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            model_name = os.getenv("NJE_EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
            _EMBEDDER = SentenceTransformer(model_name)
        except Exception:
            _EMBEDDER = False
    return _EMBEDDER or None


def available(mode: str) -> bool:
    if mode == "lexical":
        return True
    return _get_embedder() is not None


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _embed(texts: List[str]) -> Optional[List[List[float]]]:
    model = _get_embedder()
    if model is None:
        return None
    vectors = model.encode(texts, normalize_embeddings=False)
    return [list(map(float, v)) for v in vectors]


def similarity(a: str, b: str, mode: str = "lexical") -> float:
    lexical = tu.similarity(a, b)
    if mode == "lexical":
        return lexical
    if mode not in MODES:
        raise ValueError(f"unknown eval mode: {mode!r} (use {', '.join(MODES)})")

    vectors = _embed([a, b])
    if vectors is None:
        return lexical
    emb = _cosine(vectors[0], vectors[1])
    if mode == "embedding":
        return emb
    return 0.5 * lexical + 0.5 * emb
