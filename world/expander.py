"""World Expander: grow one chosen prototype into a layered worldview.

Offline growth is a **derivation**, not a template lookup. From the core rule we
first infer its properties (observability, scarcity, enforcement mode, cost,
mutability), then derive consequences / knowledge / institution / history /
geography / conflict *from those properties*. Different rules therefore produce
structurally different worlds. Every derived entry keeps a ``basis`` naming the
property it came from, so the chain stays traceable.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from engine.planning_llm import generate_json
from world.models import WorldDoc, WorldEntity
from world.util import clauses, terms

_OBSERVABILITY_KW = ("听见", "看见", "感知", "显形", "洞察", "读数", "测量")
_SCARCITY_KW = ("只有", "唯一", "稀缺", "垄断", "独占", "少数")
_CODIFIED_KW = ("法律", "禁止", "必须", "不得", "判例", "成文", "条例", "执法", "裁决", "判决")
_COSTLY_KW = ("代价", "付出", "耗费", "牺牲", "损耗", "风险")
_MUTABLE_KW = ("漂移", "变化", "改写", "重估", "修订", "更替")


class WorldExpander:
    def __init__(self, llm=None) -> None:
        self.llm = llm

    def expand(self, doc: WorldDoc) -> WorldDoc:
        idea = doc.chosen_idea
        rule = idea.core_rule if idea else (doc.seed or "一条尚未命名的世界规则")
        self._ensure_rule(doc, rule)
        props = rule_properties(doc.seed, rule)
        doc.rule_properties = props
        picked = self._from_llm(doc, rule, props)
        if picked is None:
            picked = self._derive(doc, rule, props)
        entities, questions = picked
        for entity in entities:
            if not doc.by_id(entity.id):
                doc.add(entity)
        for q in questions:
            if q not in doc.open_questions:
                doc.open_questions.append(q)
        return doc

    @staticmethod
    def _ensure_rule(doc: WorldDoc, rule: str) -> None:
        if doc.of_kind("rule"):
            return
        doc.add(WorldEntity(
            id="rule-1", kind="rule", name="核心规则", statement=rule,
            state="confirmed", source="chosen idea", basis="作者选定",
        ))

    # -- deterministic derivation -------------------------------------------
    def _derive(self, doc: WorldDoc, rule: str, props: Dict[str, str]) -> Tuple[List[WorldEntity], List[str]]:
        ref = _short_ref(doc.seed, rule)
        obs, scarce, enf = props["observability"], props["scarcity"], props["enforcement"]
        cost, mutable = props["cost"], props["mutability"]
        spec = [
            ("consequence", "证据经济", f"「{ref}」可观测性{obs}，绝大多数判断只能依赖间接证据，"
                                    "催生了以转述、鉴证与伪证为生的行当。", f"由可观测性={obs} 推导"),
            ("consequence", "接近权", f"由于「{ref}」{scarce}，对它的接近权本身成为可争夺、"
                                  "可继承、可抵押的资产。", f"由稀缺性={scarce} 推导"),
            ("knowledge", "知识分层", f"可观测性{obs}决定知识分层：能直接接触「{ref}」者掌握第一手信息，"
                                  "其余人只能接受被整理过的版本。", f"由可观测性={obs} 推导"),
            ("knowledge", "事实漂移", f"由于「{ref}」{mutable}，一代人确认的“事实”"
                                  "到下一代可能已被重新解释。", f"由可变性={mutable} 推导"),
            ("institution", "裁决机构", f"围绕「{ref}」出现以{enf}方式运作的裁决机构，"
                                    "负责裁定何为有效接触与有效证据。", f"由执行方式={enf} 推导"),
            ("institution", "准入制度", f"「{ref}」{scarce}使准入资格成为制度核心："
                                    "登记、配额与继承规则由此而来。", f"由稀缺性={scarce} 推导"),
            ("history", "边界移动", f"历史由观测条件的变化驱动：每当可观测性={obs}的边界移动，"
                                 "就出现一次全面重估与冲突。", f"由可观测性={obs} 推导"),
            ("history", "周期清算", f"由于「{ref}」{mutable}，每一次官方解释都被后来的代际"
                                 "当作压迫或启示，历史因此周期性地被清算。", f"由可变性={mutable} 推导"),
            ("geography", "成本梯度", f"接近成本{cost}，人口与产业沿成本梯度分布，"
                                  "形成中心—边缘的空间结构。", f"由代价={cost} 推导"),
            ("geography", "管控分层", f"「{ref}」{scarce}且以{enf}方式执行，使管控按距离分层："
                                  "越接近源头越受规制，边缘则被放任。", f"由稀缺性+执行方式 推导"),
            ("conflict", "零和解释权", f"由于「{ref}」{scarce}，解释权是零和的："
                                    "一方获益必然意味着另一方失去接近的可能。", f"由稀缺性={scarce} 推导"),
            ("conflict", "真假之争", f"可观测性{obs}制造了天然的骗子与真先知，"
                                  "二者的证词无法区分，冲突因此不可调和。", f"由可观测性={obs} 推导"),
        ]
        entities: List[WorldEntity] = []
        counters: Dict[str, int] = {}
        for kind, name, statement, basis in spec:
            counters[kind] = counters.get(kind, 0) + 1
            entities.append(WorldEntity(
                kind=kind, id=f"{kind}-{counters[kind]}", name=name, statement=statement,
                state="candidate", source="derived", basis=basis, depends_on=["rule-1"],
            ))
        words = [w for w in (terms(doc.seed, limit=5) or ["沉默"]) if w != ref][:3] or ["沉默"]
        for j, word in enumerate(words, start=1):
            entities.append(WorldEntity(
                kind="motif", id=f"motif-{j}", name=f"意象：{word}",
                statement=f"「{word}」反复出现，每次出现都标记「{ref}」可观测性边界的移动。",
                state="candidate", source="derived", basis="由片语意象提取", depends_on=["rule-1"],
            ))
        questions = [
            f"「{ref}」是可测量的，还是只能被经验？",
            f"违背「{ref}」的代价由谁承担、如何判定？",
            f"谁最先发现了「{ref}」，那个人后来发生了什么？",
        ]
        return entities, questions

    def _from_llm(self, doc: WorldDoc, rule: str, props: Dict[str, str]):
        prompt = (
            "根据核心规则及其属性，逐层推导出一个自洽的世界。\n"
            f"核心规则：{rule}\n"
            f"规则属性：{props}\n"
            f"原始片语：{doc.seed}\n"
            "先由属性推导后果，再由后果推导制度、历史、地理与冲突；每条都要给出依据。\n"
            '只输出 JSON：{"entities":[{"kind":"consequence","name":"","statement":"","basis":""}],'
            '"open_questions":[""]}'
        )
        data = generate_json(self.llm, prompt, max_tokens=2500)
        if not data or not isinstance(data.get("entities"), list):
            return None
        entities: List[WorldEntity] = []
        counters: Dict[str, int] = {}
        for item in data["entities"]:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or "consequence")
            counters[kind] = counters.get(kind, 0) + 1
            entities.append(WorldEntity(
                kind=kind, id=f"{kind}-{counters[kind]}",
                name=str(item.get("name") or kind), statement=str(item.get("statement") or ""),
                state="candidate", source="derived",
                basis=str(item.get("basis") or ""), depends_on=["rule-1"],
            ))
        questions = [str(q) for q in data.get("open_questions", []) if str(q).strip()]
        if not entities:
            return None
        return entities, questions


def rule_properties(seed: str, rule: str) -> Dict[str, str]:
    """Infer the rule's structural properties from its wording (offline heuristics).

    The chosen rule drives the inference (the seed is only a fallback), so two
    different rules on the same seed yield different worlds.
    """
    text = (rule or seed or "").strip()

    def has(*kws: str) -> bool:
        return any(k in text for k in kws)

    return {
        "observability": "低" if has(*_OBSERVABILITY_KW) else "高",
        "scarcity": "稀缺" if has(*_SCARCITY_KW) else "充足",
        "enforcement": "成文法" if has(*_CODIFIED_KW) else "习惯法",
        "cost": "高昂" if has(*_COSTLY_KW) else "可承受",
        "mutability": "会漂移" if has(*_MUTABLE_KW) else "被视为不可变",
    }


def _short_ref(seed: str, rule: str) -> str:
    parts = clauses(seed)
    if parts and 2 <= len(parts[0]) <= 24:
        return parts[0]
    return rule if len(rule) <= 24 else rule[:24]
