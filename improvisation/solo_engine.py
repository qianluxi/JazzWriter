"""Solo engine — every character hears the same event differently.

An engineer solos on mechanism; a child solos on sound and fear; an elder solos
on the past. This derives a solo *instrument* and a lens (attention / blindspot
/ memory-filter) from the character's own fields, so the same scene yields a
different story per soloist.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from core.character import Character

INSTRUMENTS = ["萨克斯", "钢琴", "小号", "低音贝斯", "鼓", "单簧管"]


@dataclass
class SoloStyle:
    character: str
    instrument: str
    attention: str
    blindspot: str
    memory_filter: str

    def describe(self) -> str:
        return (
            f"{self.character} 以「{self.instrument}」独奏 —— "
            f"关注: {self.attention}；盲点: {self.blindspot}；"
            f"记忆滤镜: {self.memory_filter}"
        )

    def to_dict(self) -> dict:
        return {
            "character": self.character,
            "instrument": self.instrument,
            "attention": self.attention,
            "blindspot": self.blindspot,
            "memory_filter": self.memory_filter,
        }


class CharacterSolo:
    def generate_style(self, character: Character) -> SoloStyle:
        # attention = what they reliably notice (desire / worldview)
        attention = character.desire or character.worldview or "眼前的细节"
        # blindspot = what they systematically miss (fear / contradiction)
        blindspot = character.contradiction or character.fear or "自己的动机"
        # memory filter = the past that colors the present
        memory = character.memory or "一段说不清的往事"
        return SoloStyle(
            character=character.name,
            instrument=self._instrument(character),
            attention=attention,
            blindspot=blindspot,
            memory_filter=memory,
        )

    @staticmethod
    def _instrument(character: Character) -> str:
        key = f"{character.name}|{character.voice}|{character.role}"
        idx = int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16) % len(INSTRUMENTS)
        return INSTRUMENTS[idx]
