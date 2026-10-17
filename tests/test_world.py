"""World Studio: idea divergence, growth, checking, graft and Markdown export."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from world import emit
from world.checker import WorldChecker
from world.expander import WorldExpander
from world.graft import GraftEngine
from world.idea_forge import IdeaForge
from world.models import WorldDoc, WorldEntity, WorldIdea
from world.studio import WorldStudio

SEED = "每个人死后都会留下一段从未说出口的记忆，但只有建筑能听见"


class IdeaForgeTest(unittest.TestCase):
    def test_offline_ideas_diverge_by_lens(self):
        ideas = IdeaForge().ideas(SEED, count=4)
        self.assertGreaterEqual(len(ideas), 3)
        self.assertGreaterEqual(len({i.lens for i in ideas}), 3)
        for idea in ideas:
            self.assertTrue(idea.core_rule)
            self.assertTrue(0.0 <= idea.distinctness <= 1.0)

    def test_count_is_bounded(self):
        self.assertGreaterEqual(len(IdeaForge().ideas("种子", count=99)), 3)


class ExpanderTest(unittest.TestCase):
    def _doc(self) -> WorldDoc:
        doc = WorldDoc(title="t", seed=SEED)
        doc.chosen_idea = WorldIdea(
            id="idea-1", label="制度世界", lens="制度",
            core_rule="围绕「记忆」形成了可执行、可争讼、可世袭的执法体系。",
        )
        return doc

    def test_grows_all_layers_from_one_rule(self):
        doc = WorldExpander().expand(self._doc())
        rules = doc.of_kind("rule")
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].state, "confirmed")
        for kind in ("consequence", "knowledge", "institution", "history",
                     "geography", "conflict", "motif"):
            self.assertTrue(doc.of_kind(kind), kind)
        self.assertTrue(doc.open_questions)
        derived = [e for e in doc.entities if e.kind != "rule"]
        self.assertTrue(all("rule-1" in e.depends_on for e in derived))
        self.assertTrue(all(e.state == "candidate" for e in derived))

    def test_expand_is_idempotent(self):
        doc = WorldExpander().expand(self._doc())
        before = len(doc.entities)
        WorldExpander().expand(doc)
        self.assertEqual(len(doc.entities), before)


class CheckerTest(unittest.TestCase):
    def test_flags_conflict_and_intentional_contradiction(self):
        doc = WorldDoc(title="t", seed="x")
        doc.add(WorldEntity(id="institution-1", kind="institution", name="教团",
                            statement="教团垄断对秩序的觉察", state="confirmed"))
        doc.add(WorldEntity(id="institution-2", kind="institution", name="异端",
                            statement="异端否认并能觉察秩序的反面", state="candidate"))
        doc.add(WorldEntity(id="consequence-1", kind="consequence", name="裂缝",
                            statement="秩序并不存在", state="contradiction"))
        issues = WorldChecker().check(doc)
        self.assertTrue(any(i["level"] == "warn" for i in issues))
        self.assertTrue(any(i["level"] == "note" for i in issues))


class GraftTest(unittest.TestCase):
    SRC = (
        "本世界的核心规则：记忆只能被建筑听见。历史上曾发生一场记忆灾变。"
        "权力由教会垄断。作品的主题是孤独与见证。建筑风格巨大而沉默。"
    )

    def test_extract_skeleton(self):
        skel = GraftEngine().extract(self.SRC, source_name="样例")
        self.assertTrue(skel.rules)
        self.assertIn("记忆", skel.primary_rule())
        self.assertTrue(skel.power or skel.history or skel.themes)

    def test_reverse_premise_marks_provenance_and_conflict(self):
        engine = GraftEngine()
        skel = engine.extract(self.SRC, source_name="样例")
        doc, notes = engine.transform(skel, "反转前提", "一个没有夜晚的城市")
        self.assertTrue(doc.provenance)
        self.assertTrue(doc.contradictions)
        self.assertEqual(doc.of_kind("rule")[0].state, "confirmed")
        text = emit.build_markdown(doc)
        self.assertIn("来源与变形", text)
        self.assertIn("反转前提", text)

    def test_cross_marks_two_sources(self):
        engine = GraftEngine()
        a = engine.extract(self.SRC, source_name="A")
        b = engine.extract("世界规则是：潮汐决定一切。", source_name="B")
        doc, notes = engine.transform(a, "世界交叉", "潮汐与记忆", second=b)
        self.assertTrue(doc.contradictions)
        self.assertTrue(any("交叉来源" in n for n in notes))


class StudioTest(unittest.TestCase):
    def test_end_to_end_export_and_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            studio = WorldStudio.create(SEED, root=Path(tmp), provider="mock")
            studio.raise_ideas(count=4)
            studio.choose("制度世界")
            studio.grow()
            path = studio.export()
            self.assertTrue(path.exists())
            text = path.read_text(encoding="utf-8")
            for needle in ("## 核心规则", "## 未决问题", "由 World Studio 生成", "制度世界"):
                self.assertIn(needle, text)
            self.assertTrue(studio.json_path.exists())
            reloaded = WorldStudio.load(studio.slug, root=Path(tmp))
            self.assertEqual(len(reloaded.doc.entities), len(studio.doc.entities))
            self.assertEqual(reloaded.doc.chosen_idea.label, "制度世界")

    def test_grow_requires_a_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            studio = WorldStudio.create(SEED, root=Path(tmp), provider="mock")
            studio.raise_ideas()
            with self.assertRaises(ValueError):
                studio.grow()


if __name__ == "__main__":
    unittest.main()
