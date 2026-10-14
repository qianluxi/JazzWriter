"""Improvisation Score — the conductor's chart.

This is the heart of Controlled Divergence. For each take it *deals* a Cue:
how much to stay in the theme vs. how far to travel, which color, which motif
mutations, which surprises, which rhythmic feel, which solo voice.

Directly mirrors the expert's proposed jazz parameters.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.character import Character
from core.motif import MotifLibrary
from core.theme import Theme
from improvisation.motif_engine import MotifEngine, MotifVariation
from improvisation.randomizer import JazzSeed, Randomizer
from improvisation.rhythm_engine import Rhythm, RhythmEngine
from improvisation.solo_engine import CharacterSolo, SoloStyle
from improvisation.surprise_engine import Surprise, SurpriseEngine


@dataclass
class JazzParams:
    mode: str = "classic_jazz"
    creativity: float = 0.5        # 创造程度
    randomness: float = 0.4        # 随机扰动
    motif_reuse: float = 0.8       # 主题重复
    character_freedom: float = 0.6  # 人物自主性
    surprise_level: float = 0.5    # 剧情转折
    style_distance: float = 0.3    # 语言变化
    seed: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "creativity": self.creativity,
            "randomness": self.randomness,
            "motif_reuse": self.motif_reuse,
            "character_freedom": self.character_freedom,
            "surprise_level": self.surprise_level,
            "style_distance": self.style_distance,
            "seed": self.seed,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "JazzParams":
        data = dict(data or {})
        mode = data.pop("mode", "classic_jazz")
        base = params_for_mode(mode)
        for key, value in data.items():
            if hasattr(base, key):
                setattr(base, key, value)
        return base


MODE_PRESETS: Dict[str, Dict[str, float]] = {
    # 主题 ~90% / 创新 ~10%
    "classic_jazz": dict(creativity=0.25, randomness=0.15, motif_reuse=0.9,
                         character_freedom=0.35, surprise_level=0.15, style_distance=0.15),
    # 主题 ~70% / 创新 ~30%
    "bebop": dict(creativity=0.6, randomness=0.45, motif_reuse=0.75,
                  character_freedom=0.6, surprise_level=0.5, style_distance=0.45),
    # 主题 ~50% / 创新 ~50%
    "free_jazz": dict(creativity=0.85, randomness=0.7, motif_reuse=0.5,
                      character_freedom=0.85, surprise_level=0.7, style_distance=0.8),
}
MODE_ALIASES = {
    "classic": "classic_jazz",
    "jazz": "classic_jazz",
    "standard": "classic_jazz",
    "swing": "classic_jazz",
    "free": "free_jazz",
}
MODES = list(MODE_PRESETS.keys())


def params_for_mode(mode: str, **overrides) -> JazzParams:
    key = MODE_ALIASES.get(mode, mode)
    if key not in MODE_PRESETS:
        raise KeyError(f"unknown jazz mode: {mode!r} (use {', '.join(MODES)})")
    preset = dict(MODE_PRESETS[key])
    preset.update({k: v for k, v in overrides.items() if v is not None})
    return JazzParams(mode=key, **preset)


@dataclass
class Cue:
    mode: str
    params: JazzParams
    seed_int: int
    jazz_seed: JazzSeed
    motifs: List[MotifVariation] = field(default_factory=list)
    surprises: List[Surprise] = field(default_factory=list)
    rhythm: Optional[Rhythm] = None
    solo: Optional[SoloStyle] = None

    def directives(self) -> str:
        lines: List[str] = [f"模式: {self.mode}（随机种子 {self.seed_int}）"]
        if self.jazz_seed:
            lines.append("色彩: " + self.jazz_seed.describe())
        if self.rhythm:
            lines.append("节奏: " + self.rhythm.describe())
        if self.solo:
            lines.append("独奏: " + self.solo.describe())
        if self.motifs:
            lines.append("动机变奏:")
            lines.extend("  - " + m.directive() for m in self.motifs)
        if self.surprises:
            lines.append("受控意外（须自然融入，不可生硬）:")
            lines.extend("  - " + s.directive() for s in self.surprises)
        else:
            lines.append("受控意外: 无（保持稳定，靠细节推进）")

        free = self.params.character_freedom
        if free >= 0.6:
            lines.append("人物自主性: 高 — 允许人物越过情节预设，依自身欲望行动，甚至可以违逆作者安排。")
        elif free <= 0.35:
            lines.append("人物自主性: 低 — 人物须服从既定情节与主题，不得越轨。")
        dist = self.params.style_distance
        if dist >= 0.6:
            lines.append("语言距离: 大 — 允许明显的陌生化、非常规句法与叙述跳跃。")
        elif dist <= 0.25:
            lines.append("语言距离: 小 — 贴近常规叙述，克制修辞，避免炫技。")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "seed_int": self.seed_int,
            "params": self.params.to_dict(),
            "jazz_seed": self.jazz_seed.to_dict() if self.jazz_seed else {},
            "motifs": [m.to_dict() for m in self.motifs],
            "surprises": [s.to_dict() for s in self.surprises],
            "rhythm": self.rhythm.to_dict() if self.rhythm else {},
            "solo": self.solo.to_dict() if self.solo else {},
        }


class ImprovisationScore:
    def __init__(
        self,
        params: JazzParams,
        theme: Theme,
        character: Character,
        library: MotifLibrary,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.params = params
        self.theme = theme
        self.character = character
        self.library = library
        self.seed_int = params.seed if params.seed is not None else random.SystemRandom().randint(1, 2**31 - 1)
        self.rng = rng or random.Random(self.seed_int)

    def roll(self, chapter: int = 1) -> Cue:
        p = self.params
        randomizer = Randomizer(self.rng)
        jazz_seed = randomizer.seed(
            level=p.randomness,
            emotions=self.theme.emotions,
            perspectives=(),
            symbols=self.theme.symbols + self.theme.motifs,
            angle_chance=p.randomness * 0.6,
        )
        motif_engine = MotifEngine(self.library, reuse=p.motif_reuse, rng=self.rng)
        rhythm = RhythmEngine(self.rng).choose(mode=p.mode, creativity=p.creativity)
        solo = CharacterSolo().generate_style(self.character)
        surprises = SurpriseEngine(self.rng).mutate(p.surprise_level)

        return Cue(
            mode=p.mode,
            params=p,
            seed_int=self.seed_int,
            jazz_seed=jazz_seed,
            motifs=motif_engine.plan(chapter=chapter),
            surprises=surprises,
            rhythm=rhythm,
            solo=solo,
        )
