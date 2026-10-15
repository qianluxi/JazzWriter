"""VolumePlan — a mid-level story stage (a volume or act)."""

from __future__ import annotations

from typing import List

from pydantic import Field

from core.base import Model
from core.chapter_plan import ChapterPlan


class VolumePlan(Model):
    number: int = 1
    title: str = ""
    goal: str = ""                # 本卷目标
    opening_state: str = ""       # 开端状态
    key_turns: List[str] = Field(default_factory=list)  # 关键转折
    climax: str = ""              # 高潮
    outcome: str = ""             # 阶段性结果
    sets_up_next: str = ""        # 如何改变下一卷的条件
    chapters: List[ChapterPlan] = Field(default_factory=list)
    status: str = "candidate"

    @property
    def id(self) -> str:
        return f"vol{self.number:02d}"
