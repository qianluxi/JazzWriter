"""Session — wires the score (data files) to a playable band."""

from __future__ import annotations

import dataclasses
import datetime as _dt
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.character import Character
from core.harmony import Harmony
from core.improviser import HarmonyContext, Improviser, canonical_mode
from core.motif import MotifLibrary
from core.story_state import StoryState
from core.theme import Theme
from engine.composer import Composer, Take
from engine.evaluator import Evaluation, Evaluator
from engine.scene_planner import ScenePlanner, SceneSkeleton
from engine.variation import Variation
from feedback.conductor import Advice, Conductor
from improvisation.improvisation_score import Cue, ImprovisationScore, JazzParams, params_for_mode
from llm import get_provider
from llm.base import LLMProvider
from store import (
    DATA_DIR,
    load_characters,
    load_jazz,
    load_jazz_state,
    load_motifs,
    load_story,
    load_story_state,
    save_jazz_state,
    save_motifs,
    save_run,
    append_advice,
    load_runs,
)


class Session:
    def __init__(
        self,
        theme: Theme,
        harmony: Harmony,
        characters: Dict[str, Character],
        motifs: MotifLibrary,
        provider: Optional[LLMProvider] = None,
        provider_name: str = "mock",
        jazz: Optional[JazzParams] = None,
        story_state: Optional[StoryState] = None,
        eval_mode: str = "lexical",
    ) -> None:
        self.theme = theme
        self.harmony = harmony
        self.characters = characters
        self.motifs = motifs
        self.provider = provider or get_provider(provider_name)
        self.provider_name = getattr(self.provider, "name", provider_name)
        self.jazz = jazz or JazzParams()
        self.story_state = story_state or StoryState()
        self.eval_mode = eval_mode

    # -- construction -------------------------------------------------------
    @classmethod
    def load(
        cls,
        data_dir: Optional[Path] = None,
        provider: Optional[str] = None,
        eval_mode: str = "lexical",
        **provider_kwargs,
    ) -> "Session":
        base = Path(data_dir) if data_dir else DATA_DIR
        theme, harmony = load_story(base / "story.yaml")
        characters = load_characters(base / "characters.yaml")
        motifs = load_motifs(base / "motifs.yaml")
        motifs.ensure(theme.motifs)
        state = load_story_state(base / "story_state.yaml")
        # runtime state (jazz_state.yaml) wins over author default (story.yaml)
        runtime = load_jazz_state(base / "jazz_state.yaml")
        jazz = JazzParams.from_dict(runtime) if runtime else JazzParams.from_dict(load_jazz(base / "story.yaml"))
        resolved = get_provider(provider, **provider_kwargs)
        return cls(
            theme, harmony, characters, motifs,
            provider=resolved,
            provider_name=getattr(resolved, "name", provider or "mock"),
            jazz=jazz,
            story_state=state,
            eval_mode=eval_mode,
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
        return Improviser(
            self.theme, self.character(pov), self.harmony, self.motifs,
            story_state=self.story_state,
        )

    def composer(self, pov: Optional[str] = None) -> Composer:
        return Composer(self.provider, self.improviser(pov), self.harmony)

    def evaluator(self, pov: Optional[str] = None) -> Evaluator:
        return Evaluator(
            self.theme, self.character(pov), self.harmony, self.motifs,
            story_state=self.story_state, eval_mode=self.eval_mode,
        )

    # -- jazz parameters ----------------------------------------------------
    def effective_params(
        self,
        jazz_mode: Optional[str] = None,
        seed: Optional[int] = None,
        overrides: Optional[Dict[str, float]] = None,
    ) -> JazzParams:
        if jazz_mode:
            params = params_for_mode(jazz_mode)
        else:
            params = dataclasses.replace(self.jazz)
        for key, value in (overrides or {}).items():
            if value is not None and hasattr(params, key):
                setattr(params, key, float(value))
        if seed is not None:
            params.seed = int(seed)
        return params

    def roll_cue(
        self,
        pov: Optional[str] = None,
        *,
        jazz_mode: Optional[str] = None,
        seed: Optional[int] = None,
        overrides: Optional[Dict[str, float]] = None,
        chapter: int = 1,
        used_surprises: Optional[List[str]] = None,
    ) -> Cue:
        params = self.effective_params(jazz_mode, seed, overrides)
        score = ImprovisationScore(
            params, self.theme, self.character(pov), self.motifs,
            story_state=self.story_state,
        )
        return score.roll(chapter=chapter, used_surprises=used_surprises)

    # -- playing ------------------------------------------------------------
    def play(
        self,
        scene: str,
        *,
        pov: Optional[str] = None,
        style: str = "现实主义",
        chapter: int = 1,
        total_chapters: int = 1,
        previous_summary: str = "",
        extra_instructions: str = "",
        active_motifs: Optional[List[str]] = None,
        jazz_mode: Optional[str] = None,
        seed: Optional[int] = None,
        overrides: Optional[Dict[str, float]] = None,
        cue: Optional[Cue] = None,
        previous_texts: Optional[List[str]] = None,
        record: bool = True,
    ) -> Tuple[Take, Evaluation]:
        character = self.character(pov)
        cue = cue or self.roll_cue(pov, jazz_mode=jazz_mode, seed=seed,
                                   overrides=overrides, chapter=chapter)
        mode = canonical_mode(cue.mode)
        ctx = HarmonyContext(
            chapter=chapter, total_chapters=total_chapters, pov=character.name,
            previous_summary=previous_summary, active_motifs=active_motifs or [],
        )
        take = self.composer(pov).compose(
            scene, mode=mode, style=style, context=ctx,
            extra_instructions=extra_instructions, cue=cue,
        )
        evaluation = self.evaluator(pov).evaluate(
            take.text, take=take, previous_texts=previous_texts
        )
        if record:
            self._record_run(take, evaluation, cue, scene, pov=pov)
        return take, evaluation

    def variations(
        self,
        scene: str,
        *,
        pov: Optional[str] = None,
        styles: Optional[List[str]] = None,
        chapter: int = 1,
        total_chapters: int = 1,
        jazz_mode: Optional[str] = None,
        seed: Optional[int] = None,
        overrides: Optional[Dict[str, float]] = None,
        explore: bool = False,
    ) -> List[Tuple[Take, Evaluation]]:
        character = self.character(pov)
        chosen = styles or ["冷静观察", "象征增强", "心理深入"]
        evaluator = self.evaluator(pov)
        results: List[Tuple[Take, Evaluation]] = []

        if explore:
            # Mode B: one independent cue per take -> different narrative paths
            cue_list = [
                self.roll_cue(pov, jazz_mode=jazz_mode, seed=(None if seed is None else seed + i),
                              overrides=overrides, chapter=chapter)
                for i in range(len(chosen))
            ]
        else:
            cue_list = None

        shared_cue = None if explore else self.roll_cue(
            pov, jazz_mode=jazz_mode, seed=seed, overrides=overrides, chapter=chapter)

        takes = Variation(self.composer(pov)).generate(
            scene, styles=chosen, mode=(cue_list[0].mode if cue_list else shared_cue.mode),
            context=HarmonyContext(chapter=chapter, total_chapters=total_chapters, pov=character.name),
            cue=shared_cue, cues=cue_list,
        )
        for take in takes:
            evaluation = evaluator.evaluate(take.text, take=take)
            if explore:
                self._record_run(take, evaluation, cue_list[len(results)], scene, pov=pov)
            else:
                self._record_run(take, evaluation, shared_cue, scene, pov=pov)
            results.append((take, evaluation))
        return results

    # -- run records --------------------------------------------------------
    def _record_run(self, take: Take, evaluation: Evaluation, cue: Cue,
                    scene: str, pov: Optional[str] = None) -> None:
        created = take.created_at or _dt.datetime.now().isoformat(timespec="seconds")
        run_id = self._run_id(take.chapter, cue.seed_int, created, take.style)
        advice = self.advise(take, evaluation, pov=pov).to_dict()
        record = {
            "run_id": run_id,
            "chapter": take.chapter,
            "seed": cue.seed_int,
            "mode": take.mode,
            "style": take.style,
            "pov": take.pov,
            "cue": cue.to_dict(),
            "cue_directives": cue.directives(),
            "prompt": take.prompt,
            "scene": scene,
            "context": take.context,
            "take": {"text": take.text, "harmony_violations": take.harmony_violations},
            "evaluation": evaluation.as_dict(),
            "conductor_advice": advice,
            "provider": take.provider,
            "created_at": created,
        }
        save_run(record)
        append_advice({
            "run_id": run_id, "chapter": take.chapter, "mode": take.mode,
            "created_at": created, "notes": advice["notes"],
            "deltas": advice["deltas"],
            "before": cue.params.to_dict(),
            "after": advice["suggested"], "applied": False,
        })

    @staticmethod
    def _run_id(chapter: int, seed_int: int, created: str, style: str) -> str:
        stamp = created.replace("-", "").replace(":", "").replace("T", "").replace(" ", "")
        tag = hashlib.md5(f"{style}|{seed_int}".encode("utf-8")).hexdigest()[:6]
        return f"ch{chapter:03d}_{stamp}_{seed_int:08x}_{tag}"

    def recent_texts(self, limit: int = 5) -> List[str]:
        records = load_runs()
        texts = [r.get("take", {}).get("text", "") for r in records]
        return [t for t in texts if t][-limit:]

    # -- listen-back & retune ----------------------------------------------
    def advise(self, take: Take, evaluation: Evaluation, *, pov: Optional[str] = None) -> Advice:
        params = self.effective_params(jazz_mode=take.mode)
        return Conductor().advise(
            take.text, self.theme, self.character(pov or take.pov), params,
            evaluation=evaluation,
        )

    def apply_advice(self, advice: Advice, *, run_id: str = "", note: str = "") -> Path:
        """Persist the suggested params as the runtime jazz_state.yaml."""
        self.jazz = advice.suggested
        path = save_jazz_state(advice.suggested.to_dict())
        append_advice({
            "run_id": run_id, "applied": True, "created_at":
                _dt.datetime.now().isoformat(timespec="seconds"),
            "after": advice.suggested.to_dict(), "note": note,
        })
        return path

    # -- next-scene planning -----------------------------------------------
    def plan(
        self,
        take: Optional[Take] = None,
        evaluation: Optional[Evaluation] = None,
        *,
        count: int = 3,
        seed: Optional[int] = None,
    ) -> List[SceneSkeleton]:
        planner = ScenePlanner(self.theme, self.characters, self.motifs, self.story_state)
        return planner.plan(take, evaluation, count=count, seed=seed)

    # -- motif bookkeeping --------------------------------------------------
    def record_motifs(self, take: Take) -> None:
        point = take.context.get("point", "") if take.context else ""
        for motif in self.motifs.all():
            if motif.name and motif.name in take.text:
                self.motifs.add_usage(
                    motif.name, take.chapter,
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
