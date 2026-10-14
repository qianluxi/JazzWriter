import unittest

from engine.evaluator import Evaluation
from feedback.conductor import Conductor
from improvisation.improvisation_score import params_for_mode
from tests.helpers import make_character, make_theme

PARAMS = ["creativity", "randomness", "motif_reuse",
          "character_freedom", "surprise_level", "style_distance"]


def _eval(theme=0.8, character=0.8, novelty=0.8, emotion=0.8, motif=0.8, harmony=1.0):
    m = {"theme": theme, "character": character, "emotion": emotion,
         "motif": motif, "novelty": novelty, "harmony": harmony}
    return Evaluation(metrics=m, overall=sum(m.values()) / len(m), grade="B")


class FeedbackTest(unittest.TestCase):
    def setUp(self):
        self.theme = make_theme()
        self.character = make_character()

    def test_low_novelty_raises_randomness(self):
        params = params_for_mode("classic_jazz")
        advice = Conductor().advise("x", self.theme, self.character, params,
                                    evaluation=_eval(novelty=0.1))
        self.assertGreater(advice.suggested.randomness, params.randomness)

    def test_low_theme_lowers_freedom(self):
        params = params_for_mode("free_jazz")
        advice = Conductor().advise("x", self.theme, self.character, params,
                                    evaluation=_eval(theme=0.2))
        self.assertLess(advice.suggested.character_freedom, params.character_freedom)

    def test_bounds_never_exceeded(self):
        params = params_for_mode("free_jazz")
        params.creativity = 0.98
        advice = Conductor().advise("x", self.theme, self.character, params,
                                    evaluation=_eval(novelty=0.1, theme=0.1))
        for key in PARAMS:
            value = getattr(advice.suggested, key)
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)


if __name__ == "__main__":
    unittest.main()
