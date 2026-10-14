"""Improviser — the soloist's brief.

It combines the fixed material (theme / character / harmony / motifs) with the
live environment (scene) and the conductor's *cue* (how far to travel from the
theme) into a single, constraint-dense prompt. The point is *controlled*
creation: alive enough to surprise, tight enough to stay in key.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional

from core.character import Character
from core.harmony import Harmony
from core.motif import MotifLibrary
from core.theme import Theme

if TYPE_CHECKING:  # avoid a hard import cycle at runtime
    from improvisation.improvisation_score import Cue

# Narrative improvisation modes (aligned with the jazz parameter presets) ------
MODES: Dict[str, str] = {
    "classic_jazz": (
        "标准爵士：先陈述主题动机 → 变奏 → 制造冲突 → 回归主题（但已被改变）。"
        "节奏从容，靠细节与潜台词推进。"
    ),
    "bebop": (
        "Bebop：高速、信息密度高、多线索并进、短句切分。"
        "适合悬疑/侦探，允许偶发性的锋利转折。"
    ),
    "free_jazz": (
        "自由爵士：非线性、重象征、留白、反情节。"
        "允许时间跳跃与感官碎片，情绪先于逻辑。"
    ),
}
MODE_ALIASES = {
    "classic": "classic_jazz",
    "standard": "classic_jazz",
    "swing": "classic_jazz",
    "free": "free_jazz",
}

# Solo "colors" used to generate alternative takes ----------------------------
STYLES: Dict[str, str] = {
    "现实主义": "以物质细节与可验证的观察推进，克制比喻。",
    "冷静观察": "近乎病理学式的冷静，叙述者不加评判，只记录。",
    "象征增强": "让核心象征承担更多表意，物象反复变奏。",
    "心理深入": "贴近意识流动，放大犹疑、记忆与自我欺骗。",
    "冷峻": "短句、少形容词、留白多，情绪压在冰面下。",
    "抒情": "让节奏舒展，允许一处真正柔软的时刻。",
}


def canonical_mode(mode: str) -> str:
    return MODE_ALIASES.get(mode, mode)


@dataclass
class HarmonyContext:
    """Everything the soloist needs to know about *when* it is playing."""

    chapter: int = 1
    total_chapters: int = 1
    pov: Optional[str] = None
    previous_summary: str = ""
    active_motifs: List[str] = field(default_factory=list)
    position: Optional[float] = None

    def resolved_position(self) -> float:
        if self.position is not None:
            return self.position
        if self.total_chapters <= 1:
            return 0.0
        return (self.chapter - 1) / (self.total_chapters - 1)


class Improviser:
    def __init__(
        self,
        theme: Theme,
        character: Character,
        harmony: Harmony,
        motifs: Optional[MotifLibrary] = None,
    ) -> None:
        self.theme = theme
        self.character = character
        self.harmony = harmony
        self.motifs = motifs or MotifLibrary()

    # -- prompt construction ------------------------------------------------
    def create_prompt(
        self,
        scene: str,
        *,
        mode: str = "classic_jazz",
        style: str = "现实主义",
        context: Optional[HarmonyContext] = None,
        extra_instructions: str = "",
        cue: Optional["Cue"] = None,
    ) -> str:
        mode = canonical_mode(mode)
        ctx = context or HarmonyContext()
        mode_text = MODES.get(mode, MODES["classic_jazz"])
        style_text = STYLES.get(style, style)
        point = self.harmony.curve_hint(ctx.resolved_position())

        sections = [
            "你是一名爵士式小说即兴演奏者。你不是打字机，而是一位乐队成员："
            "在既定主题、和声与节奏中即兴，同时保持自己的判断与克制。",
            "",
            "【主题旋律 Theme】",
            self.theme.as_prompt(),
            "",
            "【人物 Solo】",
            self.character.as_prompt(),
            "",
            "【叙事和声 Harmony】",
            self.harmony.as_prompt(),
        ]

        if point:
            sections += ["", f"【本章情绪坐标】{point}（沿情绪和声进行定位）"]

        sections += [
            "",
            f"【即兴模式】{mode} — {mode_text}",
            f"【本 Take 的色彩】{style} — {style_text}",
        ]

        if ctx.chapter:
            total = f"/{ctx.total_chapters}" if ctx.total_chapters else ""
            sections.append(f"【位置】第 {ctx.chapter}{total} 章")
        if ctx.pov:
            sections.append(f"【视角 POV】{ctx.pov}")

        if self.motifs.all():
            sections += ["", "【动机复用 Motif（需变奏，不可原样重复）】", self.motifs.as_prompt(ctx.active_motifs or None)]

        if cue is not None:
            sections += ["", "【即兴决策 · Jazz Cue（本次演奏的乐谱）】", cue.directives()]

        if ctx.previous_summary:
            sections += ["", "【上文回顾（保持连续性，不要复述）】", ctx.previous_summary]

        sections += [
            "",
            "【场景 Scene】",
            scene.strip(),
            "",
            "【写作规则】",
            "1. 绝不直接解释主题，只能通过细节让它被听见。",
            "2. 人物行动必须出自其欲望/恐惧/世界观，而非情节需要。",
            "3. 每个核心动机出现时给出新的意义，不作同义复读。",
            "4. 保留未知空间：不必把所有信息都给全。",
            "5. 像一个乐手那样控制信息释放的节奏与叙述距离。",
            "6. 禁用陈词滥调与空洞修辞（如“心潮澎湃”“五味杂陈”）。",
            "7. 不使用小标题或解释性括号，直接写正文。",
        ]

        if extra_instructions:
            sections += ["", "【额外指令】", extra_instructions.strip()]

        sections += [
            "",
            "现在即兴演奏这一段。只输出小说正文，长度约 500–900 字。",
        ]
        return "\n".join(sections)

    # -- structured context for providers (mock generation, logging) --------
    def build_context(
        self,
        scene: str,
        *,
        mode: str = "classic_jazz",
        style: str = "现实主义",
        context: Optional[HarmonyContext] = None,
        cue: Optional["Cue"] = None,
    ) -> Dict[str, object]:
        mode = canonical_mode(mode)
        ctx = context or HarmonyContext()
        data: Dict[str, object] = {
            "scene": scene.strip(),
            "mode": mode,
            "style": style,
            "chapter": ctx.chapter,
            "pov": ctx.pov or self.character.name,
            "point": self.harmony.curve_hint(ctx.resolved_position()),
            "theme": self.theme.to_dict(),
            "character": self.character.to_dict(),
            "harmony": self.harmony.to_dict(),
            "motifs": [m.name for m in self.motifs.all()],
            "active_motifs": ctx.active_motifs or self.motifs.names(),
        }
        if cue is not None:
            data["cue"] = cue.to_dict()
        return data
