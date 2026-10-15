import unittest
from collections import Counter

from core.character import Character
from core.motif import MotifLibrary
from improvisation.improvisation_score import params_for_mode
from jam_session.director import JamBrief
from jam_session.editor import Editor
from llm.mock import MockProvider
from session import Session
from tests.helpers import make_character, make_harmony, make_state, make_theme

PREMISE = "一场技术事故改变了一个家庭"


def _multi_session() -> Session:
    characters = {
        "林": make_character(),
        "苏": Character(name="苏", role="档案管理员", desire="让被抹去的名字重现",
                        fear="记忆被改写", worldview="记忆即权力",
                        memory="烧过一份名单", contradiction="守护真相却依靠谎言"),
    }
    motifs = MotifLibrary()
    motifs.ensure(["蒸汽", "阀门"])
    return Session(make_theme(), make_harmony(), characters, motifs,
                   provider=MockProvider(), jazz=params_for_mode("bebop", seed=1),
                   story_state=make_state())


def _max_run(seq):
    best = run = 1
    for a, b in zip(seq, seq[1:]):
        run = run + 1 if a == b else 1
        best = max(best, run)
    return best


class PovDistributionTest(unittest.TestCase):
    def setUp(self):
        self.session = _multi_session()

    def test_multi_pov_uses_all_and_avoids_long_runs(self):
        ideas = self.session.story_ideas(PREMISE, count=2, seed=1)
        book = self.session.build_book(PREMISE, ideas, pick=0, chapters=10, template="multi_pov", seed=1)
        povs = [c.pov for c in book.chapters()]
        self.assertEqual(set(povs), set(self.session.characters.keys()))
        # turning-point chapters converge on the protagonist, so allow a small run
        self.assertLessEqual(_max_run(povs), 3)

    def test_ensemble_uses_all(self):
        ideas = self.session.story_ideas(PREMISE, count=2, seed=1)
        book = self.session.build_book(PREMISE, ideas, pick=0, chapters=9, template="ensemble", seed=1)
        povs = Counter(c.pov for c in book.chapters())
        self.assertEqual(set(povs), set(self.session.characters.keys()))

    def test_converge_functions_go_to_protagonist(self):
        ideas = self.session.story_ideas(PREMISE, count=2, seed=1)
        book = self.session.build_book(PREMISE, ideas, pick=0, chapters=9, template="multi_pov", seed=1)
        for ch in book.chapters():
            if ch.function in ("高潮", "收束"):
                self.assertEqual(ch.pov, book.cast[0])


class FieldLockTest(unittest.TestCase):
    def test_locked_field_survives_regeneration(self):
        session = _multi_session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        book = session.build_book(PREMISE, ideas, pick=0, chapters=6, seed=1)
        session.lock_field(3, "conflict")
        locked_value = book.chapter(3).conflict
        book2, regenerated = session.reimprovise_chapter(3, seed=99, regen=[3, 4])
        self.assertIn(3, regenerated)          # chapter itself regenerated
        self.assertEqual(book2.chapter(3).conflict, locked_value)  # field preserved
        self.assertIn("conflict", book2.chapter(3).locked_fields)


class JamSessionTest(unittest.TestCase):
    def setUp(self):
        self.session = _multi_session()

    def test_jam_is_deterministic_and_has_roles(self):
        a = self.session.jam("深夜。检修井底。", pov="林", use_llm=False)
        b = self.session.jam("深夜。检修井底。", pov="林", use_llm=False)
        self.assertEqual(a.proposal, b.proposal)
        self.assertTrue(a.solo and a.observer)
        self.assertTrue(a.brief.direction)

    def test_editor_removes_premature_reveal(self):
        brief = JamBrief(scene="x", direction="d", pov="林")
        result = Editor().run(brief, ["档案里写着：父亲签下了掩盖命令。"], ["一个细节"],
                              story_state=make_state())
        self.assertTrue(result.removed)
        self.assertEqual(result.observer, ["一个细节"])

    def test_jam_to_take_renders(self):
        jam = self.session.jam("深夜。检修井底。", pov="林", use_llm=False)
        take, eva = self.session.jam_to_take(jam, pov="林", save=False, seed=1)
        self.assertTrue(take.text)


if __name__ == "__main__":
    unittest.main()
