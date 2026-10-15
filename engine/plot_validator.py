"""Plot validator — structural problems with concrete pointers.

It reports *specific issues* (which thread, which chapters) rather than a single
score, e.g. "线索『证据体系有缺陷』只在第 2 章出现，缺少推进或回收".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from core.book_plan import BookPlan

OPEN_TEMPLATES = ("nonlinear_puzzle", "ensemble")


@dataclass
class Issue:
    severity: str          # high | medium | low
    kind: str
    message: str
    chapter: Optional[int] = None

    def to_dict(self) -> Dict:
        return {"severity": self.severity, "kind": self.kind,
                "message": self.message, "chapter": self.chapter}


class PlotValidator:
    def validate(self, book: BookPlan) -> List[Issue]:
        issues: List[Issue] = []
        chapters = book.chapters()
        if not chapters:
            return [Issue("high", "empty", "尚未生成任何章节结构。")]

        for ch in chapters:
            missing = [f for f, v in (("起因", ch.premise), ("冲突", ch.conflict),
                                      ("结果", ch.outcome)) if not v]
            if missing:
                issues.append(Issue("medium", "incomplete",
                                    f"第 {ch.number} 章缺少：{'、'.join(missing)}。", ch.number))
            if not ch.hook_to and ch.number != chapters[-1].number:
                issues.append(Issue("low", "hook",
                                    f"第 {ch.number} 章没有抛向下一章的驱动力（hook_to 为空）。", ch.number))

        # causal chaining
        for prev, cur in zip(chapters, chapters[1:]):
            if prev.hook_to and cur.hook_from and prev.hook_to.strip() != cur.hook_from.strip():
                issues.append(Issue("low", "causal",
                                    f"第 {cur.number} 章的入口（hook_from）与第 {prev.number} 章的出口不一致，因果链可能断裂。",
                                    cur.number))

        # consecutive identical function
        for prev, cur in zip(chapters, chapters[1:]):
            if prev.function and cur.function and prev.function == cur.function:
                issues.append(Issue("low", "flat",
                                    f"第 {prev.number}、{cur.number} 章功能相同（{cur.function}），节奏可能偏平。",
                                    cur.number))

        # threads with only one appearance
        appearances: Dict[str, List[int]] = {}
        for ch in chapters:
            for t in ch.threads:
                appearances.setdefault(t, []).append(ch.number)
        for thread, chs in appearances.items():
            if len(chs) == 1 and book.structure_template not in OPEN_TEMPLATES:
                issues.append(Issue("medium", "thread",
                                    f"线索「{thread}」只在第 {chs[0]} 章出现，缺少推进或回收。", chs[0]))

        # key turns present
        if not book.key_turns:
            issues.append(Issue("medium", "turns", "全书缺少关键转折（key_turns）。"))

        # ending responds to the opening question
        if book.question and book.ending:
            last = chapters[-1]
            joined = f"{book.ending}{last.outcome}{last.hook_to}"
            if not any(k in joined for k in ("回应", "回答", "理解", "问题", "命题")):
                issues.append(Issue("low", "ending",
                                    "结尾似乎没有回应开篇提出的核心问题（可接受，但要确认是否有意为之）。",
                                    last.number))

        # pov diversity
        povs = {c.pov for c in chapters if c.pov}
        if len(book.cast) > 1 and len(povs) == 1:
            issues.append(Issue("low", "pov", "有多个主要人物，但全书只使用了一个视角。"))

        return issues
