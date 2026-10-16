"""Narrative reviewer — the second evaluation layer.

Layer 1 (`plot_validator`) does hard, deterministic checks. This layer judges
whether events are *reasonable*, character choices *hold*, conflict *escalates*,
and the ending *answers* the opening — and it must give **evidence + chapters**,
not just a score.

With a model it reasons over the synopsis and chapter cards; offline it offers a
few heuristic findings and says so explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.book_plan import BookPlan
from engine.planning_llm import generate_json

RESPOND_WORDS = ("回应", "回答", "理解", "问题", "命题", "代价", "代价")


@dataclass
class Finding:
    issue: str
    chapter: Optional[int] = None
    evidence: str = ""

    def to_dict(self) -> Dict:
        return {"issue": self.issue, "chapter": self.chapter, "evidence": self.evidence}


class NarrativeReviewer:
    def __init__(self, llm=None) -> None:
        self.llm = llm

    def review(self, book: BookPlan) -> List[Finding]:
        via_llm = self._from_llm(book)
        if via_llm is not None:
            return via_llm
        return self._offline(book)

    # -- offline heuristics -------------------------------------------------
    def _offline(self, book: BookPlan) -> List[Finding]:
        findings: List[Finding] = []
        chapters = book.chapters()

        if not book.synopsis:
            findings.append(Finding("缺少完整故事梗概（synopsis），无法在不看卡片的情况下判断全书走向。"))

        if book.question and chapters:
            last = chapters[-1]
            blob = f"{book.resolution}{book.ending}{last.outcome}{last.hook_to}"
            if not any(w in blob for w in RESPOND_WORDS):
                findings.append(Finding(
                    "结尾可能没有回应开篇提出的核心问题。",
                    chapter=last.number, evidence=(book.ending or last.summary)[:60]))

        # conflict escalation: outcomes that never grow in stakes is a smell
        if len(chapters) >= 4:
            short_turns = sum(1 for c in chapters if len(c.outcome or "") < 8)
            if short_turns >= len(chapters) // 2:
                findings.append(Finding(
                    "过半章节的“结果”过于简略，冲突可能没有真正升级。",
                    evidence=f"{short_turns}/{len(chapters)} 章 outcome 过短"))

        # character choice support
        weak = [c.number for c in chapters if not c.key_action]
        if weak:
            findings.append(Finding("部分章节缺少关键行动，人物选择难以成立。",
                                    chapter=weak[0], evidence=f"涉及章：{weak[:8]}"))

        findings.append(Finding(
            "（离线审阅）接入模型后可进一步判断事件是否合理、人物选择是否成立。",
            evidence="NarrativeReviewer offline"))
        return findings

    # -- LLM reasoning ------------------------------------------------------
    def _from_llm(self, book: BookPlan) -> Optional[List[Finding]]:
        if self.llm is None or getattr(self.llm, "name", "") in ("mock", ""):
            return None
        cards = "\n".join(
            f"第{c.number}章[{c.function}] {c.pov}：冲突={c.conflict}；结果={c.outcome}；变化={c.character_change}"
            for c in book.chapters())
        prompt = (
            "你是严谨的小说叙事审阅者。基于全书梗概与章节卡片，判断：事件是否合理、人物选择是否成立、"
            "冲突是否真正升级、结局是否回应开篇问题。每条问题必须给出**依据与章号**，不要只给分数。\n"
            f"命题：{book.question}\n梗概：{book.synopsis}\n结局：{book.ending}\n"
            f"章节卡片：\n{cards}\n"
            '输出 JSON：{"findings":[{"chapter":1,"issue":"","evidence":""}]}'
        )
        data = generate_json(self.llm, prompt, max_tokens=3000)
        if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
            return None
        out: List[Finding] = []
        for item in data["findings"]:
            if not isinstance(item, dict):
                continue
            ch = item.get("chapter")
            out.append(Finding(str(item.get("issue", "")),
                               chapter=int(ch) if isinstance(ch, (int, float)) else None,
                               evidence=str(item.get("evidence", ""))))
        return out
