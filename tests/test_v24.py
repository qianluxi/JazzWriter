import json
import tempfile
import unittest
from pathlib import Path

from core.book_plan import BookPlan
from store import load_book_plan, save_book_plan
from tests.helpers import make_session

PREMISE = "一场技术事故改变了一个家庭"


class FakeLLM:
    """Returns canned strings for planning JSON calls (name != mock)."""
    name = "fake"

    def __init__(self, responses):
        self.responses = list(responses)

    def generate(self, prompt, *, system=None, context=None, temperature=0.9, max_tokens=1500):
        return self.responses.pop(0) if self.responses else "{}"


def _chapter(n, fn="推进"):
    return {"title": f"章{n}", "function": fn, "pov": "林", "premise": f"p{n}",
            "key_action": f"a{n}", "conflict": f"c{n}", "outcome": f"o{n}", "stakes": "s",
            "info_change": f"i{n}", "character_change": f"ch{n}", "threads": [], "motifs": ["蒸汽"],
            "hook_from": "", "hook_to": f"h{n}", "summary": f"sum{n}"}


def _blueprint(vcount, counts):
    return json.dumps({
        "logline": "L", "synopsis": "S", "opening_state": "O", "inciting_incident": "I",
        "central_turn": "T", "climax": "C", "resolution": "R", "main_conflict": "M",
        "ending": "E", "key_turns": ["t1"], "volume_count": vcount,
        "volumes": [{"title": f"v{i+1}", "goal": "g", "opening_state": "o", "climax": "c",
                     "outcome": "r", "sets_up_next": "s", "chapter_count": counts[i]}
                    for i in range(vcount)],
    })


def _volume(chapters):
    return json.dumps({"chapters": chapters})


class LLMStructureTest(unittest.TestCase):
    def _session(self):
        s = make_session(seed=1)
        return s

    def test_valid_llm_response_is_accepted(self):
        session = self._session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        session.provider = FakeLLM([_blueprint(2, [3, 3]),
                                    _volume([_chapter(i) for i in range(1, 4)]),
                                    _volume([_chapter(i) for i in range(4, 7)])])
        book = session.build_book(PREMISE, ideas, pick=0, chapters=6, seed=1)
        self.assertEqual(book.generated_by, "llm")
        self.assertEqual(book.chapter_numbers(), list(range(1, 7)))
        self.assertEqual(len(set(book.chapter_numbers())), 6)
        self.assertTrue(all(c.source == "llm" for c in book.chapters()))

    def test_insufficient_chapters_falls_back_and_is_marked(self):
        session = self._session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        session.provider = FakeLLM([_blueprint(1, [6]), _volume([_chapter(1), _chapter(2)])])
        book = session.build_book(PREMISE, ideas, pick=0, chapters=6, seed=1)
        self.assertEqual(book.generated_by, "offline_template")
        self.assertEqual(len(book.chapters()), 6)  # exact count guaranteed

    def test_malformed_json_falls_back(self):
        session = self._session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        session.provider = FakeLLM(["not json at all", "{}"])
        book = session.build_book(PREMISE, ideas, pick=0, chapters=5, seed=1)
        self.assertEqual(book.generated_by, "offline_template")


class ConstraintsTest(unittest.TestCase):
    def test_world_constraints_propagate_into_book(self):
        session = make_session(seed=1)
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        book = session.build_book(PREMISE, ideas, pick=0, chapters=6, seed=1)
        joined = " ".join(book.constraints)
        self.assertTrue(book.constraints)
        self.assertIn("世界规则", joined)
        self.assertIn("禁忌", joined)


class PersistenceTest(unittest.TestCase):
    def test_roundtrip_preserves_new_fields(self):
        session = make_session(seed=1)
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        book = session.build_book(PREMISE, ideas, pick=0, chapters=6, seed=1)
        session.lock_field(2, "conflict")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bp.json"
            save_book_plan(book, path)
            loaded = load_book_plan(path)
        self.assertEqual(loaded.synopsis, book.synopsis)
        self.assertEqual(loaded.generated_by, book.generated_by)
        self.assertEqual(loaded.constraints, book.constraints)
        self.assertIn("conflict", loaded.chapter(2).locked_fields)


class ReimproviseQualityTest(unittest.TestCase):
    def test_candidate_changes_fields_and_adopt(self):
        session = make_session(seed=1)
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        session.build_book(PREMISE, ideas, pick=0, chapters=6, seed=1)
        session.lock_field(3, "conflict")
        candidates = session.reimprovise_candidates(3, seed=1)
        self.assertTrue(candidates)
        self.assertTrue(candidates[0].changed_fields)
        locked_conflict = session.book.chapter(3).conflict
        book, affected = session.apply_candidate(candidates[0])
        self.assertEqual(book.chapter(3).conflict, locked_conflict)  # locked field kept
        self.assertIn(4, affected)

    def test_expand_requires_force(self):
        session = make_session(seed=1)
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        session.build_book(PREMISE, ideas, pick=0, chapters=5, seed=1)
        with self.assertRaises(ValueError):
            session.expand_book()


class StaleIdeaTest(unittest.TestCase):
    def test_stale_detection(self):
        session = make_session(seed=1)
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        self.assertFalse(session.ideas_stale(ideas, PREMISE))
        self.assertTrue(session.ideas_stale(ideas, PREMISE + "（改了前提）"))


class TwoLayerEvalTest(unittest.TestCase):
    def test_report_has_validation_and_review(self):
        session = make_session(seed=1)
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        book = session.build_book(PREMISE, ideas, pick=0, chapters=6, template="mystery", seed=1)
        report = session.validate_book(book)
        self.assertIsInstance(report.validation, list)
        self.assertIsInstance(report.review, list)
        d = report.as_dict()
        self.assertIn("validation", d)
        self.assertIn("review", d)


if __name__ == "__main__":
    unittest.main()
