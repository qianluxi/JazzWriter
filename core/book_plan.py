"""BookPlan — the whole-novel blueprint (the primary artifact).

Holds the core idea, synopsis, main conflict, cast, key turns, ending and the
volume/chapter breakdown. Supports per-node status and *locking*: once the
author locks a chapter, later improvisation must not silently rewrite it, and
changing an earlier node reports which downstream chapters are affected.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional

from pydantic import Field

from core.base import Model
from core.chapter_plan import ChapterPlan
from core.story_idea import StoryIdea
from core.volume_plan import VolumePlan


class BookPlan(Model):
    title: str = ""
    logline: str = ""             # 一句话核心创意
    premise: str = ""
    question: str = ""            # 故事要处理的命题
    # -- full synopsis (so the story is understandable without the cards) --
    synopsis: str = ""            # 完整故事梗概
    opening_state: str = ""       # 故事开始时的主要局面
    inciting_incident: str = ""   # 引发主线的事件
    central_turn: str = ""        # 改变主角理解或目标的关键节点
    climax: str = ""              # 全书高潮
    resolution: str = ""          # 主要冲突的最终处理
    main_conflict: str = ""
    cast: List[str] = Field(default_factory=list)          # display names
    cast_ids: List[str] = Field(default_factory=list)      # stable character ids
    primary_character_id: str = ""                          # protagonist / convergence POV
    key_turns: List[str] = Field(default_factory=list)
    ending: str = ""
    structure_template: str = "linear_causality"
    volumes: List[VolumePlan] = Field(default_factory=list)
    chosen_idea: Optional[StoryIdea] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    constraints: List[str] = Field(default_factory=list)  # 应用的硬约束（可追溯）
    generated_by: str = ""        # llm | offline_template
    expected_chapters: int = 0    # 用户要求的章数（校验用）
    status: str = "candidate"
    created_at: str = ""

    # -- navigation ---------------------------------------------------------
    def chapters(self) -> List[ChapterPlan]:
        out: List[ChapterPlan] = []
        for vol in self.volumes:
            out.extend(vol.chapters)
        return sorted(out, key=lambda c: c.number)

    def chapter(self, number: int) -> Optional[ChapterPlan]:
        for c in self.chapters():
            if c.number == number:
                return c
        return None

    def chapter_numbers(self) -> List[int]:
        return [c.number for c in self.chapters()]

    def all_threads(self) -> List[str]:
        seen: List[str] = []
        for c in self.chapters():
            for t in c.threads:
                if t not in seen:
                    seen.append(t)
        return seen

    # -- lock & impact ------------------------------------------------------
    def lock(self, number: int) -> None:
        c = self.chapter(number)
        if c:
            c.status = "locked"

    def unlock(self, number: int) -> None:
        c = self.chapter(number)
        if c and c.status == "locked":
            c.status = "accepted"

    def locked_numbers(self) -> List[int]:
        return [c.number for c in self.chapters() if c.locked]

    def lock_field(self, number: int, field_name: str) -> None:
        c = self.chapter(number)
        if c and field_name and field_name not in c.locked_fields:
            c.locked_fields.append(field_name)

    def unlock_field(self, number: int, field_name: str) -> None:
        c = self.chapter(number)
        if c and field_name in c.locked_fields:
            c.locked_fields.remove(field_name)

    def affected_downstream(self, number: int) -> List[int]:
        """Chapters after ``number`` whose plans may depend on it."""
        return [n for n in self.chapter_numbers() if n > number]

    # -- serialization ------------------------------------------------------
    def stamp(self) -> "BookPlan":
        if not self.created_at:
            self.created_at = _dt.datetime.now().isoformat(timespec="seconds")
        return self
