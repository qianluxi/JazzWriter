import json
import tempfile
import unittest
from pathlib import Path

from core.book_plan import BookPlan
from core.character import Character
from core.chapter_plan import ChapterPlan
from core.motif import MotifLibrary
from core.relationship import Relationship, RelationshipMap
from core.volume_plan import VolumePlan
from engine.plot_validator import PlotValidator
from improvisation.improvisation_score import params_for_mode
from llm.mock import MockProvider
from session import Session
from store import load_book_plan, save_book_plan
from tests.helpers import make_harmony, make_state, make_theme
from tests.test_v24 import _blueprint, _volume

PREMISE = "一场技术事故改变了一个家庭"


def _session(rels=None) -> Session:
    chars = {
        "林": Character(name="林", id="lin", tier="core", pov=True, desire="查真相",
                        aliases=["阿林"]),
        "苏": Character(name="苏", id="su", tier="core", pov=True, desire="让名字重见"),
        "赵": Character(name="赵", id="zhao", tier="supporting", pov=False, desire="尽快结案"),
    }
    motifs = MotifLibrary()
    motifs.ensure(["蒸汽", "阀门"])
    return Session(make_theme(), make_harmony(), chars, motifs,
                   provider=MockProvider(), jazz=params_for_mode("bebop", seed=1),
                   story_state=make_state(), relationships=rels or RelationshipMap())


class PovFilterTest(unittest.TestCase):
    def test_non_pov_character_never_viewpoint(self):
        session = _session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        book = session.build_book(PREMISE, ideas, pick=0, chapters=12, template="multi_pov", seed=1)
        pov_ids = {c.pov_character_id for c in book.chapters()}
        self.assertNotIn("zhao", pov_ids)

    def test_primary_character_converges(self):
        session = _session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        book = session.build_book(PREMISE, ideas, pick=0, chapters=9, template="multi_pov", seed=1)
        self.assertEqual(book.primary_character_id, "lin")
        converge = [c for c in book.chapters() if c.function in ("高潮", "收束", "汇合")]
        self.assertTrue(converge)
        self.assertTrue(all(c.pov_character_id == "lin" for c in converge))


class ResolveCharacterTest(unittest.TestCase):
    def test_resolve_by_id_name_alias(self):
        session = _session()
        self.assertEqual(session.resolve_character("lin").name, "林")
        self.assertEqual(session.resolve_character("林").effective_id, "lin")
        self.assertEqual(session.resolve_character("阿林").effective_id, "lin")


class SetupWarningsTest(unittest.TestCase):
    def test_duplicate_id_and_dangling_endpoint(self):
        chars = {"A": Character(name="A", id="dup"), "B": Character(name="B", id="dup")}
        rels = RelationshipMap(relationships=[Relationship(source_id="dup", target_id="ghost")])
        session = Session(make_theme(), make_harmony(), chars, MotifLibrary(),
                          provider=MockProvider(), jazz=params_for_mode("bebop", seed=1),
                          story_state=make_state(), relationships=rels)
        warns = " ".join(session.setup_warnings())
        self.assertIn("id 重复", warns)
        self.assertIn("端点不存在", warns)


class ChapterFieldsPersistenceTest(unittest.TestCase):
    def test_nested_fields_roundtrip(self):
        session = _session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        book = session.build_book(PREMISE, ideas, pick=0, chapters=8, template="multi_pov", seed=1)
        ch = book.chapters()[0]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bp.json"
            save_book_plan(book, path)
            loaded = load_book_plan(path)
        lch = loaded.chapters()[0]
        self.assertTrue(lch.character_decisions)
        self.assertTrue(lch.knowledge_changes)
        self.assertTrue(lch.character_decisions[0].character_id)
        self.assertTrue(lch.knowledge_changes[0].source)


class LlmChapterFieldsTest(unittest.TestCase):
    def test_llm_parses_decisions_and_knowledge(self):
        from tests.test_v24 import FakeLLM
        session = _session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)

        def chap(n):
            return {"title": f"章{n}", "function": "推进", "pov": "林", "pov_character_id": "lin",
                    "characters_involved": ["lin", "su"], "premise": "p", "key_action": "a",
                    "conflict": "c", "outcome": "o", "stakes": "s", "info_change": "i",
                    "character_change": "ch",
                    "character_decisions": [{"character_id": "lin", "decision": "继续调查",
                                             "motivation": "相信证据"}],
                    "knowledge_changes": [{"character_id": "su", "change": "得知残页存在",
                                           "source": "第5章对话"}],
                    "threads": [], "motifs": ["蒸汽"], "hook_from": "", "hook_to": "h",
                    "summary": f"s{n}"}

        session.provider = FakeLLM([_blueprint(2, [2, 2]),
                                    _volume([chap(1), chap(2)]),
                                    _volume([chap(3), chap(4)])])
        book = session.build_book(PREMISE, ideas, pick=0, chapters=4, seed=1)
        self.assertEqual(book.generated_by, "llm")
        ch = book.chapters()[0]
        self.assertEqual(ch.character_decisions[0].decision, "继续调查")
        self.assertEqual(ch.knowledge_changes[0].source, "第5章对话")


class RelationshipIsolationTest(unittest.TestCase):
    def test_isolated_group_flagged(self):
        rels = RelationshipMap(relationships=[
            Relationship(source_id="lin", target_id="su"),
            Relationship(source_id="chen", target_id="zhao"),
        ])
        ch = ChapterPlan(number=1, function="建立", pov="林", premise="p", conflict="c",
                         outcome="o", summary="s", pov_character_id="lin",
                         characters_involved=["lin"])
        book = BookPlan(title="x", cast=["林", "苏", "chen", "zhao"],
                        cast_ids=["lin", "su", "chen", "zhao"], primary_character_id="lin",
                        volumes=[VolumePlan(number=1, chapters=[ch])])
        issues = PlotValidator().validate(book, relationships=rels)
        self.assertTrue(any(i.kind == "relationship_isolation" for i in issues))


if __name__ == "__main__":
    unittest.main()
