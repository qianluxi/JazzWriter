import random
import unittest

from improvisation.surprise_engine import SurpriseEngine
from tests.helpers import make_session, make_state


class DeterminismTest(unittest.TestCase):
    def test_same_seed_same_cue(self):
        s1 = make_session(seed=123)
        s2 = make_session(seed=123)
        cue1 = s1.roll_cue("林", jazz_mode="free_jazz", seed=123, chapter=3)
        cue2 = s2.roll_cue("林", jazz_mode="free_jazz", seed=123, chapter=3)
        self.assertEqual(cue1.to_dict(), cue2.to_dict())

    def test_different_seed_differs(self):
        s = make_session()
        a = s.roll_cue("林", jazz_mode="free_jazz", seed=123, chapter=3).to_dict()
        b = s.roll_cue("林", jazz_mode="free_jazz", seed=999, chapter=3).to_dict()
        self.assertNotEqual(a, b)

    def test_surprise_reproducible(self):
        state = make_state()
        e1 = SurpriseEngine(random.Random(7))
        e2 = SurpriseEngine(random.Random(7))
        r1 = e1.mutate(0.9, state, has_motifs=True, motifs=["蒸汽"])
        r2 = e2.mutate(0.9, state, has_motifs=True, motifs=["蒸汽"])
        self.assertEqual([s.to_dict() for s in r1], [s.to_dict() for s in r2])

    def test_cue_has_operators_and_state(self):
        cue = make_session().roll_cue("林", jazz_mode="bebop", seed=5, chapter=2)
        self.assertIsNotNone(cue.operators)
        self.assertTrue(1 <= len(cue.operators.operators) <= 3)


if __name__ == "__main__":
    unittest.main()
