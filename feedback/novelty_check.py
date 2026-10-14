"""Is this take fresh, or is the band repeating yesterday's solo?"""

from __future__ import annotations

from typing import List, Optional

from engine import textutil as tu


def check(text: str, previous_texts: Optional[List[str]] = None) -> float:
    diversity = tu.lexical_diversity(text)
    if previous_texts:
        sim = max((tu.similarity(text, p) for p in previous_texts), default=0.0)
        dissimilarity = tu.clamp(1.0 - sim * 3.0)
    else:
        dissimilarity = 0.7
    return tu.clamp(0.5 * tu.clamp(diversity / 0.85) + 0.5 * dissimilarity)


score = check
