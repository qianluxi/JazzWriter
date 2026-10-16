"""Orchestrator — runs the sequential jam: Director → Soloist → Observer → Editor."""

from __future__ import annotations

from typing import Dict, List, Optional

from core.character import Character
from core.motif import MotifLibrary
from core.story_state import StoryState
from core.theme import Theme
from jam_session.director import Director, JamBrief
from jam_session.editor import Editor, JamResult
from jam_session.observer import Observer
from jam_session.soloist import Soloist


class JamSession:
    def __init__(
        self,
        theme: Theme,
        characters: Dict[str, Character],
        *,
        book=None,
        story_state: Optional[StoryState] = None,
        motifs: Optional[MotifLibrary] = None,
        llm=None,
    ) -> None:
        self.theme = theme
        self.characters = characters
        self.book = book
        self.story_state = story_state
        self.motifs = motifs
        self.llm = llm

    def _character(self, pov: Optional[str]) -> Character:
        if pov:
            if pov in self.characters:
                return self.characters[pov]
            for c in self.characters.values():
                if c.name == pov or c.effective_id == pov:
                    return c
        if self.characters:
            return next(iter(self.characters.values()))
        return Character(name=pov or "主角")

    def run(self, scene: str, *, pov: Optional[str] = None,
            chapter_number: Optional[int] = None, rounds: int = 2) -> JamResult:
        character = self._character(pov)

        chapter = None
        if self.book is not None and chapter_number is not None:
            chapter = self.book.chapter(chapter_number)

        brief: JamBrief = Director().run(
            scene, pov=character.name, book=self.book, chapter=chapter, llm=self.llm)

        solo: List[str] = Soloist().run(
            brief, character, story_state=self.story_state, llm=self.llm)

        motif_names = self.motifs.names() if self.motifs else list(self.theme.motifs)
        observer: List[str] = Observer().run(
            brief, story_state=self.story_state, motifs=motif_names, llm=self.llm)

        debate: List[dict] = []
        if rounds >= 2:
            rebuttals = Observer().rebut(solo, brief, self.llm)
            for r in rebuttals:
                debate.append({"round": 2, "actor": "observer", "content": r})
            solo = Soloist().respond(rebuttals, character, solo, self.llm)
            for r in solo:
                debate.append({"round": 2, "actor": "soloist", "content": r})

        result: JamResult = Editor().run(
            brief, solo, observer, story_state=self.story_state, llm=self.llm,
            rebuttals=debate, rounds=rounds)
        return result
