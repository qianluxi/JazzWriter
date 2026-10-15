"""Jam Session (V0.7) — sequential ensemble improvisation.

Roles do *different* work, and none of them simply rewrites the prose:

  Director → sets what this round explores and its limits
  Soloist  → proposes actions/observations from a character's own drives
  Observer → offers non-central details, ambience, edge viewpoints
  Editor   → compares, drops contradictions/premature reveals, integrates

Sequence: Director → Soloist → Observer → Editor → (Evaluator/Conductor).
"""

from jam_session.director import Director, JamBrief
from jam_session.editor import Editor, JamResult
from jam_session.observer import Observer
from jam_session.soloist import Soloist
from jam_session.orchestrator import JamSession

__all__ = [
    "Director", "JamBrief",
    "Soloist",
    "Observer",
    "Editor", "JamResult",
    "JamSession",
]
