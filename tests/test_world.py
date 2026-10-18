"""World Studio: divergence analysis, rule-driven growth, dependency graph,
checker, graft plans, path safety, model fallback and Markdown export."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from world import emit
from world.checker import WorldChecker
from world.expander import WorldExpander, rule_property_analysis, rule_properties
from world.graft import GraftEngine
from world.graph import DependencyGraph
from world.idea_forge import DIMENSIONS, IdeaForge
from world.models import WorldDoc, WorldEntity, WorldIdea
from world.studio import WorldStudio

SEED = "每个人死后都会留下一段从未说出口的记忆，但只有建筑能听见"
SRC = ("本世界的核心规则：记忆只能被建筑听见。历史上曾发生一场记忆灾变。"
       "权力由教会垄断。作品的主题是孤独与见证。建筑风格巨大而沉默。")


class _StubLLM:
    name = "fake"

    def __init__(self, payload: str) -> None:
        self.payload = payload

    def generate(self, prompt, *, system=None, context=None, temperature=0.9, max_tokens=1500):
        return self.payload


class IdeaForgeTest(unittest.TestCase):
    def test_offline_ideas_carry_dimensions(self):
        ideas = IdeaForge().ideas(SEED, count=4)
        self.assertGreaterEqual(len(ideas), 3)
        for idea in ideas:
            self.assertEqual(set(idea.dimensions), set(DIMENSIONS))
            self.assertTrue(0.0 <= idea.distinctness <= 1.0)

    def test_identical_mechanisms_are_flagged(self):
        forge = IdeaForge()
        dims = {d: "同一套机制描述" for d in DIMENSIONS}
        a = WorldIdea(id="idea-1", label="甲", lens="认知", dimensions=dict(dims))
        b = WorldIdea(id="idea-2", label="乙", lens="制度", dimensions=dict(dims))
        forge.analyze([a, b])
        self.assertTrue(a.near_duplicate or b.near_duplicate)


class PropertyAnalysisTest(unittest.TestCase):
    def test_negation_and_scope(self):
        high = rule_property_analysis("", "人人都能看见这条规则。")
        self.assertEqual(high["observability"]["value"], "高")
        cheap = rule_property_analysis("", "接触它不需要付出代价。")
        self.assertEqual(cheap["cost"]["value"], "可承受")

    def test_unknown_when_no_evidence(self):
        analysis = rule_property_analysis("", "世界遵循某种难以言说的秩序。")
        self.assertEqual(analysis["scarcity"]["value"], "未知")
        self.assertEqual(analysis["scarcity"]["confidence"], "低")

    def test_value_only_view(self):
        self.assertEqual(set(rule_properties("", "法律禁止它。")),
                         {"observability", "scarcity", "enforcement", "cost", "mutability"})


class ExpanderTest(unittest.TestCase):
    def _doc(self, rule: str = "围绕「记忆」形成了可执行、可争讼、可世袭的执法体系。") -> WorldDoc:
        doc = WorldDoc(title="t", seed=SEED)
        doc.chosen_idea = WorldIdea(id="idea-1", label="制度世界", lens="制度", core_rule=rule)
        return doc

    def test_grows_multilevel_chain(self):
        doc = WorldExpander().expand(self._doc())
        self.assertEqual(len(doc.of_kind("rule")), 1)
        self.assertEqual(doc.of_kind("rule")[0].state, "confirmed")
        self.assertTrue(doc.rule_properties)
        for kind in ("consequence", "knowledge", "institution", "history",
                     "geography", "conflict", "motif"):
            self.assertTrue(doc.of_kind(kind), kind)
        graph = DependencyGraph(doc)
        reachable = set(graph.impacted_by("rule-1"))
        derived = [e for e in doc.entities if e.kind != "rule"]
        self.assertTrue(all(e.id in reachable for e in derived))
        self.assertTrue(all(e.basis for e in derived))
        # not a star: some entry must depend on another entry, not only the rule
        self.assertTrue(any(e.depends_on != ["rule-1"] for e in derived))

    def test_different_rules_give_different_worlds(self):
        a = WorldExpander().expand(self._doc("「记忆」只有少数人能听见，代价高昂。"))
        b = WorldExpander().expand(self._doc("「记忆」写入法律，人人可见。"))
        self.assertNotEqual(a.rule_properties, b.rule_properties)
        self.assertNotEqual(a.of_kind("consequence")[0].statement,
                            b.of_kind("consequence")[0].statement)

    def test_expand_is_idempotent(self):
        doc = WorldExpander().expand(self._doc())
        before = len(doc.entities)
        WorldExpander().expand(doc)
        self.assertEqual(len(doc.entities), before)

    def test_malformed_model_output_falls_back_with_note(self):
        bad = _StubLLM('{"entities": [{"kind": "nonsense", "name": "x"}]}')
        doc = self._doc()
        WorldExpander(llm=bad).expand(doc)
        self.assertTrue(doc.of_kind("consequence"))          # offline fallback happened
        self.assertTrue(any("忽略" in n or "回退" in n for n in doc.notes))

    def test_valid_model_output_is_used(self):
        good = _StubLLM(json.dumps({"entities": [
            {"id": "consequence-1", "kind": "consequence", "name": "模型后果",
             "statement": "模型推导出的后果。", "basis": "模型", "depends_on": ["rule-1"]},
            {"id": "institution-1", "kind": "institution", "name": "模型制度",
             "statement": "模型推导出的制度。"},
        ], "open_questions": ["模型问题？"]}))
        doc = self._doc()
        WorldExpander(llm=good).expand(doc)
        self.assertIn("模型问题？", doc.open_questions)
        self.assertEqual(doc.of_kind("consequence")[0].name, "模型后果")


class CheckerTest(unittest.TestCase):
    def test_flags_conflict_with_basis_and_confidence(self):
        doc = WorldDoc(title="t", seed="x")
        doc.add(WorldEntity(id="institution-1", kind="institution", name="教团",
                            statement="教团垄断对秩序的觉察", state="confirmed"))
        doc.add(WorldEntity(id="consequence-1", kind="consequence", name="异端",
                            statement="异端否认并能觉察秩序的反面", state="candidate"))
        issues = WorldChecker().check(doc)
        warns = [i for i in issues if i["level"] == "warn"]
        self.assertTrue(warns)
        self.assertTrue(all("basis" in i and "confidence" in i for i in warns))

    def test_detects_rule_violation(self):
        doc = WorldDoc(title="t", seed="x")
        doc.add(WorldEntity(id="rule-1", kind="rule", name="核心规则",
                            statement="记忆必须被公开。", state="confirmed"))
        doc.add(WorldEntity(id="consequence-1", kind="consequence", name="例外",
                            statement="记忆永远不被公开。", state="candidate"))
        issues = WorldChecker().check(doc)
        self.assertTrue(any(set(i["ids"]) == {"rule-1", "consequence-1"} and i["level"] == "warn"
                            for i in issues))

    def test_offline_mode_reports_it_cannot_judge_semantics(self):
        doc = WorldDoc(title="t", seed="x")
        doc.add(WorldEntity(id="rule-1", kind="rule", name="核心规则", statement="某规则。"))
        issues = WorldChecker().check(doc, llm=None)
        self.assertTrue(any("离线模式" in i["message"] for i in issues))


class GraftTest(unittest.TestCase):
    def test_reverse_premise_emits_structured_diff(self):
        engine = GraftEngine()
        skel = engine.extract(SRC, source_name="样例")
        doc, notes = engine.transform(skel, "反转前提", "一个没有夜晚的城市")
        self.assertEqual(set(doc.graft_diff), {"inherit", "remove", "modify", "add", "downstream"})
        self.assertTrue(doc.graft_diff["remove"])
        self.assertTrue(doc.graft_diff["add"])
        self.assertTrue(doc.graft_diff["downstream"])
        self.assertTrue(doc.contradictions)
        self.assertTrue(doc.graft_plan)
        added = [e for e in doc.of_kind("rule") if e.id != "rule-1"]
        self.assertTrue(all(e.state == "candidate" for e in added))

    def test_operators_produce_different_rules(self):
        engine = GraftEngine()
        skel = engine.extract(SRC, source_name="样例")
        rules = {}
        for op in ("深度变形", "边缘扩展", "反转前提"):
            doc, _ = engine.transform(skel, op, "一个没有夜晚的城市")
            rules[op] = doc.of_kind("rule")[0].statement
        self.assertEqual(len(set(rules.values())), 3)

    def test_cross_requires_second_material(self):
        engine = GraftEngine()
        skel = engine.extract(SRC, source_name="样例")
        with self.assertRaises(ValueError):
            engine.transform(skel, "世界交叉", "潮汐")

    def test_cross_marks_two_sources(self):
        engine = GraftEngine()
        a = engine.extract(SRC, source_name="A")
        b = engine.extract("世界规则是：潮汐决定一切。", source_name="B")
        doc, notes = engine.transform(a, "世界交叉", "潮汐与记忆", second=b)
        self.assertTrue(doc.contradictions)
        self.assertTrue(any("交叉来源" in n for n in notes))


class StudioTest(unittest.TestCase):
    def test_pick_then_grow_closure_survives_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            studio = WorldStudio.create(SEED, root=Path(tmp), provider="mock")
            studio.raise_ideas(count=4)
            studio.save()
            resumed = WorldStudio.load(studio.slug, root=Path(tmp))
            self.assertEqual(len(resumed.doc.ideas), len(studio.doc.ideas))  # prototypes restored
            with self.assertRaises(ValueError):
                resumed.grow()                                  # no silent default
            target = resumed.doc.ideas[1]
            resumed.choose(target.id)
            resumed.grow()
            resumed.export()
            again = WorldStudio.load(studio.slug, root=Path(tmp))
            self.assertEqual(again.doc.chosen_idea.id, target.id)

    def test_graft_new_does_not_touch_source_world(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = WorldStudio.create(SEED, root=Path(tmp), provider="mock")
            source.raise_ideas()
            source.export()
            before = source.json_path.read_text(encoding="utf-8")
            derived = WorldStudio.graft_new(SEED, SRC, "深度变形", root=Path(tmp), provider="mock")
            self.assertNotEqual(source.slug, derived.slug)
            self.assertEqual(source.json_path.read_text(encoding="utf-8"), before)

    def test_rejects_traversal_slug(self):
        with tempfile.TemporaryDirectory() as tmp:
            for bad in ("../evil", "a/b", "..", ""):
                with self.assertRaises(ValueError):
                    WorldStudio.load(bad, root=Path(tmp))
            studio = WorldStudio(SEED, slug="../x", root=Path(tmp), provider="mock")
            with self.assertRaises(ValueError):
                _ = studio.data_dir

    def test_markdown_marks_locked_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            studio = WorldStudio.create(SEED, root=Path(tmp), provider="mock")
            studio.raise_ideas()
            studio.choose("制度世界")
            studio.grow()
            studio.lock("consequence-1")
            path = studio.export()
            text = path.read_text(encoding="utf-8")
            self.assertIn("🔒已锁定", text)
            self.assertIn("## 锁定条目", text)


if __name__ == "__main__":
    unittest.main()
