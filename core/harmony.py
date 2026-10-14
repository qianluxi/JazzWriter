"""Harmony — the constraints that make improvisation musical.

Chords are not restrictions on freedom, they are what lets the solo *mean*
something. Here: world rules (hard constraints), forbidden moves, and the
emotional chord progression the story should move through.
"""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import Field

from core.base import Model


class Harmony(Model):
    world: str = ""
    rules: List[str] = Field(default_factory=list)       # hard constraints
    forbidden: List[str] = Field(default_factory=list)   # must never appear
    soft_constraints: List[str] = Field(default_factory=list)
    emotion_curve: List[str] = Field(default_factory=list)  # 平静→不安→…

    def violations(self, text: str) -> List[str]:
        """Return forbidden tokens found in the text (hard-constraint check)."""
        return [item for item in self.forbidden if item and item in text]

    def check(self, text: str) -> bool:
        """Compatibility shim matching the spec's boolean check()."""
        return not self.violations(text)

    def as_prompt(self) -> str:
        lines: List[str] = []
        if self.world:
            lines.append(f"世界设定: {self.world}")
        if self.rules:
            lines.append("硬约束(不可违反):")
            lines.extend(f"  - {r}" for r in self.rules)
        if self.forbidden:
            lines.append("禁忌(禁止出现):")
            lines.extend(f"  - {f}" for f in self.forbidden)
        if self.soft_constraints:
            lines.append("软约束(可突破):")
            lines.extend(f"  - {s}" for s in self.soft_constraints)
        if self.emotion_curve:
            lines.append("情绪和声进行: " + " → ".join(self.emotion_curve))
        return "\n".join(lines) if lines else "(无额外和声约束)"

    def curve_hint(self, position: float) -> str:
        """Where on the emotional progression a given chapter should sit."""
        if not self.emotion_curve:
            return ""
        if position <= 0.0:
            return self.emotion_curve[0]
        if position >= 1.0:
            return self.emotion_curve[-1]
        idx = int(round(position * (len(self.emotion_curve) - 1)))
        return self.emotion_curve[idx]
