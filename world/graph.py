"""Traceable dependency graph over world entities.

Entities point at what they were derived from (``depends_on``). The graph lets
the author ask the reverse question: *if I change this rule, which candidate
settings are affected?* That is what makes "derive from the rule" checkable
rather than a slogan.
"""

from __future__ import annotations

from typing import Dict, List

from world.models import WorldDoc


class DependencyGraph:
    def __init__(self, doc: WorldDoc) -> None:
        self.doc = doc
        self._children: Dict[str, List[str]] = {}
        for entity in doc.entities:
            for parent in entity.depends_on:
                self._children.setdefault(parent, []).append(entity.id)

    def children(self, entity_id: str) -> List[str]:
        return list(self._children.get(entity_id, []))

    def roots(self) -> List[str]:
        return [e.id for e in self.doc.entities if not e.depends_on]

    def impacted_by(self, entity_id: str) -> List[str]:
        seen: List[str] = []
        stack = list(self._children.get(entity_id, []))
        while stack:
            node = stack.pop(0)
            if node in seen:
                continue
            seen.append(node)
            stack.extend(self._children.get(node, []))
        return seen

    def names(self, ids: List[str]) -> List[str]:
        out: List[str] = []
        for entity_id in ids:
            entity = self.doc.by_id(entity_id)
            if entity is not None:
                out.append(entity.label())
        return out

    def impact_report(self, entity_id: str) -> Dict[str, List[str]]:
        impacted = self.impacted_by(entity_id)
        entity = self.doc.by_id(entity_id)
        return {
            "id": entity_id,
            "name": entity.label() if entity else entity_id,
            "direct": self.names(self.children(entity_id)),
            "transitive": self.names(impacted),
            "candidates": self.names([i for i in impacted
                                      if (self.doc.by_id(i) or None) and
                                      self.doc.by_id(i).state == "candidate"]),
        }
