"""Variation — several takes of the same solo, like multiple recording takes."""

from __future__ import annotations

from typing import List, Optional

from core.improviser import STYLES, HarmonyContext
from engine.composer import Composer, Take


class Variation:
    def __init__(self, composer: Composer) -> None:
        self.composer = composer

    def generate(
        self,
        scene: str,
        *,
        styles: Optional[List[str]] = None,
        mode: str = "classic",
        context: Optional[HarmonyContext] = None,
        per_style: int = 1,
    ) -> List[Take]:
        """Return one take per requested style (defaults to a curated trio)."""
        chosen = styles or ["冷静观察", "象征增强", "心理深入"]
        takes: List[Take] = []
        for style in chosen:
            for _ in range(max(1, per_style)):
                takes.append(
                    self.composer.compose(
                        scene, mode=mode, style=style, context=context
                    )
                )
        return takes

    @staticmethod
    def available_styles() -> List[str]:
        return list(STYLES.keys())
