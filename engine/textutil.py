"""Tiny dependency-free text analysis (CJK-aware)."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, Iterable, List

_CJK = re.compile(r"[\u4e00-\u9fff]")
_LATIN = re.compile(r"[A-Za-z]+")


def tokens(text: str) -> List[str]:
    """Character bigrams for CJK plus lowercased latin words.

    Good enough for similarity/coverage signals without pulling in a
    segmentation model. Swap for jieba/embeddings later.
    """
    if not text:
        return []
    out: List[str] = [w.lower() for w in _LATIN.findall(text)]
    cjk = _CJK.findall(text)
    if len(cjk) == 1:
        out.append(cjk[0])
    for i in range(len(cjk) - 1):
        out.append(cjk[i] + cjk[i + 1])
    return out


def vector(text: str) -> Dict[str, float]:
    counts = Counter(tokens(text))
    total = sum(counts.values()) or 1
    return {k: v / total for k, v in counts.items()}


def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    dot = sum(w * b.get(k, 0.0) for k, w in a.items())
    na = math.sqrt(sum(w * w for w in a.values()))
    nb = math.sqrt(sum(w * w for w in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def similarity(a_text: str, b_text: str) -> float:
    return cosine(vector(a_text), vector(b_text))


def contains_any(text: str, needles: Iterable[str]) -> int:
    return sum(1 for n in needles if n and n in text)


def coverage(text: str, needles: Iterable[str]) -> float:
    items = [n for n in needles if n]
    if not items:
        return 0.0
    return contains_any(text, items) / len(items)


def char_ngrams(text: str, n: int = 4) -> List[str]:
    cjk = _CJK.findall(text)
    if len(cjk) < n:
        return cjk
    return ["".join(cjk[i:i + n]) for i in range(len(cjk) - n + 1)]


def repetition_ratio(text: str, n: int = 4) -> float:
    grams = char_ngrams(text, n)
    if not grams:
        return 0.0
    return 1.0 - (len(set(grams)) / len(grams))


def lexical_diversity(text: str) -> float:
    toks = tokens(text)
    if not toks:
        return 0.0
    return len(set(toks)) / len(toks)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))
