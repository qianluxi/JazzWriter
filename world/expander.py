"""World Expander: grow one chosen prototype into a layered worldview.

Offline growth is a **derivation**, not a template lookup:

  1. infer the rule's structural properties (observability / scarcity /
     enforcement / cost / mutability) with explicit **evidence** and
     **confidence**, allowing *unknown* instead of guessing;
  2. derive a **multi-level dependency chain** from those properties:
     rule -> consequence -> institution/history -> geography/conflict.

Every entry records the ``basis`` (which property it came from) and real
``depends_on`` ids, so the graph is a causal chain rather than a star. Model
output is validated strictly; anything malformed triggers the offline path with
a visible note.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from engine.planning_llm import generate_json
from world.models import KINDS, KIND_LABELS, PROPERTY_LABELS, WorldDoc, WorldEntity
from world.util import clauses, terms

_UNKNOWN = "未知"

_OBS_KW = ("听见", "看见", "感知", "显形", "洞察", "读取", "测量", "观测")
_OBS_SCOPE_HIGH = ("人人", "所有人", "任何", "普遍", "都能", "都可", "公开")
_SCARCE_KW = ("只有", "唯一", "少数", "稀缺", "垄断", "独占", "极少", "罕见")
_ABUNDANT_KW = ("充足", "普遍", "丰富", "人人都有", "随处可见")
_CODIFIED_KW = ("法律", "禁止", "必须", "不得", "判例", "成文", "条例", "执法", "裁决", "判决")
_CUSTOM_KW = ("习惯", "传统", "风俗", "舆论", "约定俗成", "不成文")
_COSTLY_KW = ("代价", "付出", "耗费", "牺牲", "风险", "损耗")
_CHEAP_KW = ("廉价", "轻易", "免费", "无需", "轻松")
_IMMUTABLE_KW = ("不变", "永恒", "从未改变", "不可更改", "亘古")
_MUTABLE_KW = ("漂移", "变化", "改写", "重估", "修订", "更替", "演变")
_NEGATION = ("不", "无", "非", "没", "未", "别")

_DISPLAY = {"未知": "尚不明确"}


class WorldExpander:
    def __init__(self, llm=None) -> None:
        self.llm = llm

    def expand(self, doc: WorldDoc, plan: Optional[dict] = None) -> WorldDoc:
        idea = doc.chosen_idea
        rule = idea.core_rule if idea else (doc.seed or "一条尚未命名的世界规则")
        rule_id = self._ensure_rule(doc, rule)
        analysis = rule_property_analysis(doc.seed, rule)
        if plan and isinstance(plan.get("properties"), dict):
            for key, value in plan["properties"].items():
                if key in analysis:
                    analysis[key] = {"value": value, "evidence": "嫁接操作指定的属性偏移",
                                     "confidence": "中"}
        doc.rule_properties = {k: a["value"] for k, a in analysis.items()}
        doc.rule_property_basis = {k: f"{a['evidence']}（把握：{a['confidence']}）"
                                   for k, a in analysis.items()}

        picked = self._from_llm(doc, rule, analysis, rule_id)
        if picked is None:
            picked = self._derive(doc, rule, analysis, rule_id)
        entities, questions = picked
        for entity in entities:
            if not doc.by_id(entity.id):
                doc.add(entity)
        for q in questions:
            if q not in doc.open_questions:
                doc.open_questions.append(q)
        for key, entry in analysis.items():
            if entry["value"] == _UNKNOWN:
                q = f"「{PROPERTY_LABELS.get(key, key)}」尚无定论，需要作者确认。"
                if q not in doc.open_questions:
                    doc.open_questions.append(q)
        if plan:
            self._apply_plan(doc, plan, rule_id)
        return doc

    @staticmethod
    def _ensure_rule(doc: WorldDoc, rule: str) -> str:
        existing = doc.of_kind("rule")
        if existing:
            return existing[0].id
        doc.add(WorldEntity(id="rule-1", kind="rule", name="核心规则", statement=rule,
                            state="confirmed", source="chosen idea", basis="作者选定"))
        return "rule-1"

    @staticmethod
    def _apply_plan(doc: WorldDoc, plan: dict, rule_id: str) -> None:
        for i, text in enumerate(plan.get("extra_rules", []), start=1):
            if not str(text).strip() or doc.by_id(f"rule-add-{i}"):
                continue
            doc.add(WorldEntity(
                kind="rule", id=f"rule-add-{i}", name=f"{plan.get('op', '嫁接')}新增规则{i}",
                statement=str(text), state="candidate",
                source=plan.get("source", "graft"), basis=plan.get("basis", "嫁接操作"),
                depends_on=[rule_id]))
        for note in plan.get("notes", []):
            if note not in doc.notes:
                doc.notes.append(str(note))

    # -- deterministic derivation -------------------------------------------
    def _derive(self, doc: WorldDoc, rule: str, analysis: Dict[str, dict], rule_id: str
                ) -> Tuple[List[WorldEntity], List[str]]:
        ref = _short_ref(doc.seed, rule)
        obs = _disp(analysis["observability"]["value"])
        scarce = _disp(analysis["scarcity"]["value"])
        enf = _disp(analysis["enforcement"]["value"])
        cost = _disp(analysis["cost"]["value"])
        mutable = _disp(analysis["mutability"]["value"])
        R = rule_id

        spec: List[Tuple[str, str, str, str, str, List[str]]] = [
            ("consequence", "consequence-1", "证据经济",
             f"「{ref}」可观测性{obs}，多数判断只能依赖间接证据，"
             "催生了以转述、鉴证与伪证为生的行当。", "可观测性", [R]),
            ("consequence", "consequence-2", "接近权",
             f"由于「{ref}」稀缺性{scarce}，接近权本身成为可争夺、可继承、可抵押的资产。",
             "稀缺性", [R]),
            ("knowledge", "knowledge-1", "知识分层",
             f"可观测性{obs}决定知识分层：能直接接触「{ref}」者掌握一手信息，其余人只得到整理版。",
             "可观测性", [R]),
            ("knowledge", "knowledge-2", "事实漂移",
             f"由于「{ref}」{mutable}，一代人确认的“事实”到下一代可能已被重新解释。",
             "可变性", ["consequence-1"]),
            ("institution", "institution-1", "裁决机构",
             f"围绕「{ref}」出现以{enf}方式运作的裁决机构，负责裁定何为有效接触与有效证据。",
             "执行方式", ["consequence-2"]),
            ("institution", "institution-2", "准入制度",
             f"稀缺性{scarce}使准入资格成为制度核心：登记、配额与继承规则由此而来。",
             "稀缺性", ["institution-1"]),
            ("history", "history-1", "边界移动",
             f"历史由观测条件变化驱动：每当可观测性{obs}的边界移动，就出现一次重估与冲突。",
             "可观测性", ["institution-1"]),
            ("history", "history-2", "周期清算",
             f"由于「{ref}」{mutable}，每次官方解释都被后来者当作压迫或启示，历史周期性地被清算。",
             "可变性", ["knowledge-2"]),
            ("geography", "geography-1", "成本梯度",
             f"接近成本{cost}，人口与产业沿成本梯度分布，形成中心—边缘结构。",
             "代价", ["history-1"]),
            ("geography", "geography-2", "管控分层",
             f"稀缺性{scarce}且以{enf}方式执行，使管控按距离分层：越接近源头越受规制。",
             "稀缺性+执行方式", ["institution-1"]),
            ("conflict", "conflict-1", "零和解释权",
             f"由于稀缺性{scarce}，解释权是零和的：一方获益意味着另一方失去接近的可能。",
             "稀缺性", ["geography-1"]),
            ("conflict", "conflict-2", "真假之争",
             f"可观测性{obs}制造了天然的骗子与真先知，证词无法区分，冲突难以调和。",
             "可观测性", ["knowledge-2"]),
        ]
        entities: List[WorldEntity] = []
        for kind, eid, name, statement, prop, parents in spec:
            entities.append(WorldEntity(
                kind=kind, id=eid, name=name, statement=statement, state="candidate",
                source="derived", basis=f"由{prop} 推导", depends_on=list(parents)))
        words = [w for w in (terms(doc.seed, limit=5) or ["沉默"]) if w != ref][:3] or ["沉默"]
        for j, word in enumerate(words, start=1):
            entities.append(WorldEntity(
                kind="motif", id=f"motif-{j}", name=f"意象：{word}",
                statement=f"「{word}」反复出现，每次出现都标记「{ref}」可观测性边界的移动。",
                state="candidate", source="derived", basis="由片语意象提取",
                depends_on=["conflict-2"]))
        questions = [
            f"「{ref}」是可测量的，还是只能被经验？",
            f"违背「{ref}」的代价由谁承担、如何判定？",
            f"谁最先发现了「{ref}」，那个人后来发生了什么？",
        ]
        return entities, questions

    def _from_llm(self, doc: WorldDoc, rule: str, analysis: Dict[str, dict], rule_id: str):
        prompt = (
            "根据核心规则及其属性，逐层推导自洽的世界，并给出条目间的依赖关系。\n"
            f"核心规则：{rule}\n"
            f"规则属性：{ {k: v['value'] for k, v in analysis.items()} }\n"
            f"原始片语：{doc.seed}\n"
            f"kind 只能取：{', '.join(KINDS)}。每条都要有 name、statement、basis、depends_on（父条目 id）。\n"
            '只输出 JSON：{"entities":[{"id":"","kind":"consequence","name":"","statement":"",'
            '"basis":"","depends_on":[""]}],"open_questions":[""]}'
        )
        data = generate_json(self.llm, prompt, max_tokens=2500)
        if not data or not isinstance(data.get("entities"), list):
            return None
        entities: List[WorldEntity] = []
        dropped = 0
        seen: Dict[str, int] = {}
        for item in data["entities"]:
            entity = _valid_entity(item, rule_id, seen)
            if entity is None:
                dropped += 1
                continue
            entities.append(entity)
        if dropped:
            doc.notes.append(f"模型返回的 {dropped} 条设定字段不完整或类别非法，已忽略。")
        if not entities:
            doc.notes.append("模型未返回可用设定，已回退到离线推导。")
            return None
        if not any(e.kind in ("consequence", "institution", "history") for e in entities):
            doc.notes.append("模型返回缺少关键类别（后果/制度/历史），已回退到离线推导。")
            return None
        questions = [str(q) for q in data.get("open_questions", []) if str(q).strip()]
        return entities, questions


def _valid_entity(item: object, rule_id: str, seen: Dict[str, int]) -> Optional[WorldEntity]:
    if not isinstance(item, dict):
        return None
    kind = str(item.get("kind") or "")
    statement = str(item.get("statement") or "").strip()
    if kind not in KINDS or not statement:
        return None
    seen[kind] = seen.get(kind, 0) + 1
    name = str(item.get("name") or "").strip() or f"{KIND_LABELS.get(kind, kind)}{seen[kind]}"
    parents = [str(p) for p in item.get("depends_on", []) if str(p).strip()] or [rule_id]
    return WorldEntity(
        id=str(item.get("id") or f"{kind}-{seen[kind]}"), kind=kind, name=name,
        statement=statement, state="candidate", source="derived",
        basis=str(item.get("basis") or ""), depends_on=parents)


def rule_property_analysis(seed: str, rule: str) -> Dict[str, Dict[str, str]]:
    """Infer rule properties with explicit evidence/confidence; allow *unknown*.

    Keyword hits are checked for negation and scope, so "人人都能看见" and
    "不需要付出代价" are not misread.
    """
    text = (rule or seed or "").strip()

    def hit(kws: Tuple[str, ...]) -> Optional[Tuple[int, str]]:
        best: Optional[Tuple[int, str]] = None
        for kw in kws:
            idx = text.find(kw)
            if idx != -1 and (best is None or idx < best[0]):
                best = (idx, kw)
        return best

    def negated(idx: int) -> bool:
        return any(n in text[max(0, idx - 6):idx] for n in _NEGATION)

    def scoped_high(idx: int) -> bool:
        return any(s in text[max(0, idx - 4):idx + 4] for s in _OBS_SCOPE_HIGH)

    def decide(pos=(), neg=(), pos_value="", neg_value="", unknown_note="无明显依据"):
        p = hit(tuple(pos))
        n = hit(tuple(neg))
        if p is not None and n is not None:
            return (p, pos_value) if p[0] < n[0] else (n, neg_value)
        if p is not None:
            return p, pos_value
        if n is not None:
            return n, neg_value
        return None, _UNKNOWN

    result: Dict[str, Dict[str, str]] = {}
    found, value = decide(_OBS_KW, (), "低", "")
    if found is not None:
        idx = found[0]
        if negated(idx) or scoped_high(idx):
            value = "高"
        result["observability"] = _entry(value, found[1], "中")
    else:
        result["observability"] = _entry(_UNKNOWN, "未出现可观测性相关表述", "低")

    found, value = decide(_SCARCE_KW, _ABUNDANT_KW, "稀缺", "充足")
    result["scarcity"] = _entry(value, found[1] if found else "未出现稀缺性相关表述",
                                "中" if found else "低")

    found, value = decide(_CODIFIED_KW, _CUSTOM_KW, "成文法", "习惯法")
    result["enforcement"] = _entry(value, found[1] if found else "未出现执行方式相关表述",
                                   "中" if found else "低")

    found, value = decide(_COSTLY_KW, _CHEAP_KW, "高昂", "可承受")
    if found is not None and negated(found[0]):
        value = "可承受"
    result["cost"] = _entry(value, found[1] if found else "未出现代价相关表述",
                            "中" if found else "低")

    found, value = decide(_IMMUTABLE_KW, _MUTABLE_KW, "被视为不可变", "会漂移")
    result["mutability"] = _entry(value, found[1] if found else "未出现可变性相关表述",
                                  "中" if found else "低")
    return result


def rule_properties(seed: str, rule: str) -> Dict[str, str]:
    """Value-only view of :func:`rule_property_analysis` (kept for callers/export)."""
    return {k: v["value"] for k, v in rule_property_analysis(seed, rule).items()}


def _entry(value: str, evidence: str, confidence: str) -> Dict[str, str]:
    return {"value": value, "evidence": f"命中「{evidence}」" if evidence else "无明显依据",
            "confidence": confidence}


def _disp(value: str) -> str:
    return _DISPLAY.get(value, value)


def _short_ref(seed: str, rule: str) -> str:
    parts = clauses(seed)
    if parts and 2 <= len(parts[0]) <= 24:
        return parts[0]
    return rule if len(rule) <= 24 else rule[:24]
