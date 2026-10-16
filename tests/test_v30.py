import unittest

from core.character import Character
from core.chapter_plan import (CharacterDecision, KnowledgeChange, RelationshipChange,
                               format_decisions, format_knowledge, format_relationships,
                               parse_decisions, parse_knowledge, parse_relationships)
from core.motif import MotifLibrary
from improvisation.improvisation_score import params_for_mode
from llm.mock import MockProvider
from session import Session
from tests.helpers import make_harmony, make_session, make_state, make_theme
from tests.test_v26 import PREMISE, _multi_session

PREMISE2 = "一场技术事故改变了一个家庭"


def _session_with_goal() -> Session:
    chars = {
        "林": Character(name="林", id="lin", tier="core", pov=True, desire="查真相",
                        current_goal="找到被改动的记录", secrets=["知道残页存在"]),
        "苏": Character(name="苏", id="su", tier="supporting", desire="让名字重见"),
    }
    motifs = MotifLibrary()
    motifs.ensure(["蒸汽"])
    return Session(make_theme(), make_harmony(), chars, motifs,
                   provider=MockProvider(), jazz=params_for_mode("bebop", seed=1),
                   story_state=make_state())


class IdeaComparisonTest(unittest.TestCase):
    def test_ideas_have_theme_reading_and_row(self):
        session = make_session(seed=1)
        ideas = session.story_ideas(PREMISE2, count=3, seed=1)
        self.assertTrue(all(i.theme_reading for i in ideas))
        rows = session.compare_ideas(ideas)
        self.assertEqual(len(rows), 3)
        self.assertIn("theme_reading", rows[0])


class FuseCompareTest(unittest.TestCase):
    def test_fuse_compare_from_a_or_b(self):
        session = make_session(seed=1)
        ideas = session.story_ideas(PREMISE2, count=2, seed=1)
        fused = session.fuse_ideas(ideas, 0, 1, seed=1)
        rows = session.fuse_compare(ideas[0], ideas[1], fused)
        self.assertEqual(len(rows), 5)
        for r in rows:
            self.assertIn(r["from"], ("A", "B", "新"))
            if r["from"] == "A":
                self.assertEqual(r["fused"], r["a"])
            elif r["from"] == "B":
                self.assertEqual(r["fused"], r["b"])


class ChapterContextTest(unittest.TestCase):
    def test_chapter_brief_and_cast_injection(self):
        session = _session_with_goal()
        self.assertIn("当前目标", session._char_list()[0].brief("chapter"))
        brief = session._planner()._chapter_cast_brief()
        self.assertIn("当前目标", brief)
        self.assertIn("找到被改动的记录", brief)

    def test_decision_motivation_uses_current_goal(self):
        session = _session_with_goal()
        ideas = session.story_ideas(PREMISE2, count=2, seed=1)
        book = session.build_book(PREMISE2, ideas, pick=0, chapters=6, seed=1)
        motives = [d.motivation for c in book.chapters() for d in c.character_decisions]
        self.assertIn("找到被改动的记录", motives)


class ParticipationEditTest(unittest.TestCase):
    def test_format_parse_roundtrip(self):
        decisions = [CharacterDecision(character_id="lin", decision="继续调查", motivation="相信证据")]
        self.assertEqual(parse_decisions(format_decisions(decisions)), decisions)

        knowledge = [KnowledgeChange(character_id="su", change="得知残页", source="第5章", fact_id="secret_001")]
        self.assertEqual(parse_knowledge(format_knowledge(knowledge)), knowledge)

        rels = [RelationshipChange(pair=["lin", "su"], change="信任下降", cause="要求公开")]
        self.assertEqual(parse_relationships(format_relationships(rels)), rels)


class RelationshipDimensionTest(unittest.TestCase):
    def test_dimension_present(self):
        session = _multi_session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        book = session.build_book(PREMISE, ideas, pick=0, chapters=10, template="multi_pov", seed=1)
        report = session.validate_book(book)
        self.assertIn("relationship_evolution", report.dimensions)
        self.assertTrue(0.0 <= report.dimensions["relationship_evolution"] <= 1.0)

    def test_no_relationships_is_neutral(self):
        session = make_session(seed=1)
        ideas = session.story_ideas(PREMISE2, count=2, seed=1)
        book = session.build_book(PREMISE2, ideas, pick=0, chapters=6, seed=1)
        report = session.validate_book(book)
        self.assertEqual(report.dimensions["relationship_evolution"], 0.5)


if __name__ == "__main__":
    unittest.main()
