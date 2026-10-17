"""Idea Forge: raise several *structurally different* worlds from one seed.

The point is divergence, not decoration: each prototype reinterprets the same
seed through a different *underlying logic* (lens), so choosing between them is
a real creative choice rather than a change of place-names.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from engine.planning_llm import generate_json
from engine.textutil import similarity
from world.models import WorldIdea
from world.util import clauses

LENSES: List[Dict[str, str]] = [
    {
        "lens": "认知",
        "label": "认知世界",
        "logline": "世界围绕「{seed}」运转，但只有极少数人能真正解读它。",
        "core_rule": "「{seed}」并非人人可感知：它只对处在特定处境或心境的人显形。",
        "consequence": "知识与无知成为阶层、职业与亲密关系的分界线。",
        "axis": "谁看得见、谁看不见",
    },
    {
        "lens": "制度",
        "label": "制度世界",
        "logline": "「{seed}」被写进法律，整个社会围绕它重建了权力结构。",
        "core_rule": "围绕「{seed}」形成了可执行、可争讼、可世袭的解释与执法体系。",
        "consequence": "谁掌握对「{seed}」的解释权，谁就掌握秩序本身。",
        "axis": "解释权与权力",
    },
    {
        "lens": "存在论",
        "label": "存在主义世界",
        "logline": "「{seed}」改写了“存在”的定义：什么算活着、算被记住，都要重来。",
        "core_rule": "「{seed}」让自我与存在之间出现了无法弥合的裂缝。",
        "consequence": "身份、记忆与死亡的边界被永久改写。",
        "axis": "活着与被记住",
    },
    {
        "lens": "经济",
        "label": "资源世界",
        "logline": "「{seed}」成为最稀缺的资源，货币与劳动被彻底重塑。",
        "core_rule": "「{seed}」的获取与流转遵循一套残酷而稳定的供需法则。",
        "consequence": "围绕它诞生了新的职业、黑市与债务文明。",
        "axis": "稀缺与交易",
    },
    {
        "lens": "信仰",
        "label": "信仰世界",
        "logline": "「{seed}」被一部分人奉为神明，被另一部分人视为禁忌。",
        "core_rule": "关于「{seed}」的解释分裂成彼此敌对的教义。",
        "consequence": "信仰之争渗入日常，暴力与仪式共存。",
        "axis": "崇拜与禁忌",
    },
    {
        "lens": "物理/技术",
        "label": "机制世界",
        "logline": "「{seed}」遵循一套可被经验、却无法被完全解释的机制。",
        "core_rule": "「{seed}」有其边界与代价，越过边界者必须付出确定的代价。",
        "consequence": "技术的每一步都在逼近无人真正理解的极限。",
        "axis": "机制与代价",
    },
]


class IdeaForge:
    def __init__(self, llm=None) -> None:
        self.llm = llm

    def ideas(self, seed: str, count: int = 4) -> List[WorldIdea]:
        seed = (seed or "").strip()
        count = max(3, min(count, len(LENSES)))
        llm_ideas = self._from_llm(seed, count)
        ideas = llm_ideas if llm_ideas else self._from_lenses(seed, count)
        self._score(ideas)
        return ideas

    def _from_llm(self, seed: str, count: int) -> List[WorldIdea]:
        prompt = (
            f"从一个片语出发，提出 {count} 个**底层逻辑不同**的世界原型。\n"
            f"片语：{seed}\n"
            "要求：每个原型用不同的底层逻辑（如认知/制度/存在论/经济/信仰/物理）"
            "重新解释同一片语；不要只改地名或种族。\n"
            '只输出 JSON：{"ideas":[{"label":"","lens":"","logline":"","core_rule":""'
            '","consequence_seed":""}]}'
        )
        data = generate_json(self.llm, prompt, max_tokens=2000)
        if not data or not isinstance(data.get("ideas"), list):
            return []
        out: List[WorldIdea] = []
        for i, item in enumerate(data["ideas"][:count]):
            if not isinstance(item, dict):
                continue
            out.append(WorldIdea(
                id=f"idea-{i + 1}",
                label=str(item.get("label") or item.get("lens") or f"原型{i + 1}"),
                lens=str(item.get("lens") or ""),
                logline=str(item.get("logline") or ""),
                core_rule=str(item.get("core_rule") or ""),
                consequence_seed=str(item.get("consequence_seed") or ""),
                status="candidate",
                differentiators=[str(item.get("lens") or "")],
            ))
        return out if len(out) >= 3 else []

    def _from_lenses(self, seed: str, count: int) -> List[WorldIdea]:
        core = clauses(seed)[0] if clauses(seed) else (seed or "一个未说出口的念头")
        out: List[WorldIdea] = []
        for i, lens in enumerate(LENSES[:count]):
            out.append(WorldIdea(
                id=f"idea-{i + 1}",
                label=lens["label"],
                lens=lens["lens"],
                logline=lens["logline"].format(seed=core),
                core_rule=lens["core_rule"].format(seed=core),
                consequence_seed=lens["consequence"],
                status="candidate",
                differentiators=[lens["lens"], lens["axis"]],
            ))
        return out

    @staticmethod
    def _score(ideas: List[WorldIdea]) -> None:
        texts = [f"{i.core_rule} {i.logline}" for i in ideas]
        for i, idea in enumerate(ideas):
            others = [similarity(texts[i], t) for j, t in enumerate(texts) if j != i]
            idea.distinctness = round(1.0 - max(others), 3) if others else 1.0
