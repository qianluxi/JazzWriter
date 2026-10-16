"""Novel Jazz Engine — core musical-literary primitives."""

from core.theme import Theme
from core.character import Character
from core.harmony import Harmony
from core.motif import Motif, MotifLibrary
from core.improviser import Improviser, HarmonyContext
from core.relationship import Relationship, RelationshipMap

__all__ = [
    "Theme",
    "Character",
    "Harmony",
    "Motif",
    "MotifLibrary",
    "Improviser",
    "HarmonyContext",
    "Relationship",
    "RelationshipMap",
]
