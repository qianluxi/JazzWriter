import unittest

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
from tests.helpers import make_harmony, make_state, make_theme

PREMISE = "一场技术事故改变了一个家庭"


def _multi_session() -> Session:
    chars = {
        "林": Character(name="林", id="lin", tier="core", desire="查清真相",
                        fear="发现父亲是共谋", blind_spots=["只信技术还原"],
                        capabilities=["检修"], constraints=["无权调密档"]),
        "苏": Character(name="苏", id="su", tier="core", desire="让名字重见",
                        fear="记忆被改写"),
        "赵": Character(name="赵", id="zhao", tier="supporting", pov=False,
                        desire="尽快结案", fear="暴露监管失效"),
    }
    rels = RelationshipMap(relationships=[
        Relationship(source_id="lin", target_id="su", type="调查者与档案管理者",
                     mutual_interest="互取所需", conflict="是否公开记录",
                     pressure_point="名单残页", possible_transition="信任或决裂"),
        Relationship(source_id="lin", target_id="zhao", type="被调查者与调查者",
                     conflict="翻案 vs 结案"),
    ])
    motifs = MotifLibrary()
    motifs.ensure(["蒸汽", "阀门"])
    return Session(make_theme(), make_harmony(), chars, motifs,
                   provider=MockProvider(), jazz=params_for_mode("bebop", seed=1),
                   story_state=make_state(), relationships=rels)


class CharacterModelTest(unittest.TestCase):
    def test_effective_id(self):
        self.assertEqual(Character(name="林").effective_id, "林")
        self.assertEqual(Character(name="林", id="lin").effective_id, "lin")

    def test_brief_includes_drivers(self):
        c = Character(name="林", id="lin", desire="查真相", blind_spots=["只信技术"])
        brief = c.brief()
        self.assertIn("lin", brief)
        self.assertIn("查真相", brief)
        self.assertIn("只信技术", brief)


class RelationshipTest(unittest.TestCase):
    def test_for_character_and_brief(self):
        rels = RelationshipMap(relationships=[Relationship(source_id="a", target_id="b",
                                                           type="对手", conflict="目标冲突")])
        self.assertEqual(len(rels.for_character("a")), 1)
        self.assertEqual(len(rels.for_character("c")), 0)
        self.assertIn("对手", rels.brief(["a"]))


class InjectionTest(unittest.TestCase):
    def test_cast_ids_and_chapter_character_fields(self):
        session = _multi_session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        book = session.build_book(PREMISE, ideas, pick=0, chapters=6, template="multi_pov", seed=1)
        self.assertEqual(set(book.cast_ids), {"lin", "su", "zhao"})
        for ch in book.chapters():
            self.assertTrue(ch.pov_character_id)
            self.assertTrue(ch.characters_involved)
            self.assertTrue(ch.character_decisions)
            self.assertIn(ch.pov_character_id, ch.characters_involved)


class UsageTest(unittest.TestCase):
    def test_usage_and_idle(self):
        session = _multi_session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        session.build_book(PREMISE, ideas, pick=0, chapters=6, template="ensemble", seed=1)
        usage = session.character_usage()
        ids = {r["id"] for r in usage}
        self.assertEqual(ids, {"lin", "su", "zhao"})
        # every registered character should participate in at least one chapter
        self.assertEqual(session.idle_characters(), [])


class ValidatorUsageTest(unittest.TestCase):
    def test_unused_character_flagged(self):
        ch = ChapterPlan(number=1, function="建立", pov="林", premise="p",
                         conflict="c", outcome="o", summary="s",
                         characters_involved=["lin"])
        book = BookPlan(title="x", cast=["林", "赵"], cast_ids=["lin", "zhao"],
                        volumes=[VolumePlan(number=1, chapters=[ch])])
        kinds = {i.kind for i in PlotValidator().validate(book)}
        self.assertIn("unused_character", kinds)


if __name__ == "__main__":
    unittest.main()
