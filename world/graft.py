"""Graft: import an existing worldview, extract its *skeleton*, then transform.

An operator is now a **structured transformation plan**, not a note: it names
what must be kept, what premise is inverted, which property shifts, which new
rules are added, and the expected downstream impact. The plan is handed to the
expander, so offline output actually changes with the operator. Every produced
entry is candidate material for the author.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from pydantic import Field

from core.base import Model
from engine.planning_llm import generate_json
from world.expander import WorldExpander
from world.graph import DependencyGraph
from world.models import WorldDoc, WorldEntity, WorldIdea
from world.util import clauses

OPS: Dict[str, str] = {
    "深度变形": "保留少量核心规则，重新推导社会、历史与生活方式",
    "主题移植": "保留主题矛盾，改换时代、制度与技术条件",
    "世界交叉": "从两个设定中选择可兼容的规则，再处理冲突",
    "边缘扩展": "保留原世界底层逻辑，创造此前未重点描写的区域或时代",
    "反转前提": "改变一条关键假设，观察整个世界的连锁变化",
}

_ANTONYM = (
    ("只有", "人人"), ("少数", "多数"), ("稀缺", "充足"), ("垄断", "公开"), ("独占", "共享"),
    ("听见", "听不见"), ("看见", "看不见"), ("感知", "无法感知"), ("显形", "隐形"),
    ("禁止", "允许"), ("必须", "可以不"), ("不得", "可以"), ("秘密", "公开"),
    ("昂贵", "廉价"), ("高昂", "低廉"), ("代价", "无代价"), ("死亡", "永生"), ("遗忘", "铭记"),
)
_FLIP = {
    "低": "高", "高": "低", "稀缺": "充足", "充足": "稀缺",
    "成文法": "习惯法", "习惯法": "成文法", "高昂": "可承受", "可承受": "高昂",
    "被视为不可变": "会漂移", "会漂移": "被视为不可变",
}

_RULE_KW = ("规则", "必须", "禁止", "只能", "不得", "法律", "法则", "代价", "契约")
_THEME_KW = ("主题", "母题", "意义", "命运", "孤独", "牺牲", "身份", "信仰", "记忆")
_POWER_KW = ("权力", "阶层", "统治", "贵族", "机构", "议会", "教团", "家族", "帝国", "王")
_HISTORY_KW = ("历史", "战争", "年代", "曾经", "灾变", "王朝", "过去", "纪元", "远古")
_AESTHETIC_KW = ("风格", "美学", "建筑", "服饰", "语言", "色彩", "机械", "蒸汽", "魔法", "科技")


class Skeleton(Model):
    title: str = ""
    source_name: str = ""
    rules: List[str] = Field(default_factory=list)
    themes: List[str] = Field(default_factory=list)
    power: List[str] = Field(default_factory=list)
    history: List[str] = Field(default_factory=list)
    aesthetics: List[str] = Field(default_factory=list)

    def primary_rule(self, fallback: str = "") -> str:
        if self.rules:
            return max(self.rules, key=len)
        return fallback or "一条来源不明的世界规则"


class GraftEngine:
    def __init__(self, llm=None) -> None:
        self.llm = llm
        self.expander = WorldExpander(llm)

    # -- extract ------------------------------------------------------------
    def extract(self, text: str, source_name: str = "", title: str = "") -> Skeleton:
        return self._extract_llm(text, source_name, title) or \
            self._extract_heuristic(text, source_name, title)

    def _extract_heuristic(self, text: str, source_name: str, title: str) -> Skeleton:
        skel = Skeleton(source_name=source_name, title=title)
        buckets = (
            (skel.rules, _RULE_KW), (skel.themes, _THEME_KW), (skel.power, _POWER_KW),
            (skel.history, _HISTORY_KW), (skel.aesthetics, _AESTHETIC_KW),
        )
        for sentence in clauses(text):
            if len(sentence) < 3:
                continue
            for bucket, kws in buckets:
                if any(k in sentence for k in kws):
                    bucket.append(sentence)
                    break
        if not skel.rules:
            skel.rules = clauses(text)[:3] or ["来源材料未提供明确规则"]
        return skel

    def _extract_llm(self, text: str, source_name: str, title: str) -> Optional[Skeleton]:
        prompt = (
            "把下面的世界观材料拆解为可复用的**骨架**，只保留抽象规则与结构，"
            "不要抄袭人物、专名与独特表述。\n"
            f"材料：\n{text[:6000]}\n"
            '只输出 JSON：{"rules":[""],"themes":[""],"power":[""],"history":[""],"aesthetics":[""]}'
        )
        data = generate_json(self.llm, prompt, max_tokens=2000)
        if not data:
            return None
        skel = Skeleton(source_name=source_name, title=title)
        for key in ("rules", "themes", "power", "history", "aesthetics"):
            value = data.get(key)
            if isinstance(value, list):
                setattr(skel, key, [str(v) for v in value if str(v).strip()])
        return skel if skel.rules else None

    # -- transform ----------------------------------------------------------
    def plan(self, skeleton: Skeleton, op: str, seed: str,
             second: Optional[Skeleton] = None) -> dict:
        if op == "世界交叉" and second is None:
            raise ValueError("「世界交叉」需要两份来源材料（缺少第二份）。")
        base_rule = skeleton.primary_rule(seed)
        ref = _ref(seed)
        other = second.primary_rule(seed) if second else ""
        theme = skeleton.themes[0] if skeleton.themes else base_rule
        plan: Dict[str, object] = {"op": op, "base_rule": base_rule, "ref": ref,
                                   "properties": {}, "extra_rules": [], "notes": []}
        if op == "深度变形":
            new_rule = base_rule
            plan["keep"] = [base_rule]
            plan["properties"] = {"cost": "高昂", "mutability": "会漂移"}
            plan["extra_rules"] = [
                f"在新社会条件下，接触「{ref}」的成本被推高到需要用一生偿付；"
                "由此形成以“预支—偿还”为骨架的社会关系。",
                f"对「{ref}」的解释权在代际之间周期性转移，每次转移都伴随一次制度重写。",
            ]
            plan["expected"] = "社会结构、技术与生活方式在原规则下被重新推导。"
        elif op == "主题移植":
            new_rule = f"世界的底层矛盾是「{theme}」，但它现在以「{seed or '新载体'}」为载体。"
            plan["keep"] = [f"主题：{theme}"]
            plan["properties"] = {"observability": "高", "enforcement": "习惯法"}
            plan["extra_rules"] = [
                f"主题「{theme}」通过「{seed or '新载体'}」的制度安排被具体化："
                "它以可被日常检验的方式出现，而非抽象命题。",
            ]
            plan["expected"] = "时代、制度与技术条件被替换，主题矛盾保留。"
        elif op == "世界交叉":
            new_rule = f"{base_rule} 与「{other}」在同一世界并存。"
            plan["keep"] = [base_rule, other]
            plan["properties"] = {"observability": "高", "scarcity": "稀缺"}
            plan["extra_rules"] = [
                f"裁决规则：当「{base_rule}」与「{other}」对同一事件给出不同结论时，"
                "以更早被记录者为先；无记录时以代价更高者的结论为准。",
            ]
            plan["conflicts"] = [f"「{base_rule}」与「{other}」在因果上可能互斥，已附调和裁决规则。"]
            plan["expected"] = "两套规则并置，冲突由显式裁决规则处理。"
        elif op == "边缘扩展":
            new_rule = f"在世界的边缘，「{ref}」的执行被大幅削弱，形成与中心不同的局部秩序。"
            plan["keep"] = [base_rule]
            plan["properties"] = {"enforcement": "习惯法", "scarcity": "充足"}
            plan["extra_rules"] = [
                f"边缘区域采用“自有证据优先”：当地对「{ref}」的认定不受中心裁决机构约束。",
            ]
            plan["expected"] = "保留底层逻辑，焦点移向边缘区域或相邻时代。"
        else:  # 反转前提
            new_rule = _reverse(base_rule, ref)
            plan["remove"] = [base_rule]
            plan["properties"] = {k: _FLIP.get(v, v) for k, v in
                                  {"observability": "低", "scarcity": "稀缺",
                                   "enforcement": "成文法", "cost": "高昂",
                                   "mutability": "被视为不可变"}.items()}
            plan["extra_rules"] = [
                f"前提反转后，原先被垄断的「{ref}」变为人人可及；"
                "由此产生的稀缺从“接近”转移到“筛选与信任”。",
            ]
            plan["conflicts"] = [f"与原作前提相反：{base_rule}"]
            plan["expected"] = "关键前提被具体反转，全部后果重新推导。"
        if second is not None:
            plan["second_source"] = second.source_name or "（未命名材料）"
        plan["new_rule"] = new_rule
        return plan

    def transform(self, skeleton: Skeleton, op: str, seed: str,
                  second: Optional[Skeleton] = None) -> Tuple[WorldDoc, List[str]]:
        op = op if op in OPS else "深度变形"
        plan = self.plan(skeleton, op, seed, second)
        new_rule = str(plan.get("new_rule") or _rule_of(plan, seed))
        doc = WorldDoc(
            title=seed or f"{op}·{skeleton.title or '新世界'}",
            seed=seed,
            premise=f"以「{op}」对来源材料进行改造后的世界。",
            generation="graft_llm" if self._live() else "graft",
            chosen_idea=WorldIdea(id="graft-op", label=op, lens=op, logline=seed,
                                  core_rule=new_rule,
                                  consequence_seed=str(plan.get("expected", ""))),
        )
        self.expander.expand(doc, plan={**plan, "op": op, "source": f"graft:{op}",
                                        "basis": f"嫁接操作：{op}"})
        for entity in doc.entities:
            entity.source = f"graft:{op}"
        graph = DependencyGraph(doc)
        downstream = graph.names(graph.impacted_by(doc.of_kind("rule")[0].id))
        diff = {
            "inherit": [str(x) for x in plan.get("keep", [])],
            "remove": [str(x) for x in plan.get("remove", [])],
            "modify": [str(plan["expected"])] if plan.get("expected") else [],
            "add": [str(x) for x in plan.get("extra_rules", [])],
            "downstream": downstream,
        }
        doc.graft_plan = {k: plan.get(k, []) for k in ("op", "base_rule", "keep", "remove",
                                                       "properties", "expected")}
        doc.graft_diff = diff
        if plan.get("conflicts"):
            doc.contradictions.extend([str(c) for c in plan["conflicts"]])
        doc.provenance = _provenance(skeleton, op, second, plan, diff)
        return doc, doc.provenance

    def _live(self) -> bool:
        return self.llm is not None and getattr(self.llm, "name", "") not in ("mock", "")


def _rule_of(plan: dict, seed: str) -> str:
    op = plan.get("op")
    base = str(plan.get("base_rule", ""))
    ref = str(plan.get("ref", seed))
    if op == "主题移植":
        theme = (plan.get("keep") or [base])[0].replace("主题：", "")
        return f"世界的底层矛盾是「{theme}」，但它现在以「{seed or '新载体'}」为载体。"
    if op == "世界交叉":
        other = str(plan.get("second_rule", "")) or str(seed)
        return f"{base} 与「{other}」在同一世界并存。"
    if op == "边缘扩展":
        return f"在世界的边缘，「{ref}」的执行被大幅削弱，形成与中心不同的局部秩序。"
    if op == "反转前提":
        return _reverse(base, ref)
    return base


def _reverse(rule: str, ref: str) -> str:
    out = rule
    for src, dst in _ANTONYM:
        if src in out:
            out = out.replace(src, dst, 1)
            break
    else:
        out = f"{rule} 彻底失效（其对立面取而代之）"
    return f"{out}"


def _ref(seed: str) -> str:
    parts = clauses(seed)
    return parts[0] if parts else (seed or "这条规则")


def _provenance(skeleton: Skeleton, op: str, second: Optional[Skeleton],
                plan: dict, diff: Dict[str, List[str]]) -> List[str]:
    notes = [f"来源：{skeleton.source_name or '（未命名材料）'}",
             f"变形操作：{op} —— {OPS[op]}"]
    for label, key in (("继承", "inherit"), ("删除", "remove"), ("新增", "add")):
        if diff.get(key):
            notes.append(f"{label}：{'；'.join(diff[key])}")
    if plan.get("expected"):
        notes.append(f"预期影响：{plan['expected']}")
    if second is not None:
        notes.append(f"交叉来源：{second.source_name or '（未命名材料）'}")
    if plan.get("conflicts"):
        notes.append("规则冲突：" + "；".join(str(c) for c in plan["conflicts"]))
    return notes
