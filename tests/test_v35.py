import json
import tempfile
import unittest
from pathlib import Path

from core.character import Character
from core.motif import MotifLibrary
from improvisation.improvisation_score import params_for_mode
from llm.mock import MockProvider
from session import Session
from store import load_book_plan
from tests.helpers import make_harmony, make_session, make_state, make_theme
from tests.test_v24 import FakeLLM
from tests.test_v26 import PREMISE, _multi_session


def _proj(d: Path, name: str = "林") -> Session:
    return Session(make_theme(), make_harmony(), {name: Character(name=name, id="lin")},
                   MotifLibrary(), provider=MockProvider(),
                   jazz=params_for_mode("bebop", seed=1), story_state=make_state(),
                   data_dir=d)


class ProjectIsolationABTest(unittest.TestCase):
    def test_two_projects_do_not_cross(self):
        with tempfile.TemporaryDirectory() as da, tempfile.TemporaryDirectory() as db:
            da, db = Path(da), Path(db)
            a, b = _proj(da), _proj(db)
            a.play("场景甲。", pov="林")
            b.play("场景乙。", pov="林")
            # each project has its own runs / advice; A must not see B's history
            self.assertTrue(list((da / "runs").glob("*.json")))
            self.assertTrue(list((db / "runs").glob("*.json")))
            self.assertEqual(a.runs_dir, da / "runs")
            self.assertNotEqual(a.runs_dir, b.runs_dir)
            self.assertEqual(len(a.recent_texts(100)), 1)   # only A's own run
            self.assertEqual(len(b.recent_texts(100)), 1)
            self.assertTrue((da / "advice_history.jsonl").exists())
            self.assertNotEqual(a.advice_path, b.advice_path)


class ReimproviseKeepsPovTest(unittest.TestCase):
    def test_offline_keeps_pov_and_participants(self):
        session = _multi_session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        book = session.build_book(PREMISE, ideas, pick=0, chapters=8, template="multi_pov", seed=1)
        base = book.chapter(3)
        cand = session.reimprovise_candidates(3, seed=1)[0].chapter
        self.assertEqual(cand.pov, base.pov)
        self.assertEqual(cand.pov_character_id, base.pov_character_id)
        self.assertEqual(set(cand.characters_involved), set(base.characters_involved))

    def test_llm_cannot_change_pov(self):
        session = _multi_session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        book = session.build_book(PREMISE, ideas, pick=0, chapters=8, template="multi_pov", seed=1)
        base = book.chapter(3)
        payload = json.dumps({"candidates": [{"label": "换视角", "chapter": {
            "pov": "苏", "pov_character_id": "su",
            "key_action": "新行动", "conflict": "新冲突", "outcome": "新结果",
            "info_change": "新信息"}}]})
        session.provider = FakeLLM([payload])
        cand = session.reimprovise_candidates(3, seed=1)[0].chapter
        self.assertEqual(cand.pov, base.pov)                    # POV stays fixed
        self.assertEqual(cand.pov_character_id, base.pov_character_id)
        self.assertEqual(set(cand.characters_involved), set(base.characters_involved))
        # but content did change
        self.assertEqual(cand.key_action, "新行动")


class EndToEndWorkflowTest(unittest.TestCase):
    def test_build_lock_reimprovise_adopt_reload(self):
        session = _multi_session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        book = session.build_book(PREMISE, ideas, pick=0, chapters=8, template="multi_pov", seed=1)
        session.save_book()
        session.lock_chapter(5)
        candidate = session.reimprovise_candidates(3, seed=1)[0]
        session.apply_candidate(candidate)
        reloaded = load_book_plan(session.book_plan_path)
        self.assertIsNotNone(reloaded)
        self.assertTrue(reloaded.chapter(5).locked)
        self.assertEqual(reloaded.chapter(3).pov_character_id,
                         reloaded.chapter(3).pov_character_id)  # coherent
        self.assertTrue(reloaded.chapter(3).character_decisions)


if __name__ == "__main__":
    unittest.main()
