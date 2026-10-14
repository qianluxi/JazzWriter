"""Randomizer — the "jazz seed".

Each performance is dealt a hand of *color*: an emotion, a perspective, and a
symbol. At low randomness the hand is drawn from the theme's own palette (stay
in key); at high randomness it can pull an outside note (controlled divergence).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Sequence

# outside-the-theme palette ("outside notes")
OUTSIDE_EMOTIONS = ["压抑", "温暖", "疏离", "荒诞", "平静", "锋利", "怀旧", "眩晕"]
OUTSIDE_PERSPECTIVES = ["旁观者", "主角", "陌生人", "对手", "目击者", "回溯者"]
OUTSIDE_SYMBOLS = ["旧钟", "雨", "灰尘", "裂缝", "镜面", "余温", "锈", "空白"]
ANGLES = [
    "从气味开始，而不是从视觉开始",
    "从一个错误的日期开始",
    "从一件不该出现在此地的东西开始",
    "从一种无法解释的余温开始",
    "从一句话的后半截开始",
    "从声音消失之后开始",
]


@dataclass
class JazzSeed:
    emotion: str = ""
    perspective: str = ""
    symbol: str = ""
    angle: str = ""

    def to_dict(self) -> dict:
        return {
            "emotion": self.emotion,
            "perspective": self.perspective,
            "symbol": self.symbol,
            "angle": self.angle,
        }

    def describe(self) -> str:
        parts = []
        if self.emotion:
            parts.append(f"情绪色 {self.emotion}")
        if self.perspective:
            parts.append(f"视角 {self.perspective}")
        if self.symbol:
            parts.append(f"种子象征 {self.symbol}")
        if self.angle:
            parts.append(f"切入 {self.angle}")
        return "，".join(parts) or "(无)"


class Randomizer:
    def __init__(self, rng: Optional[random.Random] = None) -> None:
        self.rng = rng or random.Random()

    def _draw(self, level: float, inside: Sequence[str], outside: Sequence[str]) -> str:
        inside = [x for x in inside if x]
        pool = outside if (not inside or self.rng.random() < level) else inside
        return self.rng.choice(pool)

    def seed(
        self,
        *,
        level: float = 0.4,
        emotions: Sequence[str] = (),
        perspectives: Sequence[str] = (),
        symbols: Sequence[str] = (),
        angle_chance: float = 0.0,
    ) -> JazzSeed:
        return JazzSeed(
            emotion=self._draw(level, emotions, OUTSIDE_EMOTIONS),
            perspective=self._draw(level, perspectives, OUTSIDE_PERSPECTIVES),
            symbol=self._draw(level, symbols, OUTSIDE_SYMBOLS),
            angle=self.rng.choice(ANGLES) if self.rng.random() < angle_chance else "",
        )

    def chance(self, p: float) -> bool:
        return self.rng.random() < p

    def pick(self, seq: Sequence) -> object:
        return self.rng.choice(seq)

    def sample(self, seq: Sequence, k: int) -> List:
        k = max(0, min(k, len(seq)))
        return self.rng.sample(list(seq), k) if k else []
