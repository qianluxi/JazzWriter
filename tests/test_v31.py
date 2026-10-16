import json
import tempfile
import unittest
from pathlib import Path

from engine.report import build_html
from engine.vector_store import VectorStore
from tests.helpers import make_session, make_theme
from tests.test_v24 import FakeLLM

PREMISE = "一场技术事故改变了一个家庭"


class VectorStoreTest(unittest.TestCase):
    def test_query_and_persistence(self):
        vs = VectorStore(use_embedding=False)
        vs.add_many([
            ("a", "chapter", 1, "蒸汽管道仍然温热，附近没有任何工作人员。"),
            ("b", "chapter", 2, "苏在档案馆整理被封存的名单。"),
        ])
        top = vs.query("管道的温度", k=1)
        self.assertEqual(top[0][1].id, "a")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "vs.json"
            vs.save(path)
            loaded = VectorStore.load(path, use_embedding=False)
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded.query("名单", k=1)[0][1].id, "b")


class InteractiveReportTest(unittest.TestCase):
    def test_html_has_script_and_data(self):
        session = make_session(seed=1)
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        book = session.build_book(PREMISE, ideas, pick=0, chapters=5, seed=1)
        html = build_html(book, make_theme(), session.motifs, None)
        self.assertIn("<script", html)
        self.assertIn("const DATA", html)
        self.assertIn("章节浏览器", html)


class JamDebateTest(unittest.TestCase):
    def test_two_rounds_debate_and_attribution(self):
        session = make_session(seed=1)
        result = session.jam("深夜。检修井底。", pov="林", use_llm=False, rounds=2)
        self.assertEqual(result.rounds, 2)
        actors = {d["actor"] for d in result.debate}
        self.assertIn("observer", actors)
        self.assertIn("soloist", actors)
        sources = {a["source"] for a in result.attribution}
        self.assertEqual(sources, {"soloist", "observer"})

    def test_single_round_has_no_debate(self):
        session = make_session(seed=1)
        result = session.jam("深夜。", pov="林", use_llm=False, rounds=1)
        self.assertEqual(result.debate, [])
        self.assertTrue(result.proposal)


class ScenePlannerLlmTest(unittest.TestCase):
    def test_model_generated_skeletons(self):
        session = make_session(seed=1)
        scenes = json.dumps({"scenes": [
            {"goal": "在食堂日常里暴露异常", "pov": "林", "surface_action": "打饭",
             "latent_conflict": "想查又怕暴露", "improv_direction": "感官替换",
             "motif_variation": "蒸汽→余温", "info_boundary": "不解释原因",
             "exit_point": "不安时停笔"},
        ]})
        session.provider = FakeLLM([scenes])
        skeletons = session.plan(count=2)
        self.assertTrue(skeletons)
        self.assertEqual(skeletons[0].source, "llm")
        self.assertEqual(skeletons[0].pov, "林")

    def test_offline_fallback(self):
        session = make_session(seed=1)
        skeletons = session.plan(count=2)  # mock provider -> deterministic
        self.assertTrue(skeletons)
        self.assertNotEqual(skeletons[0].source, "llm")


if __name__ == "__main__":
    unittest.main()
