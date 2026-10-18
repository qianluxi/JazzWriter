"""Consistency checker: flag tension, never auto-correct it.

Each issue reports the entities involved, the **basis** it was detected on, and
a **confidence** level, because heuristics (token overlap + negation) can both
miss cross-kind contradictions and misread deliberate variety. Intentional
contradictions are reported as notes, not errors. A model-based semantic review
is optional and is itself labelled as needing human confirmation.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional

from engine.planning_llm import generate_json
from engine.textutil import similarity, tokens
from world.graph import DependencyGraph
from world.models import WorldDoc

_NEGATIONS = ("不", "无", "非", "禁", "永", "拒绝", "否认", "否定", "推翻", "反对",
              "不得", "丧失", "无法", "没有")


class WorldChecker:
    def check(self, doc: WorldDoc, llm=None) -> List[Dict[str, object]]:
        issues: List[Dict[str, object]] = []
        issues.extend(self._duplicates(doc))
        issues.extend(self._conflicting_pairs(doc))
        issues.extend(self._rule_violations(doc))
        issues.extend(self._intentional(doc))
        issues.extend(self._dependency_notes(doc))
        issues.extend(self._model_review(doc, llm))
        if llm is None or getattr(llm, "name", "") in ("mock", ""):
            issues.append({
                "level": "note", "ids": [],
                "message": "离线模式仅做词项启发式检查，无法判断语义冲突；"
                           "“未发现冲突”不等于“与核心规则一致”。",
                "basis": "运行模式=离线", "confidence": "高",
            })
        return issues

    # -- heuristics ---------------------------------------------------------
    @staticmethod
    def _duplicates(doc: WorldDoc) -> List[Dict[str, object]]:
        seen: Dict[str, bool] = {}
        out: List[Dict[str, object]] = []
        for entity in doc.entities:
            key = f"{entity.kind}:{entity.name}"
            if key in seen:
                out.append({
                    "level": "warn", "ids": [entity.id],
                    "message": f"同类同名条目重复：{entity.name}",
                    "basis": "kind + name 完全相同", "confidence": "高",
                })
            seen[key] = True
        return out

    @staticmethod
    def _conflicting_pairs(doc: WorldDoc) -> List[Dict[str, object]]:
        out: List[Dict[str, object]] = []
        rule_tokens = set()
        for entity in doc.of_kind("rule"):
            rule_tokens |= set(tokens(entity.statement))
        entity_tokens = {e.id: set(tokens(e.statement)) for e in doc.entities}
        # Document frequency: tokens shared by many entries are template wording
        # (or the rule reference), not evidence of a contradiction.
        df = Counter()
        for entity in doc.entities:
            if entity.kind == "motif":
                continue
            for token in entity_tokens[entity.id]:
                df[token] += 1
        entities = doc.entities
        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                a, b = entities[i], entities[j]
                if a.kind == "motif" or b.kind == "motif" or "rule" in (a.kind, b.kind):
                    continue
                shared = (entity_tokens[a.id] & entity_tokens[b.id]) - rule_tokens
                rare = {t for t in shared if df.get(t, 0) <= 2}
                if len(rare) < 2:
                    continue
                neg_a = any(m in a.statement for m in _NEGATIONS)
                neg_b = any(m in b.statement for m in _NEGATIONS)
                if neg_a == neg_b:
                    continue
                term = sorted(rare, key=len, reverse=True)[0]
                cross = a.kind != b.kind
                out.append({
                    "level": "warn", "ids": [a.id, b.id],
                    "message": f"可能冲突（围绕「{term}」)：{a.label()} 与 {b.label()} 表述相反。",
                    "basis": f"共享罕见词项「{term}」等 {len(rare)} 个 + 一侧含否定词"
                             + ("（跨类别）" if cross else ""),
                    "confidence": "中" if cross else "低",
                })
        return out

    @staticmethod
    def _rule_violations(doc: WorldDoc) -> List[Dict[str, object]]:
        """Dedicated rule <-> downstream check (offline heuristic)."""
        rules = doc.of_kind("rule")
        others = [e for e in doc.entities if e.kind not in ("rule", "motif")]
        if not rules or not others:
            return []
        entity_tokens = {e.id: set(tokens(e.statement)) for e in others}
        df = Counter()
        for entity in others:
            for token in entity_tokens[entity.id]:
                df[token] += 1
        out: List[Dict[str, object]] = []
        for rule in rules:
            rule_tokens = set(tokens(rule.statement))
            rule_neg = any(m in rule.statement for m in _NEGATIONS)
            for entity in others:
                rare = {t for t in (rule_tokens & entity_tokens[entity.id]) if df.get(t, 0) <= 2}
                if len(rare) < 2:
                    continue
                if any(m in entity.statement for m in _NEGATIONS) == rule_neg:
                    continue
                term = sorted(rare, key=len, reverse=True)[0]
                out.append({
                    "level": "warn", "ids": [rule.id, entity.id],
                    "message": f"疑似与核心规则冲突（围绕「{term}」)：{entity.label()} 的表述与规则相反。",
                    "basis": "规则↔条目 词项重叠 + 否定方向相反", "confidence": "中",
                })
        return out

    @staticmethod
    def _intentional(doc: WorldDoc) -> List[Dict[str, object]]:
        return [{
            "level": "note", "ids": [e.id],
            "message": f"有意保留的矛盾：{e.statement}",
            "basis": "条目状态=contradiction", "confidence": "高",
        } for e in doc.entities if e.state == "contradiction"]

    @staticmethod
    def _dependency_notes(doc: WorldDoc) -> List[Dict[str, object]]:
        graph = DependencyGraph(doc)
        out: List[Dict[str, object]] = []
        for entity in doc.of_kind("rule"):
            impacted = graph.impact_report(entity.id)["candidates"]
            if impacted:
                out.append({
                    "level": "note", "ids": [entity.id],
                    "message": f"若修改「{entity.label()}」，将牵连候选条目：{'、'.join(impacted)}",
                    "basis": "依赖图（depends_on 反查）", "confidence": "高",
                })
        return out

    # -- optional semantic review -------------------------------------------
    @staticmethod
    def _model_review(doc: WorldDoc, llm) -> List[Dict[str, object]]:
        if llm is None or getattr(llm, "name", "") in ("mock", ""):
            return []
        digest = "\n".join(f"{e.id} [{e.kind}/{e.state}] {e.statement}" for e in doc.entities)
        prompt = (
            "下面是按核心规则推导出的世界设定条目。找出**跨类别**的语义矛盾或与核心规则冲突的条目。"
            "只报告，不修改。\n"
            f"{digest}\n"
            '只输出 JSON：{"conflicts":[{"ids":[""],"reason":"","confidence":"低|中|高"}]}'
        )
        data = generate_json(llm, prompt, max_tokens=1500)
        if not data or not isinstance(data.get("conflicts"), list):
            return []
        out: List[Dict[str, object]] = []
        for item in data["conflicts"]:
            if not isinstance(item, dict):
                continue
            ids = [str(i) for i in item.get("ids", []) if str(i).strip()]
            if not ids:
                continue
            out.append({
                "level": "warn", "ids": ids,
                "message": f"模型提出的语义冲突：{item.get('reason', '')}",
                "basis": "模型语义审阅（需人工确认）",
                "confidence": str(item.get("confidence") or "低"),
            })
        return out
