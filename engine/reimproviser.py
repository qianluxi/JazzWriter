"""Chapter re-improvisation — propose *candidates*, don't overwrite.

Re-improvising a chapter must offer a genuinely different but equally concrete
plan — not silently replace a rich card with template filler. So this produces
**candidates** the author inspects and adopts. With a real model the candidates
are model-written; offline it produces clearly-marked *template* candidates.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.book_plan import BookPlan
from core.chapter_plan import (FIELD_NAMES, ChapterPlan, CharacterDecision,
                               KnowledgeChange, RelationshipChange)
from core.character import Character
from core.harmony import Harmony
from core.relationship import RelationshipMap
from core.story_state import StoryState
from core.theme import Theme
from engine.outline_expander import REL_CHANGE_FUNCS
from engine.planning_llm import generate_json

STRUCT_FIELDS = ["pov_character_id", "characters_involved", "character_decisions",
                 "knowledge_changes", "relationship_changes"]

OPERATOR_VARIANTS: List[tuple] = [
    ("information_displacement", "改变信息揭示顺序：先给现象，把原因后置。"),
    ("cognitive_bias", "让人物因误判做出不同选择，后续冲突随之改变。"),
    ("action_drift", "让人物短暂偏离原计划，做出计划外但符合欲望的选择。"),
    ("emotional_contrast", "让表面行为与潜在情绪相反，以克制承载焦虑。"),
]
_VARIANT_DESC = dict(OPERATOR_VARIANTS)
OFFLINE_NOTE = "离线模板候选：仅用于演示/离线跑通，不代表模型创作质量。"


@dataclass
class ChapterCandidate:
    number: int
    label: str
    chapter: ChapterPlan
    changed_fields: List[str] = field(default_factory=list)
    source: str = "offline_template"  # llm | offline_template
    note: str = ""

    def to_dict(self) -> Dict:
        return {"number": self.number, "label": self.label, "source": self.source,
                "note": self.note, "changed_fields": self.changed_fields,
                "chapter": self.chapter.to_dict()}


class ChapterReimproviser:
    def __init__(self, theme: Theme, characters: List[Character], *,
                 harmony: Optional[Harmony] = None,
                 story_state: Optional[StoryState] = None,
                 motifs=None, llm=None, relationships=None) -> None:
        self.theme = theme
        self.character_list = list(characters)
        self.characters = {c.effective_id: c for c in characters}  # id-keyed (no name overwrite)
        self.harmony = harmony
        self.story_state = story_state
        self.motifs = motifs
        self.llm = llm
        self.relationships = relationships or RelationshipMap()

    def _resolve(self, name_or_id: Optional[str]):
        if not name_or_id:
            return None
        if name_or_id in self.characters:
            return self.characters[name_or_id]
        return next((c for c in self.character_list
                     if c.name == name_or_id or c.effective_id == name_or_id), None)

    def _refresh_metadata(self, ch: ChapterPlan, base: ChapterPlan) -> None:
        """Rebuild structured character metadata so it matches the new content
        (a re-improvised chapter must not keep the old decisions/knowledge)."""
        pov = self._resolve(ch.pov) or self._resolve(base.pov)
        pov_id = pov.effective_id if pov else (
            ch.pov_character_id or base.pov_character_id or ch.pov)
        ch.pov_character_id = pov_id
        # participation follows the new POV: keep others, but never the old POV alone
        involved = [pov_id] + [x for x in base.characters_involved
                               if x and x != base.pov_character_id]
        ch.characters_involved = list(dict.fromkeys(involved))
        ch.character_decisions = [CharacterDecision(
            character_id=pov_id, decision=ch.key_action or ch.summary,
            motivation=(pov.current_goal or pov.desire or "") if pov else "")]
        if ch.info_change:
            anchor = base.threads[0] if base.threads else (ch.key_action or ch.summary)[:20]
            ch.knowledge_changes = [KnowledgeChange(
                character_id=pov_id, change=ch.info_change,
                source=f"第 {ch.number} 章 · 与〈{anchor}〉相关")]
        else:
            ch.knowledge_changes = []
        ch.relationship_changes = self._recompute_relationship(ch, base)

    def _recompute_relationship(self, ch: ChapterPlan, base: ChapterPlan):
        if base.function not in REL_CHANGE_FUNCS or not self.relationships.relationships:
            return []
        inv = set(ch.characters_involved)
        for r in self.relationships.relationships:
            if r.source_id in inv and r.target_id in inv:
                return [RelationshipChange(
                    pair=[r.source_id, r.target_id],
                    change=r.possible_transition or "关系发生变化",
                    cause=r.pressure_point or "")]
        return []

    def propose(self, book: BookPlan, number: int, *, count: int = 2,
                seed=None, operators: Optional[List[str]] = None) -> List[ChapterCandidate]:
        base = book.chapter(number)
        if base is None:
            raise ValueError(f"第 {number} 章不存在")
        prev, nxt = book.chapter(number - 1), book.chapter(number + 1)

        via_llm = self._from_llm(book, base, prev, nxt, count, operators)
        if via_llm:
            return via_llm

        rng = random.Random(seed if seed is not None else number * 7)
        keys = operators or [k for k, _ in OPERATOR_VARIANTS]
        candidates: List[ChapterCandidate] = []
        for i in range(max(1, count)):
            key = keys[i % len(keys)]
            candidates.append(self._variant(base, prev, nxt, key))
        return candidates

    # -- offline variants ---------------------------------------------------
    def _variant(self, base: ChapterPlan, prev, nxt, key: str) -> ChapterCandidate:
        ch = ChapterPlan.from_dict(base.to_dict())  # deep copy
        ch.status = "candidate"
        ch.locked_fields = []
        ch.source = "offline_template"
        pov = base.pov or "主角"

        if key == "information_displacement":
            ch.info_change = "先给现象、后置原因：" + (base.outcome or "读者得知结果，但原因被延迟")
            ch.hook_to = "原因留到后续章节；读者对前文的理解将被改写。"
        elif key == "cognitive_bias":
            ch.key_action = f"{pov}基于一个误判采取行动：" + (base.key_action or "他用自己的世界观解读了眼前的事")
            ch.conflict = "误判使冲突方向改变：" + (base.conflict or "")
        elif key == "action_drift":
            ch.key_action = f"{pov}偏离原计划：" + (base.key_action or "他做出一个计划外的选择")
            ch.outcome = "偏离带来后果：" + (base.outcome or "局面朝未预料的方向改变")
        elif key == "emotional_contrast":
            ch.character_change = "表面平静、内在相反：" + (base.character_change or "以克制的动作承载焦虑")
        else:
            ch.conflict = base.conflict
        ch.summary = f"{pov}（{key}）：{ch.key_action or base.summary}"
        ch.notes = ((base.notes + " ") if base.notes else "") + OFFLINE_NOTE
        self._refresh_metadata(ch, base)

        changed = [f for f in FIELD_NAMES + STRUCT_FIELDS if getattr(ch, f) != getattr(base, f)]
        return ChapterCandidate(number=base.number,
                                label=f"候选[{key}]：{_VARIANT_DESC.get(key, key)}",
                                chapter=ch, changed_fields=changed,
                                source="offline_template", note=OFFLINE_NOTE)

    # -- LLM path -----------------------------------------------------------
    def _constraints(self, pov: str) -> List[str]:
        out: List[str] = []
        if self.harmony:
            out += list(self.harmony.rules) + ["禁止：" + f for f in self.harmony.forbidden]
        if self.story_state:
            out += self.story_state.as_constraints()
            out += ["不可提前揭露：" + f for f in self.story_state.forbidden_reveals(pov)]
        return out

    def _from_llm(self, book, base, prev, nxt, count, operators):
        if self.llm is None or getattr(self.llm, "name", "") in ("mock", ""):
            return None
        ops = operators or [k for k, _ in OPERATOR_VARIANTS]
        pov_char = next((c for c in self.characters.values()
                         if c.name == base.pov or c.effective_id == base.pov), None)
        pov_brief = f"视角人物章节动机（当前目标/秘密/行为倾向）：{pov_char.brief('chapter')}\n" if pov_char else ""
        prompt = (
            f"为长篇小说重新即兴【第 {base.number} 章】，给出 {count} 个**实质不同**的候选方案。\n"
            f"{pov_brief}"
            f"原章节卡片：功能={base.function}；POV={base.pov}；冲突={base.conflict}；"
            f"结果={base.outcome}；信息变化={base.info_change}；人物变化={base.character_change}；"
            f"线索={base.threads}；意象={base.motifs}\n"
            f"上一章摘要：{prev.summary if prev else '（无）'}\n"
            f"下一章摘要：{nxt.summary if nxt else '（无）'}\n"
            f"可尝试的即兴操作：{ops}\n"
            f"硬约束：{'；'.join(self._constraints(base.pov)) or '（无）'}\n"
            "每个候选必须改变关键行动/冲突/信息结构/结局中的至少一项，且不得与硬约束冲突。"
            '输出 JSON：{"candidates":[{"label":"","chapter":{"title":"","function":"","pov":"",'
            '"premise":"","key_action":"","conflict":"","outcome":"","stakes":"","info_change":"",'
            '"character_change":"","threads":[],"motifs":[],"hook_from":"","hook_to":"","summary":""}}]}'
        )
        data = generate_json(self.llm, prompt, max_tokens=4000)
        if not data or not isinstance(data.get("candidates"), list):
            return None
        out: List[ChapterCandidate] = []
        for item in data["candidates"][:count]:
            if not isinstance(item, dict) or not isinstance(item.get("chapter"), dict):
                continue
            cdict = dict(item["chapter"])
            cdict["number"] = base.number
            cdict["status"] = "candidate"
            cdict["source"] = "llm"
            ch = ChapterPlan.from_dict({**base.to_dict(), **cdict})
            self._refresh_metadata(ch, base)
            changed = [f for f in FIELD_NAMES + STRUCT_FIELDS if getattr(ch, f) != getattr(base, f)]
            out.append(ChapterCandidate(number=base.number,
                                        label=str(item.get("label", "LLM 候选")),
                                        chapter=ch, changed_fields=changed, source="llm"))
        return out or None

    # -- adoption -----------------------------------------------------------
    @staticmethod
    def apply(chapter: ChapterPlan, candidate_chapter: ChapterPlan) -> None:
        """Copy a candidate's fields onto the live chapter, preserving locks."""
        locked = {f: getattr(chapter, f) for f in chapter.locked_fields}
        locked_fields = list(chapter.locked_fields)
        for f in FIELD_NAMES + STRUCT_FIELDS:
            setattr(chapter, f, getattr(candidate_chapter, f))
        chapter.status = "accepted"
        chapter.source = candidate_chapter.source or "edited"
        chapter.locked_fields = locked_fields
        for f, v in locked.items():
            setattr(chapter, f, v)
