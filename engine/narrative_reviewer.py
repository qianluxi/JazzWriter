"""Narrative reviewer — the second evaluation layer.

Layer 1 (`plot_validator`) does hard, deterministic checks. This layer judges
whether events are *reasonable*, character choices *hold*, conflict *escalates*,
and the ending *answers* the opening — and it must give **evidence + chapters**.

It also performs an explicit **semantic fact-conflict review**: does any chapter
contradict an *established fact* in the story state? That judgement needs a
model (rule/lexical checks cannot decide "the device was never repaired" vs "the
device was repaired"); offline it is reported as **"requires a model"**, never
silently passed.

With a model it reasons over the synopsis and chapter cards; offline it offers a
few heuristic findings and says so explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from core.book_plan import BookPlan
from engine.planning_llm import generate_json

RESPOND_WORDS = ("回应", "回答", "理解", "问题", "命题", "代价")


@dataclass
class Finding:
    issue: str
    chapter: Optional[int] = None
    evidence: str = ""
    kind: str = "narrative"   # narrative | fact_conflict | fact_check

    def to_dict(self) -> Dict:
        return {"issue": self.issue, "chapter": self.chapter,
                "evidence": self.evidence, "kind": self.kind}


def _facts(story_state) -> List[str]:
    if story_state is None:
        return []
    try:
        return story_state.protected_statements()
    except Exception:  # noqa: BLE001
        return []


class NarrativeReviewer:
    def __init__(self, llm=None, story_state=None) -> None:
        self.llm = llm
        self.story_state = story_state

    def review(self, book: BookPlan) -> List[Finding]:
        facts = _facts(self.story_state)
        via_llm = self._from_llm(book, facts)
        if via_llm is not None:
            return via_llm
        return self._offline(book, facts)

    # -- offline heuristics -------------------------------------------------
    def _offline(self, book: BookPlan, facts: List[str]) -> List[Finding]:
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

        if len(chapters) >= 4:
            short_turns = sum(1 for c in chapters if len(c.outcome or "") < 8)
            if short_turns >= len(chapters) // 2:
                findings.append(Finding(
                    "过半章节的“结果”过于简略，冲突可能没有真正升级。",
                    evidence=f"{short_turns}/{len(chapters)} 章 outcome 过短"))

        weak = [c.number for c in chapters if not c.key_action]
        if weak:
            findings.append(Finding("部分章节缺少关键行动，人物选择难以成立。",
                                    chapter=weak[0], evidence=f"涉及章：{weak[:8]}"))

        # explicit fact-conflict review (offline cannot judge -> say so)
        if facts:
            findings.append(Finding(
                f"已确定事实的语义冲突检查：需接入模型（离线不判定）。待核对事实 {len(facts)} 条。",
                kind="fact_check",
                evidence="；".join(facts[:5])))
        else:
            findings.append(Finding(
                "已确定事实的语义冲突检查：无已登记事实可核对（未判定）。",
                kind="fact_check"))

        findings.append(Finding(
            "（离线审阅）接入模型后可进一步判断事件是否合理、人物选择是否成立。",
            evidence="NarrativeReviewer offline"))
        return findings

    # -- LLM reasoning ------------------------------------------------------
    def _from_llm(self, book: BookPlan, facts: List[str]) -> Optional[List[Finding]]:
        if self.llm is None or getattr(self.llm, "name", "") in ("mock", ""):
            return None
        cards = "\n".join(
            f"第{c.number}章[{c.function}] {c.pov}：冲突={c.conflict}；结果={c.outcome}；"
            f"信息变化={c.info_change}；关键行动={c.key_action}"
            for c in book.chapters())
        facts_text = "\n".join(f"- {f}" for f in facts) or "（无已登记事实）"
        prompt = (
            "你是严谨的小说叙事审阅者。完成两项审阅，每条结论必须给出**依据与章号**，不要只给分数：\n"
            "A. 叙事合理性：事件是否合理、人物选择是否成立、冲突是否真正升级、结局是否回应开篇问题。\n"
            "B. 事实冲突：判断各章内容是否**与下面“已确定事实”语义矛盾**（例如事实说某物从未被修复，"
            "章节却写它已修复成功）。只有确实与某条事实矛盾时才报，并引用该事实。\n\n"
            f"命题：{book.question}\n梗概：{book.synopsis}\n结局：{book.ending}\n"
            f"已确定事实：\n{facts_text}\n"
            f"章节卡片：\n{cards}\n"
            '输出 JSON：{"findings":[{"chapter":1,"issue":"","evidence":"","type":"narrative"}]}'
            '（type 取 "fact_conflict" 或 "narrative"；fact_conflict 的 evidence 必须引用相关事实）'
        )
        data = generate_json(self.llm, prompt, max_tokens=3000)
        if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
            return None
        out: List[Finding] = []
        for item in data["findings"]:
            if not isinstance(item, dict):
                continue
            ch = item.get("chapter")
            kind = str(item.get("type", "narrative"))
            if kind not in ("narrative", "fact_conflict"):
                kind = "narrative"
            out.append(Finding(str(item.get("issue", "")),
                               chapter=int(ch) if isinstance(ch, (int, float)) else None,
                               evidence=str(item.get("evidence", "")),
                               kind=kind))
        # always surface the fact-check status explicitly
        conflicts = [f for f in out if f.kind == "fact_conflict"]
        if not conflicts:
            out.append(Finding("事实冲突检查：未发现与已确定事实的语义矛盾（模型判断）。",
                               kind="fact_check", evidence=f"核对 {len(facts)} 条事实"))
        return out
