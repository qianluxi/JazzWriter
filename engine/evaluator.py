"""Evaluator — "listening back" to a take.

Two kinds of output, deliberately not merged into one number:

* metrics   — the score (theme / character / emotion / motif / novelty / harmony)
* signals   — auto checks (continuity, repetition) and literary listen-back
              (non-obviousness, narrative increment, implicit expression)

A low-plot, low-emotion scene can still be excellent literature; the signals
inform the author, they do not override them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.character import Character
from core.harmony import Harmony
from core.motif import MotifLibrary
from core.story_state import StoryState
from core.theme import Theme
from engine import semantic_similarity as sem
from engine import textutil as tu
from engine.composer import Take

_WEIGHTS = {
    "theme": 0.25,
    "character": 0.20,
    "emotion": 0.15,
    "motif": 0.10,
    "novelty": 0.20,
    "harmony": 0.10,
}

CLICHES = [
    "心潮澎湃", "五味杂陈", "不由自主", "恍然大悟", "百感交集",
    "思绪万千", "如梦初醒", "翻江倒海", "久久不能平静",
]
META_EXPLAIN = ["这意味着", "这说明", "象征着", "代表了", "其实是在说", "寓意着"]


@dataclass
class Evaluation:
    metrics: Dict[str, float]
    overall: float
    grade: str
    notes: List[str] = field(default_factory=list)
    signals: Dict[str, float] = field(default_factory=dict)
    listening: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "metrics": {k: round(v, 3) for k, v in self.metrics.items()},
            "overall": round(self.overall, 3),
            "grade": self.grade,
            "notes": self.notes,
            "signals": {k: round(v, 3) for k, v in self.signals.items()},
            "listening": self.listening,
        }


class Evaluator:
    def __init__(
        self,
        theme: Theme,
        character: Character,
        harmony: Harmony,
        motifs: Optional[MotifLibrary] = None,
        story_state: Optional[StoryState] = None,
        eval_mode: str = "lexical",
    ) -> None:
        self.theme = theme
        self.character = character
        self.harmony = harmony
        self.motifs = motifs or MotifLibrary()
        self.story_state = story_state
        self.eval_mode = eval_mode

    def evaluate(
        self,
        text: str,
        *,
        take: Optional[Take] = None,
        previous_texts: Optional[List[str]] = None,
    ) -> Evaluation:
        notes: List[str] = []
        theme_text = " ".join(self.theme.keywords)
        char_text = " ".join(
            v
            for v in (
                self.character.desire,
                self.character.fear,
                self.character.memory,
                self.character.worldview,
                self.character.voice,
                self.character.contradiction,
            )
            if v
        )
        active_motifs = (
            (take.context.get("active_motifs") if take else None)
            or self.motifs.names()
            or self.theme.motifs
        )
        point = take.context.get("point") if take else ""

        # -- theme ----------------------------------------------------------
        symbol_cov = tu.coverage(text, self.theme.symbols + self.theme.motifs)
        anchor_cov = tu.coverage(text, self.theme.keywords)
        theme_cos = sem.similarity(text, theme_text, self.eval_mode) if theme_text else 0.0
        theme = tu.clamp(0.5 * symbol_cov + 0.3 * anchor_cov + 0.2 * tu.clamp(theme_cos * 6))
        if symbol_cov < 0.3:
            notes.append("核心象征出现偏少，主题可能听不见。")

        # -- character ------------------------------------------------------
        name_hit = 1.0 if (
            self.character.name and self.character.name in text
        ) or any(a and a in text for a in self.character.aliases) else 0.0
        char_cos = sem.similarity(text, char_text, self.eval_mode) if char_text else 0.0
        character = tu.clamp(0.55 * name_hit + 0.45 * tu.clamp(char_cos * 8))
        if name_hit < 1.0:
            notes.append("视角人物在文本中几乎缺席，即兴可能脱离了独奏者。")

        # -- emotion --------------------------------------------------------
        emo_cov = tu.coverage(text, self.theme.emotions)
        point_cov = tu.coverage(text, [point]) if point else 0.0
        emotion = tu.clamp(0.6 * emo_cov + 0.4 * point_cov) if point else tu.clamp(emo_cov)
        if emo_cov < 0.3:
            notes.append("情绪色彩偏淡，和声进行感不明显。")

        # -- motif ----------------------------------------------------------
        motif = tu.coverage(text, active_motifs) if active_motifs else 1.0
        if active_motifs and motif < 0.5:
            notes.append("有动机未在本章复用；爵士的连续性来自动机的变奏。")

        # -- novelty --------------------------------------------------------
        diversity = tu.lexical_diversity(text)
        if previous_texts:
            sim = max((tu.similarity(text, p) for p in previous_texts), default=0.0)
            dissimilarity = tu.clamp(1.0 - sim * 3.0)
        else:
            dissimilarity = 0.7
        novelty = tu.clamp(0.5 * tu.clamp(diversity / 0.85) + 0.5 * dissimilarity)
        if diversity < 0.55:
            notes.append("用词密度偏低，语言可能偏平。")

        # -- harmony --------------------------------------------------------
        violations = self.harmony.violations(text)
        harmony = 0.0 if violations else 1.0
        for v in violations:
            notes.append(f"违反硬约束/禁忌: 「{v}」")

        metrics = {
            "theme": theme,
            "character": character,
            "emotion": emotion,
            "motif": motif,
            "novelty": novelty,
            "harmony": harmony,
        }
        overall = sum(metrics[k] * _WEIGHTS[k] for k in _WEIGHTS)

        signals, listening = self._listen(
            text, take=take, previous_texts=previous_texts, violations=violations
        )
        return Evaluation(
            metrics=metrics, overall=overall, grade=self._grade(overall),
            notes=notes, signals=signals, listening=listening,
        )

    # -- literary listen-back ----------------------------------------------
    def _listen(
        self,
        text: str,
        *,
        take: Optional[Take],
        previous_texts: Optional[List[str]],
        violations: List[str],
    ):
        poz = take.pov if take else None
        prev_blob = "\n".join(previous_texts) if previous_texts else ""

        # 非显然性 non-obviousness: penalize clichés and heavy self-repetition
        cliche = tu.contains_any(text, CLICHES)
        rep = tu.repetition_ratio(text, 4)
        non_obviousness = tu.clamp(1.0 - 0.5 * min(1.0, cliche / 2.0) - rep)

        # 隐含表达 implicit expression: theme must be shown, not stated
        explicit = 0
        for phrase in (self.theme.statement, self.theme.question, self.theme.title):
            if phrase and phrase in text:
                explicit += 1
        meta = tu.contains_any(text, META_EXPLAIN)
        implicit_expression = tu.clamp(1.0 - min(1.0, explicit * 0.5 + meta * 0.3))

        # 叙事增量 narrative increment: new info / new meanings vs. earlier text
        if previous_texts:
            sim = max((tu.similarity(text, p) for p in previous_texts), default=0.0)
            dissimilarity = tu.clamp(1.0 - sim * 3.0)
        else:
            dissimilarity = 0.6
        motif_present = [m for m in self.motifs.names() if m in text]
        fresh_motif = [m for m in motif_present if m and m not in prev_blob]
        fresh_ratio = (len(fresh_motif) / len(motif_present)) if motif_present else 0.5
        narrative_increment = tu.clamp(0.6 * dissimilarity + 0.4 * fresh_ratio)

        # 连续性 continuity: no premature reveal of secrets / due threads
        hits: List[str] = []
        if self.story_state is not None:
            forbidden = self.story_state.forbidden_reveals(poz)
            hits = [f for f in forbidden if f and f in text]
        continuity = tu.clamp(1.0 - len(hits))

        # 重复风险 repetition risk (raw, "lower is better")
        repetition_risk = max((tu.similarity(text, p) for p in previous_texts), default=0.0) if previous_texts else 0.0

        signals = {
            "non_obviousness": non_obviousness,
            "implicit_expression": implicit_expression,
            "narrative_increment": narrative_increment,
            "continuity": continuity,
            "repetition_risk": repetition_risk,
        }

        listening: List[str] = []
        if cliche:
            listening.append("检测到套话/陈词滥调，建议改用具体细节或换一种叙事操作。")
        if rep > 0.25:
            listening.append("文本内部重复偏高，意象或句式可能在自我复读。")
        if implicit_expression < 0.6:
            listening.append("主题被说得过于直白，建议改为暗示，让读者自己拼出命题。")
        if narrative_increment < 0.5:
            listening.append("叙事增量偏低：本章更接近复述，考虑引入新的观察路径。")
        if hits:
            listening.append("疑似提前揭露：" + "；".join(hits[:3]) + "。请核对故事状态。")
        if repetition_risk > 0.35:
            listening.append("与前面章节相似度偏高，注意动机功能与表达的重复。")
        if not listening:
            listening.append("回听良好：表达克制，信息有增量，连续性无冲突。")
        return signals, listening

    @staticmethod
    def _grade(score: float) -> str:
        for threshold, letter in ((0.85, "A"), (0.75, "B"), (0.65, "C"), (0.55, "D")):
            if score >= threshold:
                return letter
        return "E"

    # -- optional LLM judge -------------------------------------------------
    def judge_prompt(self, text: str) -> str:
        return (
            "你是一位苛刻的文学编辑。请以 3 条以内评语评价下面这段文字，"
            "聚焦：主题是否被暗示而非直说、人物是否一致、是否有陈词滥调。"
            "只给评语，不要打分。\n\n原文:\n" + text
        )
