import random
import unittest

from core.story_state import StoryState
from engine.evaluator import Evaluator
from improvisation.surprise_engine import SurpriseEngine
from tests.helpers import make_character, make_harmony, make_state, make_theme

GENERIC_ONLY = {"隐藏关系", "未知观察者"}


class ContinuityTest(unittest.TestCase):
    def test_forbidden_reveals_dedup(self):
        state = make_state()
        forbidden = state.forbidden_reveals("林")
        self.assertEqual(len(forbidden), len(set(forbidden)))
        self.assertIn("父亲签下了掩盖命令", forbidden)

    def test_surprise_filters_inapplicable_categories(self):
        engine = SurpriseEngine(random.Random(3))
        # no facts, no motifs -> only generic categories are applicable
        results = engine.mutate(1.0, StoryState(), has_motifs=False, motifs=[])
        self.assertTrue(results)
        self.assertTrue(all(s.category in GENERIC_ONLY for s in results))

    def test_surprise_uses_fact_target_when_present(self):
        state = make_state()
        engine = SurpriseEngine(random.Random(11))
        results = engine.mutate(1.0, state, has_motifs=True, motifs=["蒸汽"])
        # every category that needs facts must reference a real fact statement
        for s in results:
            if s.category in {"错误记忆", "反向因果", "时间错位"}:
                self.assertIn(s.target, state.protected_statements())

    def test_evaluator_flags_premature_reveal(self):
        state = make_state()
        evaluator = Evaluator(make_theme(), make_character(), make_harmony(),
                              story_state=state)
        text = "档案里写着：父亲签下了掩盖命令。林合上文件。"
        eva = evaluator.evaluate(text)
        self.assertLess(eva.signals["continuity"], 1.0)
        self.assertTrue(any("提前揭露" in n for n in eva.listening))

    def test_clean_text_has_full_continuity(self):
        evaluator = Evaluator(make_theme(), make_character(), make_harmony(),
                              story_state=make_state())
        eva = evaluator.evaluate("林站在蒸汽里，什么都没有说。")
        self.assertEqual(eva.signals["continuity"], 1.0)


if __name__ == "__main__":
    unittest.main()
