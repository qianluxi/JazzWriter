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


class CharacterDecision(Model):
    """A character makes a choice in a chapter (traceable to motivation)."""
    character_id: str = ""
    decision: str = ""
    motivation: str = ""


class KnowledgeChange(Model):
    """A character learns something (traceable to a source)."""
    character_id: str = ""
    change: str = ""
    source: str = ""


class RelationshipChange(Model):
    """A relationship shifts between two characters (traceable to a cause)."""
    pair: List[str] = Field(default_factory=list)
    change: str = ""
    cause: str = ""


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
    # -- character participation (V2.6) --
    pov_character_id: str = ""                              # 视角人物的稳定 id
    characters_involved: List[str] = Field(default_factory=list)   # 参与本章的人物 id
    character_decisions: List[CharacterDecision] = Field(default_factory=list)
    knowledge_changes: List[KnowledgeChange] = Field(default_factory=list)
    relationship_changes: List[RelationshipChange] = Field(default_factory=list)
    threads: List[str] = Field(default_factory=list)   # 涉及的线索 id/名
    motifs: List[str] = Field(default_factory=list)    # 涉及的意象
    hook_from: str = ""           # 与上一章的因果入口
    hook_to: str = ""             # 抛向下一章的驱动力
    summary: str = ""             # 一两句情节摘要
    status: str = "candidate"     # candidate | accepted | locked
    locked_fields: List[str] = Field(default_factory=list)  # field-level locks
    source: str = ""              # llm | offline_template | edited
    notes: str = ""

    @property
    def id(self) -> str:
        return f"ch{self.number:03d}"

    @property
    def locked(self) -> bool:
        return self.status == "locked"

    def is_field_locked(self, name: str) -> bool:
        return name in self.locked_fields

    def to_dict(self) -> Dict:
        return super().to_dict()


# field order + Chinese labels for the editable "card" text format ------------
FIELDS = [
    ("title", "标题"),
    ("function", "功能"),
    ("pov", "视角"),
    ("pov_character_id", "视角ID"),
    ("characters_involved", "参与人物"),
    ("premise", "起因"),
    ("key_action", "关键行动"),
    ("conflict", "冲突"),
    ("outcome", "结果"),
    ("stakes", "代价"),
    ("info_change", "信息变化"),
    ("character_change", "人物变化"),
    ("threads", "线索"),
    ("motifs", "意象"),
    ("hook_from", "承接上一章"),
    ("hook_to", "驱向下一章"),
    ("summary", "摘要"),
    ("notes", "备注"),
]
_LABEL_TO_FIELD = {label: field_name for field_name, label in FIELDS}
_LIST_FIELDS = {"threads", "motifs", "characters_involved"}
FIELD_NAMES = [field_name for field_name, _ in FIELDS]


def to_text(ch: ChapterPlan) -> str:
    """Serialize a chapter card to an editable ``字段：值`` text block."""
    head = f"第 {ch.number} 章 · {ch.title}　[{ch.status}]"
    lines = [head]
    if ch.locked_fields:
        lines.append("🔒锁定字段：" + "、".join(ch.locked_fields))
    lines.append("")
    for field_name, label in FIELDS:
        value = getattr(ch, field_name)
        if isinstance(value, list):
            value = "、".join(value)
        if value:
            lines.append(f"{label}：{value}")
    return "\n".join(lines)


def apply_text(ch: ChapterPlan, text: str) -> ChapterPlan:
    """Update a chapter card from edited ``字段：值`` text (partial edits OK)."""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or "：" not in line and ":" not in line:
            continue
        sep = "：" if "：" in line else ":"
        label, _, value = line.partition(sep)
        field_name = _LABEL_TO_FIELD.get(label.strip())
        if not field_name:
            continue
        value = value.strip()
        if field_name in _LIST_FIELDS:
            parts = [p.strip() for p in value.replace("、", ",").replace("，", ",").split(",") if p.strip()]
            setattr(ch, field_name, parts)
        else:
            setattr(ch, field_name, value)
    return ch
