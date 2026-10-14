"""Character — a soloist.

Each character carries their own "improvisation rules": given the same event,
different characters produce different stories. This is the engine that makes
the prose character-driven instead of plot-driven.
"""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import Field

from core.base import Model


class Character(Model):
    name: str
    role: str = ""
    desire: str = ""
    fear: str = ""
    memory: str = ""
    worldview: str = ""
    contradiction: str = ""
    voice: str = ""
    # "when X -> do Y" heuristics that drive the solo
    rules: List[str] = Field(default_factory=list)
    # arc: from -> to (e.g. 相信技术 -> 怀疑技术)
    arc_from: str = ""
    arc_to: str = ""
    aliases: List[str] = Field(default_factory=list)

    def react(self, event: str) -> str:
        """Return the character's improvisation brief for a given event."""
        rules = "\n".join(f"- {r}" for r in self.rules) or "- (按性格自然行动)"
        return (
            f"人物 {self.name} 面对事件「{event}」时应如何即兴:\n"
            f"欲望: {self.desire}\n"
            f"恐惧: {self.fear}\n"
            f"记忆: {self.memory}\n"
            f"世界观: {self.worldview}\n"
            f"内在矛盾: {self.contradiction}\n"
            f"即兴规则:\n{rules}"
        )

    def as_prompt(self) -> str:
        parts = [f"视角人物: {self.name}" + (f"（{self.role}）" if self.role else "")]
        for label, value in (
            ("欲望", self.desire),
            ("恐惧", self.fear),
            ("记忆", self.memory),
            ("世界观", self.worldview),
            ("内在矛盾", self.contradiction),
            ("声音/语感", self.voice),
        ):
            if value:
                parts.append(f"  {label}: {value}")
        if self.arc_from or self.arc_to:
            parts.append(f"  人物弧: {self.arc_from} → {self.arc_to}")
        for rule in self.rules:
            parts.append(f"  即兴规则: {rule}")
        return "\n".join(parts)

    @property
    def anchors(self) -> List[str]:
        """Identity anchors that should remain stable across the novel."""
        out = [self.name, *self.aliases]
        for value in (self.desire, self.worldview, self.voice):
            if value:
                out.append(value)
        return [a for a in out if a]

    def to_state(self) -> Dict[str, Any]:
        return self.to_dict()
