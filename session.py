"""Session — wires the score (data files) to a playable band."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.character import Character
from core.harmony import Harmony
from core.improviser import HarmonyContext, Improviser
from core.motif import MotifLibrary
from core.theme import Theme
from engine.composer import Composer, Take
from engine.evaluator import Evaluation, Evaluator
from engine.variation import Variation
from llm import get_provider
from llm.base import LLMProvider
from store import DATA_DIR, load_characters, load_motifs, load_story, save_motifs


class Session:
    def __init__(
        self,
        theme: Theme,
        harmony: Harmony,
        characters: Dict[str, Character],
        motifs: MotifLibrary,
        provider: Optional[LLMProvider] = None,
        provider_name: str = "mock",
    ) -> None:
        self.theme = theme
        self.harmony = harmony
        self.characters = characters
        self.motifs = motifs
        self.provider = provider or get_provider(provider_name)
        self.provider_name = getattr(self.provider, "name", provider_name)

    # -- construction -------------------------------------------------------
    @classmethod
    def load(
        cls,
        data_dir: Optional[Path] = None,
        provider: Optional[str] = None,
        **provider_kwargs,
    ) -> "Session":
        base = Path(data_dir) if data_dir else DATA_DIR
        theme, harmony = load_story(base / "story.yaml")
        characters = load_characters(base / "characters.yaml")
        motifs = load_motifs(base / "motifs.yaml")
        motifs.ensure(theme.motifs)
        resolved = get_provider(provider, **provider_kwargs)
        return cls(
            theme,
            harmony,
            characters,
            motifs,
            provider=resolved,
            provider_name=getattr(resolved, "name", provider or "mock"),
        )

    def character(self, name: Optional[str] = None) -> Character:
        if not self.characters:
            raise ValueError("no characters defined in data/characters.yaml")
        if name is None:
            return next(iter(self.characters.values()))
        if name in self.characters:
            return self.characters[name]
        lowered = name.strip().lower()
        for character in self.characters.values():
            if character.name.lower() == lowered:
                return character
        raise KeyError(f"unknown character: {name}")

    # -- assembly -----------------------------------------------------------
    def improviser(self, pov: Optional[str] = None) -> Improviser:
        return Improviser(self.theme, self.character(pov), self.harmony, self.motifs)

    def composer(self, pov: Optional[str] = None) -> Composer:
        return Composer(self.provider, self.improviser(pov), self.harmony)

    def evaluator(self, pov: Optional[str] = None) -> Evaluator:
        return Evaluator(self.theme, self.character(pov), self.harmony, self.motifs)

    # -- playing ------------------------------------------------------------
    def play(
        self,
        scene: str,
        *,
        pov: Optional[str] = None,
        mode: str = "classic",
        style: str = "现实主义",
        chapter: int = 1,
        total_chapters: int = 1,
        previous_summary: str = "",
        extra_instructions: str = "",
        active_motifs: Optional[List[str]] = None,
    ) -> Tuple[Take, Evaluation]:
        character = self.character(pov)
        ctx = HarmonyContext(
            chapter=chapter,
            total_chapters=total_chapters,
            pov=character.name,
            previous_summary=previous_summary,
            active_motifs=active_motifs or [],
        )
        take = self.composer(pov).compose(
            scene,
            mode=mode,
            style=style,
            context=ctx,
            extra_instructions=extra_instructions,
        )
        evaluation = self.evaluator(pov).evaluate(take.text, take=take)
        return take, evaluation

    def variations(
        self,
        scene: str,
        *,
        pov: Optional[str] = None,
        mode: str = "classic",
        styles: Optional[List[str]] = None,
        chapter: int = 1,
        total_chapters: int = 1,
    ) -> List[Tuple[Take, Evaluation]]:
        character = self.character(pov)
        ctx = HarmonyContext(
            chapter=chapter, total_chapters=total_chapters, pov=character.name
        )
        takes = Variation(self.composer(pov)).generate(
            scene, styles=styles, mode=mode, context=ctx
        )
        evaluator = self.evaluator(pov)
        return [(t, evaluator.evaluate(t.text, take=t)) for t in takes]

    # -- motif bookkeeping --------------------------------------------------
    def record_motifs(self, take: Take) -> None:
        point = take.context.get("point", "") if take.context else ""
        for motif in self.motifs.all():
            if motif.name and motif.name in take.text:
                self.motifs.add_usage(
                    motif.name,
                    take.chapter,
                    meaning=point or take.style,
                    quote=self._quote(take.text, motif.name),
                )

    def persist_motifs(self) -> Path:
        return save_motifs(self.motifs)

    @staticmethod
    def _quote(text: str, needle: str, span: int = 18) -> str:
        idx = text.find(needle)
        if idx < 0:
            return ""
        start = max(0, idx - span)
        end = min(len(text), idx + len(needle) + span)
        return text[start:end].replace("\n", " ")
