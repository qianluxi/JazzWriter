"""Conductor — reads the review and retunes the next improvisation.

The adaptive rule the expert described: if novelty is too low, open up the
randomness; if the take drifts off-theme or off-character, pull the freedom
back. It returns a *suggested* JazzParams for the next round.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.character import Character
from core.theme import Theme
from improvisation.improvisation_score import JazzParams
from feedback import character_check, novelty_check, theme_check


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass
class Advice:
    metrics: Dict[str, float]
    deltas: Dict[str, float]
    suggested: JazzParams
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "metrics": {k: round(v, 3) for k, v in self.metrics.items()},
            "deltas": {k: round(v, 3) for k, v in self.deltas.items()},
            "notes": self.notes,
            "suggested": self.suggested.to_dict(),
        }


class Conductor:
    def advise(
        self,
        text: str,
        theme: Theme,
        character: Character,
        params: JazzParams,
        *,
        previous_texts: Optional[List[str]] = None,
        evaluation=None,
    ) -> Advice:
        if evaluation is not None:
            m = dict(evaluation.metrics)
        else:
            m = {
                "theme": theme_check.check(text, theme),
                "character": character_check.check(text, character),
                "novelty": novelty_check.check(text, previous_texts),
            }

        deltas: Dict[str, float] = {}
        notes: List[str] = []

        if m.get("novelty", 1.0) < 0.55:
            deltas["randomness"] = deltas.get("randomness", 0.0) + 0.15
            deltas["creativity"] = deltas.get("creativity", 0.0) + 0.10
            notes.append("创新偏低 → 提高 randomness / creativity。")

        if m.get("theme", 1.0) < 0.6:
            deltas["creativity"] = deltas.get("creativity", 0.0) - 0.15
            deltas["character_freedom"] = deltas.get("character_freedom", 0.0) - 0.10
            deltas["style_distance"] = deltas.get("style_distance", 0.0) - 0.10
            notes.append("主题被稀释 → 降低自由度，让动机回归。")

        if m.get("character", 1.0) < 0.6:
            deltas["character_freedom"] = deltas.get("character_freedom", 0.0) - 0.15
            notes.append("人物一致性不足 → 收紧 character_freedom。")

        if "emotion" in m and m.get("emotion", 1.0) < 0.5:
            deltas["style_distance"] = deltas.get("style_distance", 0.0) + 0.05
            notes.append("情绪和声偏淡 → 略增 style_distance，允许更鲜明的色彩。")

        if not notes:
            notes.append("状态良好：可维持当前乐谱，或小幅提高自由度。")

        suggested = dataclasses.replace(
            params,
            creativity=_clamp01(params.creativity + deltas.get("creativity", 0.0)),
            randomness=_clamp01(params.randomness + deltas.get("randomness", 0.0)),
            motif_reuse=_clamp01(params.motif_reuse + deltas.get("motif_reuse", 0.0)),
            character_freedom=_clamp01(params.character_freedom + deltas.get("character_freedom", 0.0)),
            surprise_level=_clamp01(params.surprise_level + deltas.get("surprise_level", 0.0)),
            style_distance=_clamp01(params.style_distance + deltas.get("style_distance", 0.0)),
        )
        return Advice(metrics=m, deltas=deltas, suggested=suggested, notes=notes)
