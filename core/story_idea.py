"""StoryIdea — a story hypothesis produced by story-level improvisation.

The point of story-level divergence: two candidates must differ in their
*causal machinery* (why things happen), *truth nature*, *character relations*
or *ending direction* — not merely in style or incident.
"""

from __future__ import annotations

from typing import List

from core.base import Model


class StoryIdea(Model):
    id: str = ""
    label: str = ""                 # 简短标签
    premise: str = ""               # 一句话故事
    causal_mechanism: str = ""      # 因果机制：事情为何发生
    truth_nature: str = ""          # 真相的性质
    character_relation: str = ""    # 人物关系的关键走向
    ending_direction: str = ""      # 结局方向
    distinctness: float = 0.0       # 与基准的差异度 0..1
    rationale: str = ""             # 为什么这条路线值得探索
    differentiators: List[str] = []  # 相对其他候选的差异点

    @property
    def is_viable(self) -> bool:
        return bool(self.causal_mechanism and self.ending_direction)
