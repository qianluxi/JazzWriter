"""Is the soloist actually present and in character?"""

from __future__ import annotations

from core.character import Character
from engine import textutil as tu


def check(text: str, character: Character) -> float:
    name_hit = 1.0 if (
        (character.name and character.name in text)
        or any(a and a in text for a in character.aliases)
    ) else 0.0
    blob = " ".join(
        v
        for v in (
            character.desire,
            character.fear,
            character.memory,
            character.worldview,
            character.voice,
            character.contradiction,
        )
        if v
    )
    char_cos = tu.similarity(text, blob) if blob else 0.0
    return tu.clamp(0.55 * name_hit + 0.45 * tu.clamp(char_cos * 8))


score = check
