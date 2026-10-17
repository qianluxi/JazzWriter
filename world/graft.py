"""Graft: import an existing worldview, extract its *skeleton*, then transform.

The skeleton keeps only the abstract, reusable layer (rules, themes, power,
history, aesthetics) so a graft produces a genuinely new world instead of a
renamed copy. Every step is written to ``provenance`` so the author can see
what was inherited, what changed, and where rules conflict.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from pydantic import Field

from core.base import Model
from engine.planning_llm import generate_json
from world.expander import WorldExpander
from world.models import WorldDoc, WorldIdea
from world.util import clauses

OPS: Dict[str, str] = {
    "深度变形": "保留少量核心规则，重新推导社会、历史与生活方式",
    "主题移植": "保留主题矛盾，改换时代、制度与技术条件",
    "世界交叉": "从两个设定中选择可兼容的规则，再处理冲突",
    "边缘扩展": "保留原世界底层逻辑，创造此前未重点描写的区域或时代",
    "反转前提": "改变一条关键假设，观察整个世界的连锁变化",
}

_RULE_KW = ("规则", "必须", "禁止", "只能", "不得", "法律", "法则", "代价", "契约", "代价")
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
        skeleton = self._extract_llm(text, source_name, title)
        if skeleton is None:
            skeleton = self._extract_heuristic(text, source_name, title)
        return skeleton

    def _extract_heuristic(self, text: str, source_name: str, title: str) -> Skeleton:
        skel = Skeleton(source_name=source_name, title=title)
        buckets = {
            "rules": (skel.rules, _RULE_KW),
            "themes": (skel.themes, _THEME_KW),
            "power": (skel.power, _POWER_KW),
            "history": (skel.history, _HISTORY_KW),
            "aesthetics": (skel.aesthetics, _AESTHETIC_KW),
        }
        for sentence in clauses(text):
            if len(sentence) < 3:
                continue
            for _, (bucket, kws) in buckets.items():
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
    def transform(
        self,
        skeleton: Skeleton,
        op: str,
        seed: str,
        second: Optional[Skeleton] = None,
    ) -> Tuple[WorldDoc, List[str]]:
        op = op if op in OPS else "深度变形"
        base_rule = skeleton.primary_rule(seed)
        new_rule, kept, changed, conflicts = self._apply_op(skeleton, op, seed, base_rule, second)
        doc = WorldDoc(
            title=seed or f"{op}·{skeleton.title or '新世界'}",
            seed=seed,
            premise=f"以「{op}」对来源材料进行改造后的世界。",
            generation="graft" if self.llm is None or getattr(self.llm, "name", "") in ("mock", "") else "graft_llm",
            chosen_idea=WorldIdea(
                id="graft-op", label=op, lens=op, logline=seed,
                core_rule=new_rule, consequence_seed=changed,
            ),
        )
        self.expander.expand(doc)
        for entity in doc.entities:
            entity.source = f"graft:{op}"
        notes = [f"来源：{skeleton.source_name or '（未命名材料）'}",
                 f"变形操作：{op} —— {OPS[op]}"]
        if kept:
            notes.append("继承：" + "；".join(kept))
        if changed:
            notes.append("改变：" + changed)
        if second is not None:
            notes.append(f"交叉来源：{second.source_name or '（未命名材料）'}")
        if conflicts:
            doc.contradictions.extend(conflicts)
            notes.append("规则冲突：" + "；".join(conflicts))
        doc.provenance = notes
        return doc, notes

    @staticmethod
    def _apply_op(skeleton, op, seed, base_rule, second):
        kept: List[str] = []
        changed = ""
        conflicts: List[str] = []
        if op == "深度变形":
            new_rule = base_rule
            kept = [base_rule]
            changed = "时代、技术与生活方式全部重新推导，只保留核心规则。"
        elif op == "主题移植":
            theme = skeleton.themes[0] if skeleton.themes else base_rule
            new_rule = f"世界的底层矛盾是「{theme}」，但它现在以「{seed or '新技术'}」为载体。"
            kept = [f"主题：{theme}"]
            changed = "时代、制度与技术条件被替换。"
        elif op == "世界交叉":
            other = second.primary_rule(seed) if second else (seed or "另一条外来规则")
            new_rule = f"{base_rule} 与「{other}」在同一世界并存。"
            kept = [base_rule, other]
            conflicts = [f"「{base_rule}」与「{other}」在因果上可能互斥，需要设定调和机制。"]
            changed = "两套规则被并置，冲突处需要新的解释。"
        elif op == "边缘扩展":
            new_rule = base_rule
            kept = [base_rule]
            changed = "把镜头移向原世界的边缘区域或相邻时代。"
        else:  # 反转前提
            new_rule = f"{base_rule} 被颠倒：世界遵循与之相反的法则。"
            kept = []
            changed = "关键前提被反转，全部后果需要重新推导。"
            conflicts = [f"与原作前提相反：{base_rule}"]
        return new_rule, kept, changed, conflicts
