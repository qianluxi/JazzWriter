"""Surprise engine — sudden modulations, not random noise.

In jazz a surprise is a *key change* that still resolves. Here a surprise must
be structural (change how the scene is read), not a random event. Intensity is
governed by ``surprise_level``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional

CATEGORIES: Dict[str, List[str]] = {
    "隐藏关系": [
        "两个看似无关的人，其实共享同一个秘密。",
        "对手与主角之间有血缘或旧交，一直未被点破。",
    ],
    "错误记忆": [
        "人物确信的一段往事，细节在本次被证伪。",
        "他记错了关键的时间或顺序，而真相正藏在这个错误里。",
    ],
    "反向因果": [
        "不是事故导致隐瞒，而是隐瞒本身引发了事故。",
        "看似后果的东西，其实是原因。",
    ],
    "未知观察者": [
        "有第三人一直在场，只是叙述里从未给他位置。",
        "某个物件的视角被短暂占据，读者先于人物察觉。",
    ],
    "时间错位": [
        "记录中的日期指向尚未发生的时刻。",
        "某些痕迹比事件本身更早出现。",
    ],
    "物件背叛": [
        "某个被信任的物件，透露出与人物叙述相反的信息。",
        "核心意象在本次显示出此前没有的功能。",
    ],
}


@dataclass
class Surprise:
    category: str
    detail: str
    intensity: float

    def directive(self) -> str:
        return f"转折（{self.category}）：{self.detail}"

    def to_dict(self) -> dict:
        return {"category": self.category, "detail": self.detail, "intensity": self.intensity}


class SurpriseEngine:
    def __init__(self, rng: Optional[random.Random] = None) -> None:
        self.rng = rng or random.Random()

    def mutate(self, level: float, story_state: Optional[dict] = None) -> List[Surprise]:
        """Return 0–2 surprises scaled by ``level`` (0..1)."""
        count = 0
        if self.rng.random() < level:
            count = 1
        if level > 0.7 and self.rng.random() < (level - 0.7) * 2:
            count = 2

        used: List[str] = []
        surprises: List[Surprise] = []
        for _ in range(count):
            category = self.rng.choice([c for c in CATEGORIES if c not in used] or list(CATEGORIES))
            used.append(category)
            detail = self.rng.choice(CATEGORIES[category])
            surprises.append(Surprise(category, detail, round(level, 2)))
        return surprises
