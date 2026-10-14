"""Surprise engine — sudden modulations, now aware of the story state.

A surprise is a *key change that still resolves*: it must change how the scene
is read without contradicting confirmed facts. Candidates are filtered by
applicability to the current StoryState, may reference a concrete fact / thread
/ motif, and are chosen reproducibly by the shared RNG.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from core.story_state import StoryState


@dataclass
class Surprise:
    category: str
    detail: str
    intensity: float
    target: str = ""

    def directive(self) -> str:
        base = f"转折（{self.category}）：{self.detail}"
        if self.target:
            base += f"（关联：{self.target}）"
        return base

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "detail": self.detail,
            "intensity": self.intensity,
            "target": self.target,
        }


# category -> (details, needs) where needs ∈ {"facts","threads","motifs"} ------
_CATEGORIES: Dict[str, Tuple[List[str], Tuple[str, ...]]] = {
    "隐藏关系": ([
        "两个看似无关的人，其实共享同一个秘密。",
        "对手与主角之间有血缘或旧交，一直未被点破。",
    ], ()),
    "错误记忆": ([
        "某个人物确信的版本，与记录中的事实并不一致。",
        "他记错了关键的时间或顺序，而真相正藏在这个错误里。",
    ], ("facts",)),
    "反向因果": ([
        "不是事故导致隐瞒，而是隐瞒本身引发了事故。",
        "看似后果的东西，其实是原因。",
    ], ("facts",)),
    "未知观察者": ([
        "有第三人一直在场，只是叙述里从未给他位置。",
        "某个物件的视角被短暂占据，读者先于人物察觉。",
    ], ()),
    "时间错位": ([
        "某个记录中的日期指向尚未发生的时刻。",
        "某些痕迹比事件本身更早出现。",
    ], ("facts",)),
    "物件背叛": ([
        "某个被信任的物件，透露出与人物叙述相反的信息。",
        "核心意象在本次显示出此前没有的功能。",
    ], ("motifs",)),
}


class SurpriseEngine:
    def __init__(self, rng: Optional[random.Random] = None) -> None:
        self.rng = rng or random.Random()

    def _target(self, needs: Tuple[str, ...], state: Optional[StoryState],
                motifs: Sequence[str]) -> str:
        if "facts" in needs and state and state.confirmed():
            return self.rng.choice(state.confirmed()).statement
        if "threads" in needs and state and state.open_thread_list():
            return self.rng.choice(state.open_thread_list()).question
        if "motifs" in needs and motifs:
            return self.rng.choice(list(motifs))
        return ""

    def _applicable(self, needs: Tuple[str, ...], state: Optional[StoryState],
                    motifs: Sequence[str], has_motifs: bool) -> bool:
        if "facts" in needs:
            return bool(state and state.confirmed())
        if "motifs" in needs:
            return bool(has_motifs or motifs)
        return True

    def mutate(
        self,
        level: float,
        state: Optional[StoryState] = None,
        *,
        has_motifs: bool = True,
        motifs: Sequence[str] = (),
        used_categories: Sequence[str] = (),
    ) -> List[Surprise]:
        """Return 0–3 surprises scaled by ``level``, filtered by applicability.

        Reusing a category already in ``used_categories`` is avoided so a novel
        does not lean on the same trick twice in a row.
        """
        count = 0
        if self.rng.random() < level:
            count = 1
        if level > 0.6 and self.rng.random() < (level - 0.6) * 2:
            count = 2
        if level > 0.85 and self.rng.random() < (level - 0.85) * 3:
            count = 3

        available = []
        for name, (details, needs) in _CATEGORIES.items():
            if name in used_categories:
                continue
            if not self._applicable(needs, state, motifs, has_motifs):
                continue
            available.append((name, details, needs))

        results: List[Surprise] = []
        for _ in range(count):
            if not available:
                break
            idx = self.rng.randrange(len(available))
            name, details, needs = available.pop(idx)
            detail = self.rng.choice(details)
            target = self._target(needs, state, motifs)
            results.append(Surprise(name, detail, round(level, 2), target))
        return results
