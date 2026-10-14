"""Motif engine — same figure, meaning mutated on each return.

The whole point of a jazz motif is that it is *not* repeated verbatim. Each
appearance advances one stage further from the literal.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Sequence

from core.motif import Motif, MotifLibrary

STAGES = {1: "literal", 2: "symbolic", 3: "psychological", 4: "philosophical"}

STAGE_HINT = {
    "literal": "直陈其物：它是可触摸、可测量的实体。",
    "symbolic": "让它承载隐喻，物象开始发光、指向别处。",
    "psychological": "让它与记忆、恐惧、欲望发生短路。",
    "philosophical": "让它指向不可名状之物，成为某种命题的化身。",
}


@dataclass
class MotifVariation:
    name: str
    stage: int
    mode: str
    hint: str

    def directive(self) -> str:
        return f"{self.name}：第 {self.stage} 次变奏（{self.mode}）— {self.hint}"

    def to_dict(self) -> dict:
        return {"name": self.name, "stage": self.stage, "mode": self.mode, "hint": self.hint}


class MotifEngine:
    def __init__(
        self,
        library: MotifLibrary,
        reuse: float = 0.8,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.library = library
        self.reuse = reuse
        self.rng = rng or random.Random()

    # expert-suggested API
    def transform(self, motif: Motif, stage: int) -> str:
        return STAGES.get(max(1, min(4, stage)), "literal")

    def plan(self, active: Optional[Sequence[str]] = None, chapter: int = 1) -> List[MotifVariation]:
        names = list(active) if active else self.library.names()
        variations: List[MotifVariation] = []
        for name in names:
            if self.rng.random() > self.reuse:
                continue
            motif = self.library.get(name)
            stage = max(1, min(4, motif.count + 1))
            mode = self.transform(motif, stage)
            variations.append(
                MotifVariation(name=name, stage=stage, mode=mode, hint=STAGE_HINT[mode])
            )
        return variations
