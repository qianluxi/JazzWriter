import unittest

from core.book_plan import BookPlan
from core.chapter_plan import ChapterPlan, KnowledgeChange
from core.volume_plan import VolumePlan
from engine.plot_validator import PlotValidator
from tests.helpers import make_session, make_state
from tests.test_v26 import PREMISE, _multi_session


class RelationshipInjectionTest(unittest.TestCase):
    def test_relationships_reach_the_planner(self):
        without = make_session(seed=1)._planner()._relationships_brief()
        with_rels = _multi_session()._planner()._relationships_brief()
        self.assertEqual(without, "")
        self.assertIn("冲突", with_rels)
        self.assertIn("lin", with_rels)


class WorldConstraintInjectionTest(unittest.TestCase):
    def test_story_state_facts_and_forbidden_reach_the_plan(self):
        session = make_session(seed=1)  # make_state has a confirmed fact + a secret
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        book = session.build_book(PREMISE, ideas, pick=0, chapters=6, seed=1)
        joined = " ".join(book.constraints)
        self.assertIn("世界规则", joined)
        self.assertIn("禁忌", joined)
        self.assertIn("已确定事实", joined)
        self.assertIn("不可提前揭露", joined)


def _book(kcs, number=2):
    ch = ChapterPlan(number=number, function="调查", pov="林", premise="p",
                     conflict="c", outcome="o", summary="s",
                     knowledge_changes=list(kcs))
    return BookPlan(title="x", cast=["林"], cast_ids=["林"],
                    volumes=[VolumePlan(number=1, chapters=[ch])])


class KnowledgeContinuityTest(unittest.TestCase):
    def test_missing_source_flagged(self):
        book = _book([KnowledgeChange(character_id="林", change="得知真相", source="")])
        issues = PlotValidator().validate(book, story_state=make_state())
        self.assertTrue(any(i.kind == "knowledge" and "信息来源" in i.message for i in issues))

    def test_future_source_flagged(self):
        book = _book([KnowledgeChange(character_id="林", change="得知", source="第5章 对话")], number=2)
        issues = PlotValidator().validate(book, story_state=make_state())
        self.assertTrue(any(i.kind == "knowledge" and "不早于本章" in i.message for i in issues))

    def test_secret_reveal_hint(self):
        book = _book([KnowledgeChange(character_id="林", change="得知", source="第1章 记录",
                                      fact_id="secret_001")], number=2)
        issues = PlotValidator().validate(book, story_state=make_state())
        self.assertTrue(any(i.kind == "knowledge" and "秘密" in i.message for i in issues))

    def test_clean_knowledge_passes(self):
        book = _book([KnowledgeChange(character_id="林", change="得知", source="第1章 记录")], number=2)
        issues = PlotValidator().validate(book, story_state=make_state())
        self.assertFalse(any(i.kind == "knowledge" for i in issues))


if __name__ == "__main__":
    unittest.main()
