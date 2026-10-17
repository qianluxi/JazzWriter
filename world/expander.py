"""World Expander: grow one chosen prototype into a layered worldview.

It never rewrites the core rule. It derives consequence / knowledge /
institution / history / geography / conflict / motif layers *from* that rule,
so the world stays internally motivated instead of turning into a list of tropes.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from engine.planning_llm import generate_json
from world.models import WorldDoc, WorldEntity
from world.util import clauses, terms

_LAYERS: List[Tuple[str, List[str]]] = [
    ("consequence", [
        "「{R}」成为日常默认前提：人们规划人生时必须先绕开或利用它。",
        "围绕它的灰色地带催生了新的行当：中间人、鉴定者、赎买者。",
        "违反它的代价被公开示范，成为最有效的社会教育。",
    ]),
    ("knowledge", [
        "关于「{R}」的真相被少数机构垄断，普通人只掌握被整理过的版本。",
        "存在一批天生“感知不到”的人，他们的证词在制度中不被采信。",
    ]),
    ("institution", [
        "出现专门解释与执行「{R}」的机构，与旧权力持续争夺管辖边界。",
        "围绕它形成新的身份登记制度：谁被纳入、谁被排除在外。",
    ]),
    ("history", [
        "一场旧灾变让「{R}」第一次进入公共视野，此后所有分岔都由此而来。",
        "上一代人曾试图废除它，失败后反而把它写进了根本法。",
    ]),
    ("geography", [
        "空间按与「{R}」的距离分层：越靠近越受管控，越边缘越失控。",
        "出现只有在此处才成立的特区，与外界规则长期摩擦。",
    ]),
    ("conflict", [
        "主角因「{R}」获得优势，也因此必须向最亲近的人隐瞒它。",
        "两股势力都想独占对「{R}」的解释权，其中一方宁愿毁掉它。",
    ]),
]

_QUESTIONS = [
    "「{R}」是能被测量的，还是只能被经验？",
    "违背它的人会怎样？谁有权判定与执行？",
    "谁最先发现了它，那个人后来发生了什么？",
]


class WorldExpander:
    def __init__(self, llm=None) -> None:
        self.llm = llm

    def expand(self, doc: WorldDoc) -> WorldDoc:
        idea = doc.chosen_idea
        rule = idea.core_rule if idea else (doc.seed or "一条尚未命名的世界规则")
        self._ensure_rule(doc, rule)
        picked = self._from_llm(doc, rule)
        if picked is None:
            picked = self._from_templates(doc, rule)
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
            state="confirmed", source="chosen idea",
        ))

    def _from_templates(self, doc: WorldDoc, rule: str) -> Tuple[List[WorldEntity], List[str]]:
        ref = _short_ref(doc.seed, rule)
        R = ref
        words = [w for w in (terms(doc.seed, limit=5) or ["沉默"]) if w != ref][:3] or ["沉默"]
        entities: List[WorldEntity] = []
        for kind, statements in _LAYERS:
            for j, tmpl in enumerate(statements):
                entities.append(WorldEntity(
                    kind=kind,
                    id=f"{kind}-{j + 1}",
                    name=f"{_name_of(kind)}{j + 1}",
                    statement=tmpl.format(R=R),
                    state="candidate",
                    source="derived",
                    depends_on=["rule-1"],
                ))
        for j, word in enumerate(words[:3]):
            entities.append(WorldEntity(
                kind="motif",
                id=f"motif-{j + 1}",
                name=f"意象：{word}",
                statement=f"「{word}」反复出现，每次出现都标记「{R}」的边界在移动。",
                state="candidate",
                source="derived",
                depends_on=["rule-1"],
            ))
        questions = [q.format(R=R) for q in _QUESTIONS]
        return entities, questions

    def _from_llm(self, doc: WorldDoc, rule: str):
        prompt = (
            "根据核心规则，逐层生长出一个自洽的世界。\n"
            f"核心规则：{rule}\n"
            f"原始片语：{doc.seed}\n"
            "分层：社会后果 consequence、知识与认知 knowledge、制度与权力 institution、"
            "历史动力 history、地理与空间 geography、冲突与人物 conflict、意象与母题 motif。\n"
            '只输出 JSON：{"entities":[{"kind":"consequence","name":"","statement":""}],'
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
                kind=kind,
                id=f"{kind}-{counters[kind]}",
                name=str(item.get("name") or _name_of(kind)),
                statement=str(item.get("statement") or ""),
                state="candidate",
                source="derived",
                depends_on=["rule-1"],
            ))
        questions = [str(q) for q in data.get("open_questions", []) if str(q).strip()]
        if not entities:
            return None
        return entities, questions or [q.format(R=_short_ref(doc.seed, rule)) for q in _QUESTIONS]


def _short_ref(seed: str, rule: str) -> str:
    parts = clauses(seed)
    if parts and 2 <= len(parts[0]) <= 24:
        return parts[0]
    return rule if len(rule) <= 24 else rule[:24]


def _name_of(kind: str) -> str:
    from world.models import KIND_LABELS

    return KIND_LABELS.get(kind, kind)
