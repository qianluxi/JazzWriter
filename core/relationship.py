"""Relationship network — the engine of story conflict.

Two fleshed-out character files do not by themselves make a story. What matters
is *why they must cooperate, why they may obstruct each other, and what one
one's choice costs the other*. Relationships are first-class data.
"""

from __future__ import annotations

from typing import Dict, List

from pydantic import Field

from core.base import Model


class Relationship(Model):
    source_id: str
    target_id: str
    type: str = ""                 # 亲属/盟友/对手/上下级/证人与调查者…
    mutual_interest: str = ""      # 双方为什么需要彼此
    conflict: str = ""             # 目标在何处冲突
    asymmetry: str = ""            # 权力/信息/资源/责任的不对称
    initial_state: str = ""        # 故事开始时的关系
    pressure_point: str = ""       # 什么事件最可能改变这段关系
    possible_transition: str = ""  # 关系可能走向何方

    def to_dict(self) -> Dict:
        return super().to_dict()

    def involves(self, character_id: str) -> bool:
        return character_id in (self.source_id, self.target_id)


class RelationshipMap(Model):
    relationships: List[Relationship] = Field(default_factory=list)

    def for_character(self, character_id: str) -> List[Relationship]:
        return [r for r in self.relationships if r.involves(character_id)]

    def brief(self, ids: List[str] | None = None) -> str:
        rels = self.relationships
        if ids:
            rels = [r for r in rels if r.source_id in ids or r.target_id in ids]
        if not rels:
            return ""
        lines = []
        for r in rels:
            lines.append(
                f"{r.source_id}↔{r.target_id}（{r.type}）：需要={r.mutual_interest}；"
                f"冲突={r.conflict}；不对称={r.asymmetry}；压力点={r.pressure_point}")
        return "\n".join(lines)
