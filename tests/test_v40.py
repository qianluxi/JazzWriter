import unittest

from engine.preview import build_manuscript_html
from engine.textutil import word_count
from tests.helpers import make_session


class WordCountTest(unittest.TestCase):
    def test_textutil(self):
        self.assertEqual(word_count("你好，world!"), 3)   # 2 CJK + 1 latin word
        self.assertEqual(word_count(""), 0)

    def test_take_word_count_and_serialization(self):
        session = make_session(seed=1)
        take, _ = session.play("冬夜。食堂。一台旧机器。", pov="林")
        self.assertGreater(take.word_count, 0)
        self.assertEqual(take.to_dict()["word_count"], take.word_count)

    def test_preview_shows_counts(self):
        html = build_manuscript_html("书名", [
            {"number": 1, "title": "开端", "pov": "林", "text": "第一句话。world"},
        ])
        self.assertIn("字", html)
        self.assertIn("全书", html)

    def test_render_book_reports_counts(self):
        from tests.test_v26 import PREMISE, _multi_session
        session = _multi_session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        session.build_book(PREMISE, ideas, pick=0, chapters=4, seed=1)
        # render without publishing (no git) into a temp preview dir
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            session.preview_dir = Path(tmp)
            results = session.render_book_from_plan(save=False, publish=True)
        total = sum(t.word_count for _, t, _ in results)
        self.assertGreater(total, 0)
        self.assertTrue(session.last_publish and session.last_publish["path"])


if __name__ == "__main__":
    unittest.main()
