"""Plot validator — structural problems with concrete pointers.

It reports *specific issues* (which thread, which chapters) rather than a single
score, e.g. "线索『证据体系有缺陷』只在第 2 章出现，缺少推进或回收".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from core.book_plan import BookPlan

OPEN_TEMPLATES = ("nonlinear_puzzle", "ensemble")


@dataclass
class Issue:
    severity: str          # high | medium | low
    kind: str
    message: str
    chapter: Optional[int] = None

    def to_dict(self) -> Dict:
        return {"severity": self.severity, "kind": self.kind,
                "message": self.message, "chapter": self.chapter}


class PlotValidator:
    def validate(self, book: BookPlan, relationships=None, story_state=None) -> List[Issue]:
        issues: List[Issue] = []
        chapters = book.chapters()
        if not chapters:
            return [Issue("high", "empty", "尚未生成任何章节结构。")]

        # numbering: unique, consecutive, starting at 1
        nums = [c.number for c in chapters]
        if len(set(nums)) != len(nums):
            issues.append(Issue("high", "numbering", f"章节编号重复：{sorted(nums)}"))
        expected = list(range(1, len(chapters) + 1))
        if sorted(nums) != expected:
            missing = sorted(set(expected) - set(nums))
            if missing:
                issues.append(Issue("high", "numbering", f"缺少章节：{missing}（编号不连续）"))
        # per-volume order
        for vol in book.volumes:
            vnums = [c.number for c in vol.chapters]
            if vnums != sorted(vnums):
                issues.append(Issue("low", "order", f"第 {vol.number} 卷章节顺序不正确：{vnums}"))

        # character usage: a registered character that never participates
        if book.cast_ids:
            involved = {cid for c in chapters for cid in c.characters_involved}
            if involved:
                idle = [cid for cid in book.cast_ids if cid not in involved]
                if idle:
                    issues.append(Issue("medium", "unused_character",
                                        f"人物全程未参与任何章节：{idle}（检查是否被闲置或未与主戏连接）"))

        # unknown character ids referenced by chapters
        known = set(book.cast_ids)
        if known:
            for c in chapters:
                refs = set(c.characters_involved)
                if c.pov_character_id:
                    refs.add(c.pov_character_id)
                for rc in c.relationship_changes:
                    refs.update(rc.pair or [])
                unknown = sorted(r for r in refs if r and r not in known)
                if unknown:
                    issues.append(Issue("high", "unknown_character",
                                        f"第 {c.number} 章引用了未知人物 id：{unknown}", c.number))

        # relationship continuity
        rels = getattr(relationships, "relationships", None) if relationships is not None else None
        if rels:
            defined = {(r.source_id, r.target_id) for r in rels} | {(r.target_id, r.source_id) for r in rels}
            changed_pairs = set()
            for c in chapters:
                for rc in c.relationship_changes:
                    pair = rc.pair or []
                    if len(pair) != 2:
                        continue
                    p = (pair[0], pair[1])
                    changed_pairs.add(p)
                    changed_pairs.add((pair[1], pair[0]))
                    if p not in defined:
                        issues.append(Issue("medium", "relationship",
                                            f"第 {c.number} 章发生了未定义的关系变化：{pair}", c.number))
                    if not rc.cause:
                        issues.append(Issue("low", "relationship",
                                            f"第 {c.number} 章的关系变化缺少原因（cause）", c.number))
            for r in rels:
                if r.source_id in known and r.target_id in known and (r.source_id, r.target_id) not in changed_pairs:
                    issues.append(Issue("medium", "relationship",
                                        f"关系 {r.source_id}↔{r.target_id} 在全书从未发生变化"))

            # isolated relationship groups (structure is a deliberate choice, so
            # only warn, never fail)
            if known:
                parent = {cid: cid for cid in known}

                def find(x):
                    while parent[x] != x:
                        parent[x] = parent[parent[x]]
                        x = parent[x]
                    return x

                for r in rels:
                    if r.source_id in known and r.target_id in known:
                        parent[find(r.source_id)] = find(r.target_id)
                groups = {}
                for cid in known:
                    groups.setdefault(find(cid), set()).add(cid)
                if len(groups) > 1:
                    primary = book.primary_character_id
                    isolated = [sorted(g) for g in groups.values() if primary not in g]
                    if isolated:
                        issues.append(Issue("low", "relationship_isolation",
                                            f"存在与主角隔离的人物关系组：{isolated}"
                                            "（若为有意设计可忽略；否则需给出与主线的接触/信息传递机制）"))

        for ch in chapters:
            missing = [f for f, v in (("起因", ch.premise), ("冲突", ch.conflict),
                                      ("结果", ch.outcome)) if not v]
            if missing:
                issues.append(Issue("medium", "incomplete",
                                    f"第 {ch.number} 章缺少：{'、'.join(missing)}。", ch.number))
            if not ch.hook_to and ch.number != chapters[-1].number:
                issues.append(Issue("low", "hook",
                                    f"第 {ch.number} 章没有抛向下一章的驱动力（hook_to 为空）。", ch.number))

        # causal chaining
        for prev, cur in zip(chapters, chapters[1:]):
            if prev.hook_to and cur.hook_from and prev.hook_to.strip() != cur.hook_from.strip():
                issues.append(Issue("low", "causal",
                                    f"第 {cur.number} 章的入口（hook_from）与第 {prev.number} 章的出口不一致，因果链可能断裂。",
                                    cur.number))

        # consecutive identical function
        for prev, cur in zip(chapters, chapters[1:]):
            if prev.function and cur.function and prev.function == cur.function:
                issues.append(Issue("low", "flat",
                                    f"第 {prev.number}、{cur.number} 章功能相同（{cur.function}），节奏可能偏平。",
                                    cur.number))

        # threads with only one appearance
        appearances: Dict[str, List[int]] = {}
        for ch in chapters:
            for t in ch.threads:
                appearances.setdefault(t, []).append(ch.number)
        for thread, chs in appearances.items():
            if len(chs) == 1 and book.structure_template not in OPEN_TEMPLATES:
                issues.append(Issue("medium", "thread",
                                    f"线索「{thread}」只在第 {chs[0]} 章出现，缺少推进或回收。", chs[0]))

        # key turns present
        if not book.key_turns:
            issues.append(Issue("medium", "turns", "全书缺少关键转折（key_turns）。"))

        # ending responds to the opening question
        if book.question and book.ending:
            last = chapters[-1]
            joined = f"{book.ending}{last.outcome}{last.hook_to}"
            if not any(k in joined for k in ("回应", "回答", "理解", "问题", "命题")):
                issues.append(Issue("low", "ending",
                                    "结尾似乎没有回应开篇提出的核心问题（可接受，但要确认是否有意为之）。",
                                    last.number))

        # pov diversity
        povs = {c.pov for c in chapters if c.pov}
        if len(book.cast) > 1 and len(povs) == 1:
            issues.append(Issue("low", "pov", "有多个主要人物，但全书只使用了一个视角。"))

        # knowledge continuity: no knowing without a source, no source from the future
        secret_ids = set()
        if story_state is not None:
            try:
                secret_ids = {f.id for f in story_state.facts("secret")}
            except Exception:  # noqa: BLE001
                secret_ids = set()
        for c in chapters:
            for kc in c.knowledge_changes:
                who = kc.character_id or "?"
                if not kc.source:
                    issues.append(Issue("low", "knowledge",
                                        f"第 {c.number} 章 {who} 的认知变化缺少信息来源(source)", c.number))
                else:
                    nums = [int(x) for x in re.findall(r"第\s*(\d+)\s*章", kc.source)]
                    if nums and min(nums) > c.number:
                        issues.append(Issue("medium", "knowledge",
                                            f"第 {c.number} 章 {who} 的信息来源指向未来章节（{kc.source}）",
                                            c.number))
                    residual = re.sub(r"第\s*\d+\s*章", "", kc.source).strip(" ·，,;；:-—")
                    if len(residual) < 2:
                        issues.append(Issue("low", "knowledge",
                                            f"第 {c.number} 章 {who} 的知识来源过于宽泛（只给了章号，未说明通过什么得知）",
                                            c.number))
                if kc.fact_id and kc.fact_id in secret_ids:
                    issues.append(Issue("low", "knowledge",
                                        f"第 {c.number} 章通过认知变化涉及秘密 {kc.fact_id}，请确认揭露时机",
                                        c.number))

        return issues
