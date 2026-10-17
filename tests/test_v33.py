import tempfile
import unittest
from pathlib import Path

from core.chapter_plan import ChapterPlan
from core.character import Character
from core.harmony import Harmony
from core.motif import MotifLibrary
from engine.outline_expander import OutlineExpander
from improvisation.improvisation_score import params_for_mode
from llm.mock import MockProvider
from session import Session
from store import load_characters
from tests.helpers import (make_character, make_harmony, make_session, make_state,
                          make_theme)
from tests.test_v26 import PREMISE, _multi_session


class ProjectIsolationRuntimeTest(unittest.TestCase):
    def test_runs_and_chapters_are_project_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            session = Session(make_theme(), make_harmony(), {"林": make_character()},
                              MotifLibrary(), provider=MockProvider(),
                              jazz=params_for_mode("bebop", seed=1),
                              story_state=make_state(), data_dir=tmp)
            session.play("深夜。井底。", pov="林")
            self.assertTrue(list((tmp / "runs").glob("*.json")))
            session.compose_book(["场景一", "场景二"], save=True)
            self.assertTrue(list((tmp / "chapters").glob("*.md")))
            self.assertTrue(list((tmp / "runs").glob("*.json")))


class DuplicateIdTest(unittest.TestCase):
    def test_duplicate_id_keeps_both_and_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "characters.yaml"
            path.write_text(
                "characters:\n"
                "  - name: 甲\n    id: dup\n"
                "  - name: 乙\n    id: dup\n",
                encoding="utf-8")
            chars = load_characters(path)
        self.assertEqual(len(chars), 2)  # neither lost
        session = Session(make_theme(), make_harmony(), chars, MotifLibrary(),
                          provider=MockProvider(), jazz=params_for_mode("bebop", seed=1),
                          story_state=make_state())
        warns = " ".join(session.setup_warnings())
        self.assertIn("id 重复", warns)


class ReimproviseConsistencyTest(unittest.TestCase):
    def test_pov_and_involvement_follow_candidate(self):
        session = _multi_session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        session.build_book(PREMISE, ideas, pick=0, chapters=8, template="multi_pov", seed=1)
        cand = session.reimprovise_candidates(3, seed=1)[0].chapter
        expected_id = session.resolve_character(cand.pov).effective_id
        self.assertEqual(cand.pov_character_id, expected_id)
        self.assertIn(cand.pov_character_id, cand.characters_involved)

    def test_knowledge_source_is_anchored(self):
        session = _multi_session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        session.build_book(PREMISE, ideas, pick=0, chapters=8, template="multi_pov", seed=1)
        cand = session.reimprovise_candidates(3, seed=1)[0].chapter
        if cand.knowledge_changes:
            self.assertIn("〈", cand.knowledge_changes[0].source)


class OfflineFieldSanitizeTest(unittest.TestCase):
    def test_all_fields_sanitized(self):
        expander = OutlineExpander(
            make_theme(), [Character(name="林", id="lin")],
            harmony=Harmony(world="", rules=[], forbidden=["魔法"]),
            story_state=make_state())
        ch = ChapterPlan(number=1, pov="林", pov_character_id="lin",
                         title="魔法之门", conflict="这里有魔法", hook_to="魔法",
                         summary="父亲签下了掩盖命令")
        expander._sanitize_chapter(ch, "lin")
        self.assertNotIn("魔法", ch.title + ch.conflict + ch.hook_to)
        self.assertNotIn("父亲签下了掩盖命令", ch.summary)


class PovGuardTest(unittest.TestCase):
    def test_no_pov_character_blocks_build(self):
        session = make_session(seed=1)
        for c in session.characters.values():
            c.pov = False
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        with self.assertRaises(ValueError):
            session.build_book(PREMISE, ideas, pick=0, chapters=5, seed=1)


class ComposeBookNoCycleTest(unittest.TestCase):
    def test_compose_book_refuses_cycling(self):
        session = make_session(seed=1)
        with self.assertRaises(ValueError):
            session.compose_book(["只有一个场景"], target_chapters=3, save=False)


if __name__ == "__main__":
    unittest.main()
