"""Character — a soloist.

Each character carries their own "improvisation rules": given the same event,
different characters produce different stories. This is the engine that makes
the prose character-driven instead of plot-driven.
"""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import Field

from core.base import Model


TIERS = ("core", "supporting", "functional")


class Character(Model):
    name: str
    id: str = ""                 # stable id (preferred over name; names may change)
    role: str = ""
    tier: str = "core"           # core | supporting | functional
    pov: bool = True             # eligible as a viewpoint character
    desire: str = ""
    fear: str = ""
    memory: str = ""
    worldview: str = ""
    contradiction: str = ""
    voice: str = ""
    # -- narrative-driver attributes (V2.6) --
    blind_spots: List[str] = Field(default_factory=list)   # 认知局限：会在何处误判
    secrets: List[str] = Field(default_factory=list)       # 隐瞒之事
    capabilities: List[str] = Field(default_factory=list)  # 能做什么
    constraints: List[str] = Field(default_factory=list)   # 做不到/受限
    current_goal: str = ""                                 # 当下短期目标
    # "when X -> do Y" heuristics that drive the solo
    rules: List[str] = Field(default_factory=list)
    # arc: from -> to (e.g. 相信技术 -> 怀疑技术)
    arc_from: str = ""
    arc_to: str = ""
    aliases: List[str] = Field(default_factory=list)

    @property
    def effective_id(self) -> str:
        """Stable identifier used across plans (falls back to the name)."""
        return self.id or self.name

    def brief(self, scope: str = "story") -> str:
        """Compact narrative-driver summary, scoped to the planning task.

        - ``story``   : drives for whole-book planning (worldview/arc/relations)
        - ``chapter`` : drives for a single chapter (goal/secrets/rules)
        """
        if scope == "chapter":
            parts = [f"{self.name}({self.effective_id})"]
            for label, value in (("当前目标", self.current_goal), ("欲望", self.desire),
                                 ("恐惧", self.fear)):
                if value:
                    parts.append(f"{label}={value}")
            if self.secrets:
                parts.append("秘密=" + "、".join(self.secrets))
            if self.rules:
                parts.append("行为倾向=" + "、".join(self.rules))
            return "；".join(parts)

        parts = [f"{self.name}({self.effective_id},{self.tier})"]
        if self.role:
            parts.append(f"角色={self.role}")
        if self.desire:
            parts.append(f"欲望={self.desire}")
        if self.fear:
            parts.append(f"恐惧={self.fear}")
        if self.worldview:
            parts.append(f"信念={self.worldview}")
        if self.blind_spots:
            parts.append("盲点=" + "、".join(self.blind_spots))
        if self.contradiction:
            parts.append(f"矛盾={self.contradiction}")
        if self.capabilities:
            parts.append("能力=" + "、".join(self.capabilities))
        if self.constraints:
            parts.append("限制=" + "、".join(self.constraints))
        if self.secrets:
            parts.append("秘密=" + "、".join(self.secrets))
        if self.arc_from or self.arc_to:
            parts.append(f"弧={self.arc_from}→{self.arc_to}")
        return "；".join(parts)

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
            ("当前目标", self.current_goal),
        ):
            if value:
                parts.append(f"  {label}: {value}")
        for label, items in (("认知盲点", self.blind_spots), ("秘密", self.secrets),
                             ("能力", self.capabilities), ("限制", self.constraints)):
            if items:
                parts.append(f"  {label}: " + "、".join(items))
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
