import tempfile
import unittest
from pathlib import Path

from engine.memory import MemoryIndex, analyze_book
from engine.report import build_markdown, write_reports
from jam_session.editor import Editor
from tests.helpers import make_session, make_theme

PREMISE = "一场技术事故改变了一个家庭"


class MemoryTest(unittest.TestCase):
    def test_duplicates_detected(self):
        idx = MemoryIndex()
        idx.add("a", "chapter", 1, "林在检修井底发现阀门被人拧过，扳手擦痕是新的。")
        idx.add("b", "chapter", 2, "林在检修井底发现阀门被人拧过，扳手擦痕是新的。")
        idx.add("c", "chapter", 3, "苏在档案馆发现报告存在两个不同版本。")
        dups = idx.duplicates(threshold=0.5)
        pairs = {(d["a"], d["b"]) for d in dups}
        self.assertIn(("a", "b"), pairs)
        self.assertNotIn(("a", "c"), pairs)

    def test_query_ranks_related(self):
        idx = MemoryIndex()
        idx.add("a", "chapter", 1, "蒸汽管道仍然温热，附近没有任何工作人员。")
        idx.add("b", "chapter", 2, "苏在档案馆整理被封存的名单。")
        top = idx.query("管道的温度", k=1)
        self.assertEqual(top[0][1].id, "a")

    def test_analyze_book_reports(self):
        session = make_session(seed=1)
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        book = session.build_book(PREMISE, ideas, pick=0, chapters=6, template="mystery", seed=1)
        report = analyze_book(book, make_theme(), motifs=session.motifs, story_state=session.story_state)
        self.assertEqual(len(report.theme_similarity), len(book.chapters()))
        self.assertTrue(report.issues)


class ReportTest(unittest.TestCase):
    def test_write_reports(self):
        session = make_session(seed=1)
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        book = session.build_book(PREMISE, ideas, pick=0, chapters=6, seed=1)
        md_text = build_markdown(book, make_theme(), session.motifs, None)
        self.assertIn("动机演变时间线", md_text)
        self.assertIn("线索与伏笔面板", md_text)
        with tempfile.TemporaryDirectory() as tmp:
            md, html = write_reports(book, make_theme(), motifs=session.motifs, outdir=Path(tmp))
            self.assertTrue(md.exists() and html.exists())
            self.assertIn("<table", html.read_text(encoding="utf-8"))


class EditorRankTest(unittest.TestCase):
    def test_rank_sorted_and_chosen(self):
        ranked = Editor.rank(["短", "林用袖口把灰重新抹回原位，记下阀门擦痕的方向。", "心潮澎湃"])
        scores = [r["score"] for r in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertTrue(all(0.0 <= s <= 1.0 for s in scores))
        # the concrete, non-cliché candidate should rank first
        self.assertIn("擦痕", ranked[0]["text"])


if __name__ == "__main__":
    unittest.main()
