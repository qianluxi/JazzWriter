"""World Studio: divergence analysis, rule-driven growth, dependency graph,
checker, graft diff and Markdown export."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from world import emit
from world.checker import WorldChecker
from world.expander import WorldExpander, rule_properties
from world.graft import GraftEngine
from world.graph import DependencyGraph
from world.idea_forge import DIMENSIONS, IdeaForge
from world.models import WorldDoc, WorldEntity, WorldIdea
from world.studio import WorldStudio

SEED = "每个人死后都会留下一段从未说出口的记忆，但只有建筑能听见"


class IdeaForgeTest(unittest.TestCase):
    def test_offline_ideas_carry_dimensions(self):
        ideas = IdeaForge().ideas(SEED, count=4)
        self.assertGreaterEqual(len(ideas), 3)
        self.assertGreaterEqual(len({i.lens for i in ideas}), 3)
        for idea in ideas:
            self.assertEqual(set(idea.dimensions), set(DIMENSIONS))
            self.assertTrue(all(idea.dimensions[d] for d in DIMENSIONS))
            self.assertTrue(0.0 <= idea.distinctness <= 1.0)

    def test_identical_mechanisms_are_flagged(self):
        forge = IdeaForge()
        dims = {d: "同一套机制描述" for d in DIMENSIONS}
        a = WorldIdea(id="idea-1", label="甲", lens="认知", dimensions=dict(dims))
        b = WorldIdea(id="idea-2", label="乙", lens="制度", dimensions=dict(dims))
        forge.analyze([a, b])
        self.assertTrue(a.near_duplicate or b.near_duplicate)
        self.assertTrue(forge.duplicate_warnings([a, b]))

    def test_count_is_bounded(self):
        self.assertGreaterEqual(len(IdeaForge().ideas("种子", count=99)), 3)


class ExpanderTest(unittest.TestCase):
    def _doc(self, rule: str = "围绕「记忆」形成了可执行、可争讼、可世袭的执法体系。") -> WorldDoc:
        doc = WorldDoc(title="t", seed=SEED)
        doc.chosen_idea = WorldIdea(id="idea-1", label="制度世界", lens="制度", core_rule=rule)
        return doc

    def test_grows_all_layers_from_rule_properties(self):
        doc = WorldExpander().expand(self._doc())
        self.assertEqual(len(doc.of_kind("rule")), 1)
        self.assertEqual(doc.of_kind("rule")[0].state, "confirmed")
        self.assertTrue(doc.rule_properties)
        for kind in ("consequence", "knowledge", "institution", "history",
                     "geography", "conflict", "motif"):
            self.assertTrue(doc.of_kind(kind), kind)
        derived = [e for e in doc.entities if e.kind != "rule"]
        self.assertTrue(all("rule-1" in e.depends_on for e in derived))
        self.assertTrue(all(e.basis for e in derived))
        self.assertTrue(doc.open_questions)

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


class DependencyGraphTest(unittest.TestCase):
    def test_impact_of_rule_lists_derived_entries(self):
        doc = WorldExpander().expand(ExpanderTest()._doc())
        graph = DependencyGraph(doc)
        impacted = graph.impacted_by("rule-1")
        self.assertGreater(len(impacted), 3)
        report = graph.impact_report("rule-1")
        self.assertTrue(report["transitive"])
        self.assertTrue(report["candidates"])


class CheckerTest(unittest.TestCase):
    def test_flags_conflict_with_basis_and_confidence(self):
        doc = WorldDoc(title="t", seed="x")
        doc.add(WorldEntity(id="institution-1", kind="institution", name="教团",
                            statement="教团垄断对秩序的觉察", state="confirmed"))
        doc.add(WorldEntity(id="consequence-1", kind="consequence", name="异端",
                            statement="异端否认并能觉察秩序的反面", state="candidate"))
        doc.add(WorldEntity(id="consequence-2", kind="consequence", name="裂缝",
                            statement="秩序并不存在", state="contradiction"))
        issues = WorldChecker().check(doc)
        warns = [i for i in issues if i["level"] == "warn"]
        notes = [i for i in issues if i["level"] == "note"]
        self.assertTrue(warns)
        self.assertTrue(all("basis" in i and "confidence" in i for i in warns))
        self.assertTrue(notes)
        self.assertTrue(any("跨类别" in i["basis"] for i in warns))


class GraftTest(unittest.TestCase):
    SRC = ("本世界的核心规则：记忆只能被建筑听见。历史上曾发生一场记忆灾变。"
           "权力由教会垄断。作品的主题是孤独与见证。建筑风格巨大而沉默。")

    def test_extract_skeleton(self):
        skel = GraftEngine().extract(self.SRC, source_name="样例")
        self.assertTrue(skel.rules)
        self.assertIn("记忆", skel.primary_rule())

    def test_reverse_premise_emits_structured_diff(self):
        engine = GraftEngine()
        skel = engine.extract(self.SRC, source_name="样例")
        doc, notes = engine.transform(skel, "反转前提", "一个没有夜晚的城市")
        self.assertEqual(set(doc.graft_diff), {"inherit", "remove", "modify", "add", "downstream"})
        self.assertTrue(doc.graft_diff["remove"])
        self.assertTrue(doc.graft_diff["add"])
        self.assertTrue(doc.graft_diff["downstream"])
        self.assertTrue(doc.contradictions)
        added = [e for e in doc.of_kind("rule") if e.id != "rule-1"]
        self.assertTrue(added)
        self.assertTrue(all(e.state == "candidate" for e in added))
        text = emit.build_markdown(doc)
        self.assertIn("嫁接变形记录", text)
        self.assertIn("下游影响", text)

    def test_cross_marks_two_sources(self):
        engine = GraftEngine()
        a = engine.extract(self.SRC, source_name="A")
        b = engine.extract("世界规则是：潮汐决定一切。", source_name="B")
        doc, notes = engine.transform(a, "世界交叉", "潮汐与记忆", second=b)
        self.assertTrue(doc.contradictions)
        self.assertTrue(any("交叉来源" in n for n in notes))


class StudioTest(unittest.TestCase):
    def test_end_to_end_state_lock_and_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            studio = WorldStudio.create(SEED, root=Path(tmp), provider="mock")
            studio.raise_ideas(count=4)
            studio.choose("制度世界")
            studio.grow()
            path = studio.export()
            for needle in ("## 核心规则", "## 规则属性（推导起点）", "## 规则依赖与影响",
                           "## 未决问题", "由 World Studio 生成"):
                self.assertIn(needle, path.read_text(encoding="utf-8"))
            studio.set_state("consequence-1", "confirmed")
            studio.lock("rule-1")
            studio.save()
            reloaded = WorldStudio.load(studio.slug, root=Path(tmp))
            self.assertEqual(reloaded.doc.by_id("consequence-1").state, "confirmed")
            self.assertTrue(reloaded.doc.by_id("rule-1").locked)
            self.assertEqual(reloaded.impact("rule-1")["transitive"] != [], True)

    def test_grow_requires_a_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            studio = WorldStudio.create(SEED, root=Path(tmp), provider="mock")
            studio.raise_ideas()
            with self.assertRaises(ValueError):
                studio.grow()


if __name__ == "__main__":
    unittest.main()
