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
    ) -> List[Take]:
        """Return one take per requested style (defaults to a curated trio).

        All takes share the same ``cue`` — same changes, different solo color —
        exactly like recording several takes over the same chord progression.
        """
        chosen = styles or ["冷静观察", "象征增强", "心理深入"]
        takes: List[Take] = []
        for style in chosen:
            for _ in range(max(1, per_style)):
                takes.append(
                    self.composer.compose(
                        scene, mode=mode, style=style, context=context, cue=cue
                    )
                )
        return takes

    @staticmethod
    def available_styles() -> List[str]:
        return list(STYLES.keys())
