"""ChapterPlan — a structural summary card for one chapter.

This is the primary artifact of JazzWriter: not prose, but a browsable,
editable, lockable description of what a chapter *does* in the story — its
cause, the choice, the conflict, the outcome, what changes, and how it links to
the chapters around it.
"""

from __future__ import annotations

from typing import Dict, List

from pydantic import Field

from core.base import Model

STATUS = ("candidate", "accepted", "locked")


class ChapterPlan(Model):
    number: int
    title: str = ""
    function: str = ""            # 章节功能（建立/升级/转折/低谷/高潮/收束…）
    pov: str = ""
    premise: str = ""             # 起因 / 悬念入口
    key_action: str = ""          # 关键行动
    conflict: str = ""            # 冲突
    outcome: str = ""             # 结果
    stakes: str = ""              # 代价 / 赌注
    info_change: str = ""         # 信息变化（读者或人物知道/误解了什么）
    character_change: str = ""    # 人物状态/认知变化
    threads: List[str] = Field(default_factory=list)   # 涉及的线索 id/名
    motifs: List[str] = Field(default_factory=list)    # 涉及的意象
    hook_from: str = ""           # 与上一章的因果入口
    hook_to: str = ""             # 抛向下一章的驱动力
    summary: str = ""             # 一两句情节摘要
    status: str = "candidate"     # candidate | accepted | locked
    notes: str = ""

    @property
    def id(self) -> str:
        return f"ch{self.number:03d}"

    @property
    def locked(self) -> bool:
        return self.status == "locked"

    def to_dict(self) -> Dict:
        return super().to_dict()
