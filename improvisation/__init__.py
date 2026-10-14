"""Improvisation layer — Controlled Divergence.

The band does not play random notes. It improvises inside the changes. This
package decides *how far* a take may travel from the theme, and in which
dimension: color (seed), motif mutation, surprise, rhythm, and solo voice.
"""

from improvisation.improvisation_score import (
    Cue,
    ImprovisationScore,
    JazzParams,
    MODES,
    params_for_mode,
)
from improvisation.randomizer import JazzSeed, Randomizer
from improvisation.motif_engine import MotifEngine, MotifVariation
from improvisation.surprise_engine import Surprise, SurpriseEngine
from improvisation.rhythm_engine import Rhythm, RhythmEngine
from improvisation.solo_engine import CharacterSolo, SoloStyle

__all__ = [
    "Cue",
    "ImprovisationScore",
    "JazzParams",
    "MODES",
    "params_for_mode",
    "JazzSeed",
    "Randomizer",
    "MotifEngine",
    "MotifVariation",
    "Surprise",
    "SurpriseEngine",
    "Rhythm",
    "RhythmEngine",
    "CharacterSolo",
    "SoloStyle",
]
