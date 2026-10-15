import tempfile
import unittest
from pathlib import Path

import store
from store import load_book_plan, save_book_plan
from tests.helpers import make_session

PREMISE = "一场技术事故改变了一个家庭"


class StoryStructureTest(unittest.TestCase):
    def setUp(self):
        self.session = make_session(seed=7)

    def test_ideas_are_materially_distinct(self):
        ideas = self.session.story_ideas(PREMISE, count=3, seed=1)
        self.assertGreaterEqual(len(ideas), 2)
        self.assertTrue(any(i.distinctness > 0 for i in ideas))
        # candidates must differ in causal machinery, not only wording
        causals = {i.causal_mechanism for i in ideas}
        self.assertGreater(len(causals), 1)

    def test_build_expands_exact_chapter_count(self):
        ideas = self.session.story_ideas(PREMISE, count=2, seed=1)
        book = self.session.build_book(PREMISE, ideas, pick=0, chapters=9, template="mystery", seed=1)
        numbers = book.chapter_numbers()
        self.assertEqual(numbers, list(range(1, 10)))
        self.assertGreaterEqual(len(book.volumes), 1)

    def test_no_scene_cycling_in_structure(self):
        ideas = self.session.story_ideas(PREMISE, count=2, seed=1)
        book = self.session.build_book(PREMISE, ideas, pick=0, chapters=6, template="linear_causality", seed=1)
        summaries = [c.summary for c in book.chapters()]
        # chapters must not be byte-identical copies of one scene
        self.assertEqual(len(set(summaries)), len(summaries))

    def test_locked_chapter_survives_reimprovise(self):
        ideas = self.session.story_ideas(PREMISE, count=2, seed=1)
        book = self.session.build_book(PREMISE, ideas, pick=0, chapters=6, seed=1)
        self.session.lock_chapter(2)
        before = book.chapter(2).summary
        book2, affected = self.session.reimprovise_chapter(2, seed=99)
        self.assertTrue(book2.chapter(2).locked)
        self.assertEqual(book2.chapter(2).summary, before)
        self.assertIn(3, affected)

    def test_structure_report_dimensions(self):
        ideas = self.session.story_ideas(PREMISE, count=2, seed=1)
        book = self.session.build_book(PREMISE, ideas, pick=0, chapters=6, seed=1)
        report = self.session.validate_book(book)
        for key in ("idea_uniqueness", "completeness", "causal_continuity",
                    "character_change", "chapter_contribution", "foreshadowing"):
            self.assertIn(key, report.dimensions)

    def test_fuse_ideas_blends_dimensions(self):
        ideas = self.session.story_ideas(PREMISE, count=2, seed=1)
        fused = self.session.fuse_ideas(ideas, 0, 1, seed=1)
        self.assertTrue(fused.is_viable)
        # default blend: causal from A, truth from B
        self.assertEqual(fused.causal_mechanism, ideas[0].causal_mechanism)
        self.assertEqual(fused.truth_nature, ideas[1].truth_nature)
        self.assertGreater(fused.distinctness, 0.0)

    def test_update_chapter_roundtrip(self):
        from core.chapter_plan import apply_text, to_text
        ideas = self.session.story_ideas(PREMISE, count=2, seed=1)
        book = self.session.build_book(PREMISE, ideas, pick=0, chapters=5, seed=1)
        ch = book.chapter(2)
        text = to_text(ch).replace(ch.conflict, "全新冲突：证据本身不可靠")
        apply_text(ch, text)
        self.assertEqual(ch.conflict, "全新冲突：证据本身不可靠")
        self.session.update_chapter(2, {"title": "改过的标题"})
        self.assertEqual(self.session.book.chapter(2).title, "改过的标题")

    def test_scoped_regeneration_keeps_unselected(self):
        ideas = self.session.story_ideas(PREMISE, count=2, seed=1)
        book = self.session.build_book(PREMISE, ideas, pick=0, chapters=6, seed=1)
        before = {c.number: c.summary for c in book.chapters()}
        book2, regenerated = self.session.reimprovise_chapter(2, seed=99, regen=[2, 3])
        self.assertIn(2, regenerated)
        self.assertIn(3, regenerated)
        # chapters outside the scope keep their cards
        for n in (4, 5, 6):
            self.assertEqual(book2.chapter(n).summary, before[n])

    def test_book_plan_roundtrip(self):
        ideas = self.session.story_ideas(PREMISE, count=2, seed=1)
        book = self.session.build_book(PREMISE, ideas, pick=0, chapters=5, seed=1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "book_plan.json"
            save_book_plan(book, path)
            loaded = load_book_plan(path)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.chapter_numbers(), book.chapter_numbers())
        self.assertEqual(loaded.structure_template, book.structure_template)


if __name__ == "__main__":
    unittest.main()
