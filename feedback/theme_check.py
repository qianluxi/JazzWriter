"""Is the theme still audible — without being stated?"""

from __future__ import annotations

from core.theme import Theme
from engine import textutil as tu


def check(text: str, theme: Theme) -> float:
    symbol_cov = tu.coverage(text, theme.symbols + theme.motifs)
    anchor_cov = tu.coverage(text, theme.keywords)
    blob = " ".join(theme.keywords)
    theme_cos = tu.similarity(text, blob) if blob else 0.0
    return tu.clamp(0.5 * symbol_cov + 0.3 * anchor_cov + 0.2 * tu.clamp(theme_cos * 6))


score = check
