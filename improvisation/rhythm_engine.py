"""Rhythm engine — narrative tempo and information release.

A solo has a *feel*: a ballad breathes, bebop chops, free jazz refuses the
bar line. This chooses the prosodic feel of a take and tells the writer how to
pace sentences and how fast to release information.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class Rhythm:
    name: str
    pace: str
    release: str
    hint: str

    def describe(self) -> str:
        return f"{self.name}（{self.pace}；信息释放{self.release}）— {self.hint}"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "pace": self.pace,
            "release": self.release,
            "hint": self.hint,
        }


PATTERNS: Dict[str, Rhythm] = {
    "adagio": Rhythm("adagio", "慢板，长句为主", "缓慢",
                      "让一个动作占满一段，允许沉默与停顿。"),
    "swing": Rhythm("swing", "摇曳，长短句交替", "中等",
                    "句尾稍稍延宕，像呼吸一样有重音。"),
    "bebop": Rhythm("bebop", "快，短句切分", "密集",
                    "信息一段接一段抛出，句短、转折硬。"),
    "ballad": Rhythm("ballad", "抒情，舒展", "渐次",
                     "先铺情绪，再让事件到来，留一个柔软收束。"),
    "free": Rhythm("free", "不规则，随时变拍", "跳脱",
                   "句长失控地变化，拒绝整齐，允许离题。"),
}

# default feel per improvisation mode
MODE_DEFAULT = {
    "classic_jazz": "swing",
    "bebop": "bebop",
    "free_jazz": "free",
}


class RhythmEngine:
    def __init__(self, rng: Optional[random.Random] = None) -> None:
        self.rng = rng or random.Random()

    def choose(self, mode: str = "classic_jazz", creativity: float = 0.5) -> Rhythm:
        default = MODE_DEFAULT.get(mode, "swing")
        # higher creativity can wander to a different feel
        if self.rng.random() < creativity * 0.5:
            return self.rng.choice(list(PATTERNS.values()))
        return PATTERNS[default]
