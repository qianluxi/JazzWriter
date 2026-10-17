"""Consistency checker: flag tension, never auto-correct it.

Conflicts are surfaced as *hints*. Some contradictions are deliberate (mystery,
religion, unreliable narration), so the checker only points at them and leaves
the decision to the author. Entities marked ``contradiction`` are reported as
intentional, not as errors.
"""

from __future__ import annotations

from typing import Dict, List

from engine.textutil import tokens
from world.models import WorldDoc

_NEGATIONS = ("不", "无", "非", "禁", "永", "拒绝", "否认", "否定", "推翻", "反对",
              "不得", "丧失", "无法", "没有")


class WorldChecker:
    def check(self, doc: WorldDoc) -> List[Dict[str, object]]:
        issues: List[Dict[str, object]] = []
        issues.extend(self._duplicates(doc))
        issues.extend(self._conflicting_pairs(doc))
        for entity in doc.entities:
            if entity.state == "contradiction":
                issues.append({
                    "level": "note",
                    "ids": [entity.id],
                    "message": f"有意保留的矛盾：{entity.statement}",
                })
        return issues

    @staticmethod
    def _duplicates(doc: WorldDoc) -> List[Dict[str, object]]:
        seen: Dict[str, bool] = {}
        out: List[Dict[str, object]] = []
        for entity in doc.entities:
            key = f"{entity.kind}:{entity.name}"
            if key in seen:
                out.append({
                    "level": "warn",
                    "ids": [entity.id],
                    "message": f"同类同名条目重复：{entity.name}",
                })
            seen[key] = True
        return out

    @staticmethod
    def _conflicting_pairs(doc: WorldDoc) -> List[Dict[str, object]]:
        out: List[Dict[str, object]] = []
        for kind in {e.kind for e in doc.entities}:
            group = [e for e in doc.entities if e.kind == kind]
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    shared = set(tokens(a.statement)) & set(tokens(b.statement))
                    if len(shared) < 2:
                        continue
                    neg_a = any(m in a.statement for m in _NEGATIONS)
                    neg_b = any(m in b.statement for m in _NEGATIONS)
                    if neg_a != neg_b:
                        term = sorted(shared, key=len, reverse=True)[0]
                        out.append({
                            "level": "warn",
                            "ids": [a.id, b.id],
                            "message": f"可能冲突（围绕「{term}」)：{a.name} 与 {b.name} 表述相反。",
                        })
        return out
