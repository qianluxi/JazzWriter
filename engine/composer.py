"""Composer — turns a solo brief into an actual take."""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from core.harmony import Harmony
from core.improviser import HarmonyContext, Improviser
from engine.textutil import word_count
from llm.base import LLMProvider

if TYPE_CHECKING:
    from improvisation.improvisation_score import Cue


@dataclass
class Take:
    text: str
    prompt: str
    chapter: int = 1
    mode: str = "classic_jazz"
    style: str = "现实主义"
    pov: str = ""
    scene: str = ""
    provider: str = ""
    created_at: str = ""
    harmony_violations: List[str] = field(default_factory=list)
    cue: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)

    @property
    def word_count(self) -> int:
        return word_count(self.text)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "word_count": self.word_count,
            "chapter": self.chapter,
            "mode": self.mode,
            "style": self.style,
            "pov": self.pov,
            "scene": self.scene,
            "provider": self.provider,
            "created_at": self.created_at,
            "harmony_violations": self.harmony_violations,
            "cue": self.cue,
            "prompt": self.prompt,
            "context": self.context,
        }


class Composer:
    def __init__(
        self,
        llm: LLMProvider,
        improviser: Improviser,
        harmony: Optional[Harmony] = None,
    ) -> None:
        self.llm = llm
        self.improviser = improviser
        self.harmony = harmony or improviser.harmony

    def compose(
        self,
        scene: str,
        *,
        mode: str = "classic_jazz",
        style: str = "现实主义",
        context: Optional[HarmonyContext] = None,
        extra_instructions: str = "",
        temperature: float = 0.9,
        max_tokens: int = 1500,
        cue: Optional["Cue"] = None,
    ) -> Take:
        ctx = context or HarmonyContext()
        prompt = self.improviser.create_prompt(
            scene,
            mode=mode,
            style=style,
            context=ctx,
            extra_instructions=extra_instructions,
            cue=cue,
        )
        llm_context = self.improviser.build_context(
            scene, mode=mode, style=style, context=ctx, cue=cue
        )
        text = self.llm.generate(
            prompt,
            context=llm_context,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return Take(
            text=text.strip(),
            prompt=prompt,
            chapter=ctx.chapter,
            mode=mode,
            style=style,
            pov=ctx.pov or self.improviser.character.name,
            scene=scene,
            provider=getattr(self.llm, "name", "?"),
            created_at=_dt.datetime.now().isoformat(timespec="seconds"),
            harmony_violations=self.harmony.violations(text),
            cue=cue.to_dict() if cue is not None else {},
            context=llm_context,
        )
