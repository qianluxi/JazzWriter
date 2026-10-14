"""Variation — several takes of the same solo, like multiple recording takes."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from core.improviser import STYLES, HarmonyContext
from engine.composer import Composer, Take

if TYPE_CHECKING:
    from improvisation.improvisation_score import Cue


class Variation:
    def __init__(self, composer: Composer) -> None:
        self.composer = composer

    def generate(
        self,
        scene: str,
        *,
        styles: Optional[List[str]] = None,
        mode: str = "classic_jazz",
        context: Optional[HarmonyContext] = None,
        per_style: int = 1,
        cue: Optional["Cue"] = None,
        cues: Optional[List["Cue"]] = None,
    ) -> List[Take]:
        """Return takes for the requested styles.

        Mode A (default): all takes share the same ``cue`` — same changes,
        different solo color, like several takes over one chord progression.

        Mode B (``cues`` given): each take gets its *own* cue — the same theme
        improvised down different paths, opening genuinely different directions.
        """
        chosen = styles or ["冷静观察", "象征增强", "心理深入"]
        takes: List[Take] = []
        index = 0
        for style in chosen:
            for _ in range(max(1, per_style)):
                take_cue = cue
                if cues:
                    take_cue = cues[index % len(cues)]
                takes.append(
                    self.composer.compose(
                        scene, mode=mode, style=style, context=context, cue=take_cue
                    )
                )
                index += 1
        return takes

    @staticmethod
    def available_styles() -> List[str]:
        return list(STYLES.keys())
