"""Evaluator — "listening back" to a take.

This is the on-stage feedback loop: after a solo we judge whether it stayed in
key (theme/harmony), kept its character, moved the emotional chord, and stayed
fresh. Heuristics first; an LLM judge can be layered on top later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.character import Character
from core.harmony import Harmony
from core.motif import MotifLibrary
from core.theme import Theme
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


@dataclass
class Evaluation:
    metrics: Dict[str, float]
    overall: float
    grade: str
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "metrics": {k: round(v, 3) for k, v in self.metrics.items()},
            "overall": round(self.overall, 3),
            "grade": self.grade,
            "notes": self.notes,
        }


class Evaluator:
    def __init__(
        self,
        theme: Theme,
        character: Character,
        harmony: Harmony,
        motifs: Optional[MotifLibrary] = None,
    ) -> None:
        self.theme = theme
        self.character = character
        self.harmony = harmony
        self.motifs = motifs or MotifLibrary()

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
        theme_cos = tu.similarity(text, theme_text) if theme_text else 0.0
        theme = tu.clamp(0.5 * symbol_cov + 0.3 * anchor_cov + 0.2 * tu.clamp(theme_cos * 6))
        if symbol_cov < 0.3:
            notes.append("核心象征出现偏少，主题可能听不见。")

        # -- character ------------------------------------------------------
        name_hit = 1.0 if (
            self.character.name and self.character.name in text
        ) or any(a and a in text for a in self.character.aliases) else 0.0
        char_cos = tu.similarity(text, char_text) if char_text else 0.0
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
        return Evaluation(metrics=metrics, overall=overall, grade=self._grade(overall), notes=notes)

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
