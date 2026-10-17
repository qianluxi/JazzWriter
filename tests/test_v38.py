import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from engine.preview import build_manuscript_html, rebuild_index, write_preview
from tests.helpers import make_session


class ManuscriptHtmlTest(unittest.TestCase):
    def test_build_contains_title_and_text(self):
        html = build_manuscript_html("界河纪事", [
            {"number": 1, "title": "冰上的界桩", "pov": "韩雪", "text": "第一段。\n第二段。"},
            {"number": 2, "title": "两边的名单", "pov": "瓦洛佳", "text": "第三段。"},
        ], question="隔开我们的是什么？")
        self.assertIn("界河纪事", html)
        self.assertIn("第一段。", html)
        self.assertIn("第 1 章", html)
        self.assertIn("隔开我们的是什么？", html)
        self.assertIn("第2章", html)  # nav anchor

    def test_write_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_preview(d, "a.html", "<html>A</html>")
            write_preview(d, "b.html", "<html>B</html>")
            idx = rebuild_index(d)
            self.assertTrue(idx.exists())
            text = idx.read_text(encoding="utf-8")
            self.assertIn("a.html", text)
            self.assertIn("b.html", text)


class PublishPreviewTest(unittest.TestCase):
    def test_publish_writes_files_without_git(self):
        session = make_session(seed=1)
        with tempfile.TemporaryDirectory() as tmp:
            session.preview_dir = Path(tmp)
            info = session.publish_preview(
                [(1, SimpleNamespace(text="正文甲。", pov="林", chapter=1))],
                push=False)
            self.assertTrue(Path(info["path"]).exists())
            self.assertTrue((Path(tmp) / "index.html").exists())
            self.assertIn("正文甲。", Path(info["path"]).read_text(encoding="utf-8"))
            self.assertFalse(info["pushed"])
            self.assertIs(session.last_publish, info)


if __name__ == "__main__":
    unittest.main()
