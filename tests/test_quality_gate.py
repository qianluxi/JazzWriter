import json
import unittest

from core.book_plan import BookPlan
from core.chapter_plan import ChapterPlan
from core.volume_plan import VolumePlan
from engine.plot_validator import PlotValidator
from gui import SingleFlight
from llm.mock import MockProvider
from tests.helpers import make_session
from tests.test_v24 import PREMISE, FakeLLM, _blueprint, _chapter, _volume


class SingleFlightTest(unittest.TestCase):
    def test_rejects_overlapping_tasks(self):
        flight = SingleFlight()
        self.assertTrue(flight.begin())
        self.assertFalse(flight.begin())   # second task rejected
        self.assertTrue(flight.busy)
        flight.end()
        self.assertFalse(flight.busy)
        self.assertTrue(flight.begin())    # recovered after finish


def _broken_book() -> BookPlan:
    ch1 = ChapterPlan(number=1, function="建立", pov="林", premise="p",
                      conflict="c1", outcome="o1", hook_from="start", hook_to="A",
                      threads=["t1"], summary="s1")
    ch3 = ChapterPlan(number=3, function="建立", pov="林", premise="p",
                      conflict="", outcome="o3", hook_from="B", hook_to="C",
                      threads=["t2"], summary="s3")
    return BookPlan(title="x", question="q", ending="一切照旧",
                    cast=["林", "苏"], volumes=[VolumePlan(number=1, chapters=[ch1, ch3])])


class ValidatorRegressionTest(unittest.TestCase):
    def test_flags_broken_structure(self):
        issues = PlotValidator().validate(_broken_book())
        kinds = {i.kind for i in issues}
        self.assertIn("numbering", kinds)     # missing chapter 2
        self.assertIn("incomplete", kinds)    # empty conflict
        self.assertIn("flat", kinds)          # same function twice
        self.assertIn("thread", kinds)        # threads appear once each
        self.assertIn("causal", kinds)        # hook_to A != hook_from B


class QualityGateTest(unittest.TestCase):
    """Short premise -> distinct directions -> full structure -> mid-book change
    with accurate downstream scope and preserved locks."""

    def test_end_to_end(self):
        session = make_session(seed=1)

        # 1) distinct story directions (fake LLM)
        ideas_json = json.dumps({"ideas": [
            {"label": "A", "premise": "p", "causal_mechanism": "系统性隐瞒",
             "truth_nature": "可查明", "character_relation": "父亲是共谋",
             "ending_direction": "以理解收束", "rationale": "r"},
            {"label": "B", "premise": "p", "causal_mechanism": "善意被时间放大",
             "truth_nature": "不可归结", "character_relation": "父亲是替罪者",
             "ending_direction": "开放结局", "rationale": "r"},
        ]})
        session.provider = FakeLLM([ideas_json])
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        self.assertGreaterEqual(len(ideas), 2)
        self.assertGreater(len({i.causal_mechanism for i in ideas}), 1)

        # 2) full structure via staged fake LLM
        session.provider = FakeLLM([
            _blueprint(2, [3, 3]),
            _volume([_chapter(i) for i in range(1, 4)]),
            _volume([_chapter(i) for i in range(4, 7)]),
        ])
        book = session.build_book(PREMISE, ideas, pick=0, chapters=6, seed=1)
        self.assertEqual(book.generated_by, "llm")
        self.assertEqual(book.chapter_numbers(), list(range(1, 7)))
        self.assertEqual(len(set(book.chapter_numbers())), 6)

        # 3) validate
        report = session.validate_book(book)
        self.assertTrue(report.dimensions)

        # 4) lock a downstream chapter and a field
        session.lock_chapter(5)
        session.lock_field(4, "outcome")
        locked5 = book.chapter(5).summary
        locked4_outcome = book.chapter(4).outcome

        # 5) re-improvise a mid chapter (offline candidates), adopt a different one
        session.provider = MockProvider()
        candidates = session.reimprovise_candidates(3, count=2, seed=1)
        self.assertTrue(candidates)
        pick = next((c for c in candidates if "conflict" in c.changed_fields), candidates[0])
        old_conflict = book.chapter(3).conflict
        book, affected = session.apply_candidate(pick)
        self.assertEqual(affected, [4, 5, 6])            # downstream scope
        self.assertNotEqual(book.chapter(3).conflict, old_conflict)  # genuinely different

        # 6) regenerate scope, preserving locks
        book, done = session.regenerate_chapters([3, 4, 5, 6])
        self.assertNotIn(5, done)                         # whole-chapter lock respected
        self.assertEqual(book.chapter(5).summary, locked5)
        self.assertEqual(book.chapter(4).outcome, locked4_outcome)  # field lock respected


if __name__ == "__main__":
    unittest.main()
