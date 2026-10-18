"""World Expander: grow one chosen prototype into a layered worldview.

Offline growth is a **derivation**: the rule's structural properties are inferred
with explicit evidence/confidence (allowing *unknown*), then a causal chain is
built and **composable mechanism modules** are switched on by those properties,
so different rules yield different structures, not just different wording.

When a graft *plan* is supplied it is passed into the model prompt as an explicit
constraint and verified afterwards; if the output does not satisfy the plan, the
expander falls back to the offline derivation instead of appending a note.

Model output is validated strictly (kind whitelist, minimum category coverage,
id uniqueness, depends_on type/reference integrity, acyclicity).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from engine.planning_llm import generate_json
from world.models import KINDS, KIND_LABELS, PROPERTY_LABELS, WorldDoc, WorldEntity
from world.util import clauses, terms

_UNKNOWN = "未知"
MIN_KINDS = ("consequence", "institution", "history")

_OBS_KW = ("听见", "看见", "感知", "显形", "洞察", "读取", "测量", "观测")
_OBS_SCOPE_HIGH = ("人人", "所有人", "任何人", "普遍", "都能", "都可", "都可以", "公开")
_SCARCE_KW = ("只有", "唯一", "少数", "稀缺", "垄断", "独占", "极少", "罕见")
_ABUNDANT_KW = ("充足", "普遍", "丰富", "人人都有", "随处可见")
_SCARCE_PHRASE = ("并非人人", "不是人人", "并非所有", "只有部分")
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

        picked = self._from_llm(doc, rule, analysis, rule_id, plan)
        if picked is not None and plan:
            gaps = _plan_gaps(picked[0], plan)
            if gaps:
                doc.notes.append("模型输出未完全体现嫁接计划（供作者确认）：" + "；".join(gaps))
        if picked is None:
            picked = self._derive(doc, rule, analysis, rule_id, plan)
        entities, questions = picked
        self._merge(doc, entities)
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
    def _merge(doc: WorldDoc, entities: List[WorldEntity]) -> None:
        for entity in entities:
            if doc.by_id(entity.id):
                doc.notes.append(f"条目 id 重复，已跳过：{entity.id}")
                continue
            doc.add(entity)

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

    # -- deterministic derivation with composable modules --------------------
    def _derive(self, doc: WorldDoc, rule: str, analysis: Dict[str, dict], rule_id: str,
                plan: Optional[dict] = None
                ) -> Tuple[List[WorldEntity], List[str]]:
        # Graft keeps a source rule unrelated to the seed: reference the rule's
        # subject, not the seed, so entries do not talk about the wrong thing.
        prefer_rule = bool(plan and plan.get("keep"))
        ref = _subject_ref(rule, doc.seed) if prefer_rule else _short_ref(doc.seed, rule)
        value = {k: a["value"] for k, a in analysis.items()}
        obs, scarce = _disp(value["observability"]), _disp(value["scarcity"])
        enf, cost, mutable = _disp(value["enforcement"]), _disp(value["cost"]), _disp(value["mutability"])
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
        spec.extend(_modules(value, ref))
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

    # -- model path ----------------------------------------------------------
    def _from_llm(self, doc: WorldDoc, rule: str, analysis: Dict[str, dict],
                  rule_id: str, plan: Optional[dict]):
        plan_text = _plan_brief(plan) if plan else "（无嫁接计划）"
        prompt = (
            "根据核心规则、规则属性与（若有）嫁接变形计划，逐层推导自洽的世界，并给出条目间依赖。\n"
            f"核心规则：{rule}\n"
            f"规则属性：{ {k: v['value'] for k, v in analysis.items()} }\n"
            f"原始片语：{doc.seed}\n"
            f"嫁接变形计划（必须遵循，不得只写在说明里）：\n{plan_text}\n"
            f"kind 只能取：{', '.join(KINDS)}；至少覆盖 {', '.join(MIN_KINDS)}。\n"
            "每条需有 唯一 id、kind、name、statement、basis、depends_on（父条目 id 列表，"
            f"父 id 必须来自本响应或 \"{rule_id}\"）。\n"
            '只输出 JSON：{"entities":[{"id":"","kind":"consequence","name":"","statement":"",'
            '"basis":"","depends_on":[""]}],"open_questions":[""]}'
        )
        data = generate_json(self.llm, prompt, max_tokens=2600)
        if not data or not isinstance(data.get("entities"), list):
            return None
        entities = _validated_entities(doc, data["entities"], rule_id)
        if not entities:
            doc.notes.append("模型未返回可用设定，已回退到离线推导。")
            return None
        kinds = {e.kind for e in entities}
        if not set(MIN_KINDS) <= kinds:
            missing = "、".join(k for k in MIN_KINDS if k not in kinds)
            doc.notes.append(f"模型返回缺少关键类别（{missing}），已回退到离线推导。")
            return None
        questions = [str(q) for q in data.get("open_questions", []) if str(q).strip()]
        return entities, questions


def _validated_entities(doc: WorldDoc, raw: List[object], rule_id: str) -> List[WorldEntity]:
    """Strict schema + reference integrity. Returns valid entities (notes recorded)."""
    prepared: List[WorldEntity] = []
    used: Set[str] = set()
    dropped = 0
    renamed = 0
    for item in raw:
        if not isinstance(item, dict):
            dropped += 1
            continue
        kind = str(item.get("kind") or "")
        statement = str(item.get("statement") or "").strip()
        if kind not in KINDS or not statement:
            dropped += 1
            continue
        base_id = str(item.get("id") or "").strip()
        if not base_id or base_id in used or base_id == rule_id:
            base_id = f"{kind}-{len([e for e in prepared if e.kind == kind]) + 1}"
            renamed += 1
            while base_id in used:
                base_id = base_id + "-dup"
        used.add(base_id)
        name = str(item.get("name") or "").strip() or f"{KIND_LABELS.get(kind, kind)}"
        prepared.append(WorldEntity(
            id=base_id, kind=kind, name=name, statement=statement, state="candidate",
            source="derived", basis=str(item.get("basis") or ""),
            depends_on=_parents(item.get("depends_on"), rule_id)))

    known = {e.id for e in prepared} | {rule_id}
    for entity in prepared:
        valid = [p for p in entity.depends_on if p in known]
        if len(valid) != len(entity.depends_on):
            dropped_refs = [p for p in entity.depends_on if p not in known]
            for ref in dropped_refs:
                if f"无效依赖引用已忽略：{ref}" not in doc.notes:
                    doc.notes.append(f"无效依赖引用已忽略：{ref}")
            entity.depends_on = valid or [rule_id]
    _break_cycles(prepared, doc)
    if dropped:
        doc.notes.append(f"模型返回的 {dropped} 条设定字段不完整或类别非法，已忽略。")
    if renamed:
        doc.notes.append(f"模型返回的 {renamed} 条设定 id 缺失或重复，已重新编号。")
    return prepared


def _parents(value: object, rule_id: str) -> List[str]:
    if isinstance(value, list):
        parents = [str(v).strip() for v in value if str(v).strip()]
        return parents or [rule_id]
    if isinstance(value, str) and value.strip():     # a bare string must not be split per char
        return [value.strip()]
    return [rule_id]


def _break_cycles(entities: List[WorldEntity], doc: WorldDoc) -> None:
    ids = {e.id for e in entities}
    adj = {e.id: [p for p in e.depends_on if p in ids] for e in entities}
    color: Dict[str, int] = {}
    removed = False

    def dfs(node: str) -> None:
        nonlocal removed
        color[node] = 1
        for parent in list(adj[node]):
            if color.get(parent) == 1:
                adj[node].remove(parent)
                removed = True
            elif color.get(parent, 0) == 0:
                dfs(parent)
        color[node] = 2

    for entity in entities:
        if color.get(entity.id, 0) == 0:
            dfs(entity.id)
    if removed:
        for entity in entities:
            entity.depends_on = [p for p in entity.depends_on
                                 if p not in ids or p in adj[entity.id]]
        if "检测到循环依赖，已断开部分引用。" not in doc.notes:
            doc.notes.append("检测到循环依赖，已断开部分引用。")


def _plan_gaps(entities: List[WorldEntity], plan: dict) -> List[str]:
    """Non-blocking check: report plan aspects the model did not reflect.

    Word-level matching is too brittle to *reject* model output, so this only
    produces author-facing notes; the output is kept.
    """
    text = " ".join(e.statement + " " + e.basis for e in entities)
    gaps = []
    for key, value in (plan.get("properties") or {}).items():
        if value != _UNKNOWN and str(value) not in text:
            gaps.append(f"属性「{PROPERTY_LABELS.get(key, key)}」未明显体现（期望 {value}）")
    return gaps


def _plan_brief(plan: Optional[dict]) -> str:
    if not plan:
        return ""
    lines = [f"操作：{plan.get('op', '')}",
             f"保留：{'；'.join(str(x) for x in plan.get('keep', [])) or '（无）'}"]
    if plan.get("remove"):
        lines.append(f"删除：{'；'.join(str(x) for x in plan['remove'])}")
    if plan.get("properties"):
        lines.append("属性位移：" + "；".join(f"{k}→{v}" for k, v in plan["properties"].items()))
    if plan.get("extra_rules"):
        lines.append("必须推导出的新增规则：" + "；".join(str(x) for x in plan["extra_rules"]))
    if plan.get("expected"):
        lines.append(f"预期影响：{plan['expected']}")
    return "\n".join(lines)


# -- property analysis ---------------------------------------------------------
def _hit(text: str, kws: Tuple[str, ...]) -> Optional[Tuple[int, str]]:
    best: Optional[Tuple[int, str]] = None
    for kw in kws:
        idx = text.find(kw)
        if idx != -1 and (best is None or idx < best[0]):
            best = (idx, kw)
    return best


def _negated(text: str, idx: int, window: int = 6) -> bool:
    return any(n in text[max(0, idx - window):idx] for n in _NEGATION)


def rule_property_analysis(seed: str, rule: str) -> Dict[str, Dict[str, str]]:
    """Infer rule properties with evidence/confidence; allow *unknown*.

    Explicit per-dimension rules (positive / negative / scope / unknown) instead
    of inverting a lone keyword: e.g. "记忆不会被建筑看见" is *low* observability,
    "这种能力并不稀缺" is *abundant*.
    """
    text = (rule or seed or "").strip()
    out: Dict[str, Dict[str, str]] = {}

    # observability: a perception verb means low; a scope word means high; a
    # negated perception verb still means low (never flip to high).
    obs = _hit(text, _OBS_KW)
    scope = _hit(text, _OBS_SCOPE_HIGH)
    if obs or scope:
        idx, kw = (scope if (scope and (not obs or scope[0] <= obs[0])) else obs)  # earliest
        high = (kw in _OBS_SCOPE_HIGH) and not _negated(text, idx)
        out["observability"] = _entry("高" if high else "低", kw, "中")
    else:
        out["observability"] = _entry(_UNKNOWN, "未出现可观测性相关表述", "低")

    out["scarcity"] = _flip(text, [(_SCARCE_KW, "稀缺"), (_ABUNDANT_KW, "充足")],
                            {"稀缺": "充足", "充足": "稀缺"}, _SCARCE_PHRASE)
    out["enforcement"] = _flip(text, [(_CODIFIED_KW, "成文法"), (_CUSTOM_KW, "习惯法")],
                               {"成文法": "习惯法", "习惯法": "成文法"})
    out["cost"] = _flip(text, [(_COSTLY_KW, "高昂"), (_CHEAP_KW, "可承受")],
                        {"高昂": "可承受", "可承受": "高昂"})
    out["mutability"] = _flip(text, [(_IMMUTABLE_KW, "被视为不可变"), (_MUTABLE_KW, "会漂移")],
                              {"被视为不可变": "会漂移", "会漂移": "被视为不可变"})
    return out


def _flip(text: str, groups, opposite: Dict[str, str], phrases: Tuple[str, ...] = ()) -> Dict[str, str]:
    hits: List[Tuple[int, str, str]] = []
    for kws, value in groups:
        found = _hit(text, kws)
        if found:
            hits.append((found[0], found[1], value))
    for phrase in phrases:
        idx = text.find(phrase)
        if idx != -1:
            hits.append((idx, phrase, "稀缺"))
    if not hits:
        return _entry(_UNKNOWN, "未出现相关表述", "低")
    idx, kw, value = min(hits, key=lambda t: t[0])
    if _negated(text, idx):
        value = opposite.get(value, value)
    return _entry(value, kw, "中")


def _entry(value: str, evidence: str, confidence: str) -> Dict[str, str]:
    return {"value": value, "evidence": f"命中「{evidence}」" if evidence else "无明显依据",
            "confidence": confidence}


def rule_properties(seed: str, rule: str) -> Dict[str, str]:
    """Value-only view of :func:`rule_property_analysis` (kept for callers/export)."""
    return {k: v["value"] for k, v in rule_property_analysis(seed, rule).items()}


def _disp(value: str) -> str:
    return _DISPLAY.get(value, value)


def _short_ref(seed: str, rule: str) -> str:
    parts = clauses(seed)
    if parts and 2 <= len(parts[0]) <= 24:
        return parts[0]
    return rule if len(rule) <= 24 else rule[:24]


def _subject_ref(rule: str, seed: str) -> str:
    """A short subject taken from the *rule* (used when the rule is the source)."""
    text = (rule or "").strip()
    for sep in ("：", ":"):
        if sep in text:
            text = text.split(sep)[-1].strip()
    if "被" in text:
        head = text.split("被")[0].strip(" 「」")
        if 2 <= len(head) <= 20:
            return head
    parts = clauses(text)
    if parts:
        return parts[0] if len(parts[0]) <= 20 else parts[0][:20]
    return _short_ref(seed, rule)


# -- composable mechanism modules ---------------------------------------------
def _modules(value: Dict[str, str], ref: str) -> List[Tuple[str, str, str, str, str, List[str]]]:
    """Extra entries switched on by rule properties -> different rules, different
    structures (not just different fill-in values)."""
    mods: List[Tuple[str, str, str, str, str, List[str]]] = []
    if value["scarcity"] == "稀缺":
        mods += [
            ("consequence", "consequence-3", "垄断租金",
             f"稀缺性使接近权的持有者获得稳定租金，形成不事生产的寄生阶层。",
             "稀缺性", ["consequence-2"]),
            ("institution", "institution-3", "配给制度",
             "为分配稀缺的接近权，出现配额、排队与抽签制度。", "稀缺性", ["institution-2"]),
        ]
    if value["enforcement"] == "成文法":
        mods += [
            ("institution", "institution-4", "合法化仪式",
             "成文法要求以公开仪式确认规则效力，仪式本身成为权力展演。",
             "执行方式", ["institution-1"]),
            ("history", "history-3", "修法周期",
             "法律可修订，历史因此以“修法—反抗—再修法”的周期展开。",
             "执行方式", ["history-1"]),
        ]
    if value["cost"] == "高昂":
        mods += [
            ("conflict", "conflict-3", "代偿者",
             "越界代价高昂，出现专门替他人承担代价的“代偿者”这一职业。",
             "代价", ["conflict-1"]),
        ]
    if value["observability"] == "低":
        mods += [
            ("knowledge", "knowledge-3", "口述传统",
             "可观测性低，知识以口述与师徒制传递，书面记录被视为不可靠。",
             "可观测性", ["knowledge-1"]),
        ]
    if value["observability"] == "高":
        mods += [
            ("consequence", "consequence-4", "公开监督",
             "可观测性高使行为处于持续监督之下，隐私成为少数人的奢侈品。",
             "可观测性", ["consequence-1"]),
        ]
    if value["mutability"] == "会漂移":
        mods += [
            ("history", "history-4", "修正主义",
             "规则会漂移，因此每一代都出现重写历史的修正派。", "可变性", ["history-2"]),
            ("knowledge", "knowledge-4", "失传与再发现",
             "漂移导致部分知识失传，出现“考古式”的再发现运动。", "可变性", ["knowledge-2"]),
        ]
    return mods
