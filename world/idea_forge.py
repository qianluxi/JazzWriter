"""Idea Forge: raise several *structurally different* worlds from one seed.

Divergence is measured on **world mechanics**, not wording. Each prototype
answers the same structural questions (how the rule works, who holds power, how
knowledge is distributed, what dilemma a person faces, how time behaves); two
prototypes that answer them the same way are reported as near-duplicates even if
their labels differ. The score is a comparison aid, never a claim of novelty.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from engine.planning_llm import generate_json
from engine.textutil import similarity
from world.models import WorldIdea
from world.util import clauses

DIMENSIONS = (
    "rule_mechanism",       # 规则如何运作
    "power_structure",      # 权力结构
    "knowledge_distribution",  # 知识与信息分配
    "character_dilemma",    # 人物困境
    "temporal_dynamics",    # 时间与历史动力
)

DIMENSION_LABELS: Dict[str, str] = {
    "rule_mechanism": "规则机制",
    "power_structure": "权力结构",
    "knowledge_distribution": "知识分配",
    "character_dilemma": "人物困境",
    "temporal_dynamics": "时间动力",
}

_DUPLICATE_THRESHOLD = 0.86

LENSES: List[Dict[str, object]] = [
    {
        "lens": "认知",
        "label": "认知世界",
        "logline": "世界围绕「{seed}」运转，但只有极少数人能真正解读它。",
        "core_rule": "「{seed}」并非人人可感知：它只对处在特定处境或心境的人显形。",
        "consequence": "知识与无知成为阶层、职业与亲密关系的分界线。",
        "dimensions": {
            "rule_mechanism": "规则只对特定条件的人显形，无法被客观测量。",
            "power_structure": "权力属于能解读它的人：解释者即权威。",
            "knowledge_distribution": "知识高度不对称，多数人终生处于无知状态。",
            "character_dilemma": "知道真相的人无法证明自己，沉默或撒谎都付出代价。",
            "temporal_dynamics": "认知会随处境漂移，历史记录不可信。",
        },
        "axis": "谁看得见、谁看不见",
    },
    {
        "lens": "制度",
        "label": "制度世界",
        "logline": "「{seed}」被写进法律，整个社会围绕它重建了权力结构。",
        "core_rule": "围绕「{seed}」形成了可执行、可争讼、可世袭的解释与执法体系。",
        "consequence": "谁掌握对「{seed}」的解释权，谁就掌握秩序本身。",
        "dimensions": {
            "rule_mechanism": "规则被成文化，有判例、程序与执行机构。",
            "power_structure": "权力分裂为立法、裁决与执行三方，彼此制衡又勾结。",
            "knowledge_distribution": "解释权被机构垄断，普通人只接触被整理过的版本。",
            "character_dilemma": "个人要么服从程序、要么成为被审判的例外。",
            "temporal_dynamics": "历史由判例累积而成，旧案随时被翻案重写。",
        },
        "axis": "解释权与权力",
    },
    {
        "lens": "存在论",
        "label": "存在主义世界",
        "logline": "「{seed}」改写了“存在”的定义：什么算活着、算被记住，都要重来。",
        "core_rule": "「{seed}」让自我与存在之间出现了无法弥合的裂缝。",
        "consequence": "身份、记忆与死亡的边界被永久改写。",
        "dimensions": {
            "rule_mechanism": "规则作用于存在本身，无法用因果或物理描述。",
            "power_structure": "权力不再是统治，而是“谁被承认为存在”。",
            "knowledge_distribution": "无人真正理解规则，只能各自赋予意义。",
            "character_dilemma": "人物必须在“被记住”与“保持自我”之间选择。",
            "temporal_dynamics": "过去可被重新存在，历史与当下互相渗入。",
        },
        "axis": "活着与被记住",
    },
    {
        "lens": "经济",
        "label": "资源世界",
        "logline": "「{seed}」成为最稀缺的资源，货币与劳动被彻底重塑。",
        "core_rule": "「{seed}」的获取与流转遵循一套残酷而稳定的供需法则。",
        "consequence": "围绕它诞生了新的职业、黑市与债务文明。",
        "dimensions": {
            "rule_mechanism": "规则体现为可占有、可交易的稀缺资源与稳定的供需曲线。",
            "power_structure": "权力属于控制获取与流通节点的人。",
            "knowledge_distribution": "知识被当作商品定价，真相需要购买。",
            "character_dilemma": "人物必须在生存需要与道德底线之间交易。",
            "temporal_dynamics": "历史由价格与债务周期推动，繁荣与崩溃交替。",
        },
        "axis": "稀缺与交易",
    },
    {
        "lens": "信仰",
        "label": "信仰世界",
        "logline": "「{seed}」被一部分人奉为神明，被另一部分人视为禁忌。",
        "core_rule": "关于「{seed}」的解释分裂成彼此敌对的教义。",
        "consequence": "信仰之争渗入日常，暴力与仪式共存。",
        "dimensions": {
            "rule_mechanism": "规则通过仪式与禁忌被体验，效力来自信念而非实证。",
            "power_structure": "权力属于掌握正统教义的祭司集团。",
            "knowledge_distribution": "知识以教义形式分级，异端解释被压制。",
            "character_dilemma": "信仰与诚实的冲突：说真话即成为异端。",
            "temporal_dynamics": "历史被神话化，起源故事不断被改写以服务当下。",
        },
        "axis": "崇拜与禁忌",
    },
    {
        "lens": "物理/技术",
        "label": "机制世界",
        "logline": "「{seed}」遵循一套可被经验、却无法被完全解释的机制。",
        "core_rule": "「{seed}」有其边界与代价，越过边界者必须付出确定的代价。",
        "consequence": "技术的每一步都在逼近无人真正理解的极限。",
        "dimensions": {
            "rule_mechanism": "规则是可复现的机制，有边界、参数与确定的代价。",
            "power_structure": "权力属于掌握技术参数与维护能力的工程师阶层。",
            "knowledge_distribution": "操作知识被广泛掌握，但底层原理无人知晓。",
            "character_dilemma": "人物清楚代价却必须使用它，越界是否值得。",
            "temporal_dynamics": "历史由技术突破与随之而来的事故推动。",
        },
        "axis": "机制与代价",
    },
]


class IdeaForge:
    def __init__(self, llm=None) -> None:
        self.llm = llm

    def ideas(self, seed: str, count: int = 4) -> List[WorldIdea]:
        seed = (seed or "").strip()
        count = max(3, min(count, len(LENSES)))
        ideas = self._from_llm(seed, count) or self._from_lenses(seed, count)
        self.analyze(ideas)
        return ideas

    # -- generation ---------------------------------------------------------
    def _from_llm(self, seed: str, count: int) -> List[WorldIdea]:
        prompt = (
            f"从一个片语出发，提出 {count} 个**底层逻辑不同**的世界原型。\n"
            f"片语：{seed}\n"
            "每个原型用不同的底层逻辑（认知/制度/存在论/经济/信仰/物理）重新解释同一片语；"
            "不要只改地名或种族。每个原型都要分别回答五个结构问题：\n"
            "rule_mechanism 规则如何运作、power_structure 权力归属、"
            "knowledge_distribution 知识分配、character_dilemma 人物困境、"
            "temporal_dynamics 时间动力。\n"
            '只输出 JSON：{"ideas":[{"label":"","lens":"","logline":"","core_rule":"",'
            '"consequence_seed":"","dimensions":{"rule_mechanism":"","power_structure":"",'
            '"knowledge_distribution":"","character_dilemma":"","temporal_dynamics":""}}]}'
        )
        data = generate_json(self.llm, prompt, max_tokens=2500)
        if not data or not isinstance(data.get("ideas"), list):
            return []
        out: List[WorldIdea] = []
        for i, item in enumerate(data["ideas"][:count]):
            if not isinstance(item, dict):
                continue
            dims = item.get("dimensions") if isinstance(item.get("dimensions"), dict) else {}
            out.append(WorldIdea(
                id=f"idea-{i + 1}",
                label=str(item.get("label") or item.get("lens") or f"原型{i + 1}"),
                lens=str(item.get("lens") or ""),
                logline=str(item.get("logline") or ""),
                core_rule=str(item.get("core_rule") or ""),
                consequence_seed=str(item.get("consequence_seed") or ""),
                dimensions={k: str(dims.get(k, "")) for k in DIMENSIONS},
                status="candidate",
            ))
        return out if len(out) >= 3 else []

    def _from_lenses(self, seed: str, count: int) -> List[WorldIdea]:
        core = clauses(seed)[0] if clauses(seed) else (seed or "一个未说出口的念头")
        out: List[WorldIdea] = []
        for i, lens in enumerate(LENSES[:count]):
            dims = {k: str(v) for k, v in lens["dimensions"].items()}  # type: ignore[union-attr]
            out.append(WorldIdea(
                id=f"idea-{i + 1}",
                label=str(lens["label"]),
                lens=str(lens["lens"]),
                logline=str(lens["logline"]).format(seed=core),
                core_rule=str(lens["core_rule"]).format(seed=core),
                consequence_seed=str(lens["consequence"]),
                dimensions=dims,
                differentiators=[str(lens["lens"]), str(lens["axis"])],
                status="candidate",
            ))
        return out

    # -- analysis -----------------------------------------------------------
    def analyze(self, ideas: List[WorldIdea]) -> List[WorldIdea]:
        """Score divergence on mechanics and flag structural near-duplicates."""
        for idea in ideas:
            idea.dimensions = {k: idea.dimensions.get(k, "") for k in DIMENSIONS}
            idea.mechanism = " ".join(idea.dimensions.get(k, "") for k in DIMENSIONS)
            if not idea.mechanism.strip():
                idea.mechanism = f"{idea.core_rule} {idea.logline}"
        for i, idea in enumerate(ideas):
            others = [t for j, t in enumerate(ideas) if j != i]
            sim = [similarity(idea.mechanism, o.mechanism) for o in others]
            idea.distinctness = round(1.0 - max(sim), 3) if sim else 1.0
            best: Optional[WorldIdea] = None
            best_sim = -1.0
            for o in others:
                s = similarity(idea.mechanism, o.mechanism)
                if s > best_sim:
                    best_sim, best = s, o
            if best is not None and best_sim >= _DUPLICATE_THRESHOLD:
                idea.near_duplicate = best.id
            dims = self._differentiating_dimensions(idea, others)
            if dims:
                idea.differentiators = list(dict.fromkeys(idea.differentiators + dims))
        return ideas

    @staticmethod
    def _differentiating_dimensions(idea: WorldIdea, others: List[WorldIdea]) -> List[str]:
        out: List[str] = []
        for dim in DIMENSIONS:
            here = idea.dimensions.get(dim, "")
            if not here:
                continue
            if all(similarity(here, o.dimensions.get(dim, "")) < 0.5 for o in others):
                out.append(DIMENSION_LABELS[dim])
        return out

    def duplicate_warnings(self, ideas: List[WorldIdea]) -> List[str]:
        return [
            f"{i.label}({i.id}) 与 {i.near_duplicate} 机制高度相似，可能只是换了名称"
            for i in ideas if i.near_duplicate
        ]
