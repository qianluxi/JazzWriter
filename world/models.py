"""Data model for World Studio.

A world is a set of *entities* (rules, consequences, institutions, history,
geography, conflicts, motifs) plus a record of where each came from. Every
entity carries a *state* so the model never mistakes a guess for a fact:

  confirmed     作者已确认的事实
  candidate     模型提出的候选
  open          尚未决定的问题
  contradiction 有意保留的矛盾（不是错误）
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import Field

from core.base import Model

STATES = ("confirmed", "candidate", "open", "contradiction")

KINDS = (
    "rule", "consequence", "knowledge", "institution",
    "history", "geography", "conflict", "motif",
)

KIND_LABELS: Dict[str, str] = {
    "rule": "核心规则",
    "consequence": "社会后果",
    "knowledge": "知识与认知",
    "institution": "制度与权力",
    "history": "历史动力",
    "geography": "地理与空间",
    "conflict": "冲突与人物",
    "motif": "意象与母题",
}

STATE_MARKS: Dict[str, str] = {
    "confirmed": "",
    "candidate": "〔候选〕",
    "open": "〔未决〕",
    "contradiction": "〔有意保留的矛盾〕",
}


class WorldIdea(Model):
    """One divergent world prototype raised from the same seed.

    ``dimensions`` records how this prototype answers the same structural
    questions (rule mechanism / power / knowledge / dilemma / time) so two ideas
    can be compared by *how the world runs*, not by wording. ``near_duplicate``
    names another idea id when the two are structurally the same despite
    different labels.
    """

    id: str = ""
    label: str = ""
    lens: str = ""
    logline: str = ""
    core_rule: str = ""
    consequence_seed: str = ""
    distinctness: float = 0.0
    differentiators: List[str] = Field(default_factory=list)
    dimensions: Dict[str, str] = Field(default_factory=dict)
    mechanism: str = ""
    near_duplicate: str = ""
    status: str = "candidate"


class WorldEntity(Model):
    id: str = ""
    kind: str = "consequence"
    name: str = ""
    statement: str = ""
    state: str = "candidate"
    source: str = "derived"
    basis: str = ""
    depends_on: List[str] = Field(default_factory=list)
    locked: bool = False

    def label(self) -> str:
        mark = STATE_MARKS.get(self.state, "")
        return f"{self.name}{mark}" if mark else self.name


class WorldDoc(Model):
    title: str = ""
    seed: str = ""
    premise: str = ""
    chosen_idea: Optional[WorldIdea] = None
    ideas: List[WorldIdea] = Field(default_factory=list)
    entities: List[WorldEntity] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)
    provenance: List[str] = Field(default_factory=list)
    rule_properties: Dict[str, str] = Field(default_factory=dict)
    graft_diff: Dict[str, List[str]] = Field(default_factory=dict)
    generation: str = "offline_template"
    created_at: str = ""

    def of_kind(self, kind: str) -> List[WorldEntity]:
        return [e for e in self.entities if e.kind == kind]

    def by_id(self, entity_id: str) -> Optional[WorldEntity]:
        for e in self.entities:
            if e.id == entity_id:
                return e
        return None

    def add(self, entity: WorldEntity) -> WorldEntity:
        if not entity.id:
            entity.id = f"{entity.kind}-{len(self.of_kind(entity.kind)) + 1}"
        self.entities.append(entity)
        return entity

    def lock(self, entity_id: str, locked: bool = True) -> None:
        entity = self.by_id(entity_id)
        if entity is not None:
            entity.locked = locked
            if locked:
                entity.state = "confirmed"
