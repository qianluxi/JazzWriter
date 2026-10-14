"""Scene planner — proposes a few next-scene skeletons.

It does not write the next chapter. It offers 2–3 explorable directions built
from the *current* story state (open threads, motifs, character arcs, the
emotional curve), so the author chooses where to improvise next. Rule-based and
reproducible; no model required.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.character import Character
from core.motif import MotifLibrary
from core.story_state import StoryState
from core.theme import Theme
from engine.composer import Take
from engine.evaluator import Evaluation
from improvisation.motif_engine import STAGE_HINT, STAGES
from improvisation.operator_engine import _BY_KEY


@dataclass
class SceneSkeleton:
    goal: str
    pov: str
    surface_action: str
    latent_conflict: str
    improv_direction: str
    motif_variation: str
    info_boundary: str
    exit_point: str
    source: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "目标": self.goal,
            "POV": self.pov,
            "表层行动": self.surface_action,
            "潜在冲突": self.latent_conflict,
            "即兴方向": self.improv_direction,
            "动机变奏": self.motif_variation,
            "信息边界": self.info_boundary,
            "退出点": self.exit_point,
            "来源": self.source,
        }


class ScenePlanner:
    def __init__(
        self,
        theme: Theme,
        characters: Dict[str, Character],
        motifs: MotifLibrary,
        story_state: Optional[StoryState] = None,
    ) -> None:
        self.theme = theme
        self.characters = list(characters.values())
        self.motifs = motifs
        self.story_state = story_state or StoryState()

    def _pov(self, rng: random.Random) -> Character:
        return rng.choice(self.characters) if self.characters else Character(name="他")

    def _boundary(self, pov_name: str) -> str:
        threads = self.story_state.open_thread_list()
        forbidden = self.story_state.forbidden_reveals(pov_name)
        parts = []
        if threads:
            parts.append("可暗示线索：" + threads[0].question)
        if forbidden:
            parts.append("不可揭露：" + "、".join(forbidden[:3]))
        return "；".join(parts) or "可以提示线索，但不必给出结论。"

    def plan(
        self,
        take: Optional[Take] = None,
        evaluation: Optional[Evaluation] = None,
        *,
        count: int = 3,
        seed: Optional[int] = None,
    ) -> List[SceneSkeleton]:
        rng = random.Random(seed if seed is not None else random.SystemRandom().randint(1, 2**31 - 1))
        skeletons: List[SceneSkeleton] = []

        # A) from an open thread — advance the inquiry
        for thread in self.story_state.open_thread_list()[:2]:
            pov = self._pov(rng)
            skeletons.append(SceneSkeleton(
                goal=f"围绕未解线索推进：{thread.question}",
                pov=pov.name,
                surface_action=f"{pov.name}试图通过一件小事靠近这条线索。",
                latent_conflict=f"{pov.desire or '查明真相'} 与 {pov.fear or '触怒他人'} 发生拉扯。",
                improv_direction="信息错位：先给现象，保留原因。",
                motif_variation=self._motif_line(),
                info_boundary=self._boundary(pov.name),
                exit_point="在答案快要浮现之前收束，保留下一步的入口。",
                source=f"线索 {thread.id}",
            ))

        # B) from a motif — mutate an image rather than the plot
        if self.motifs.all():
            pov = self._pov(rng)
            skeletons.append(SceneSkeleton(
                goal="不推进情节，只让一个核心意象发生变奏。",
                pov=pov.name,
                surface_action=f"{pov.name}与某个反复出现的意象再次相遇。",
                latent_conflict="意象唤起的记忆与人物的当前立场相冲突。",
                improv_direction="注意力转移：把焦点放在边缘的人物或物件上。",
                motif_variation=self._motif_line(),
                info_boundary=self._boundary(pov.name),
                exit_point="在意象完成一次意义偏移之后结束。",
                source="动机变奏",
            ))

        # C) off the mainline — an ordinary, quiet scene
        pov = self._pov(rng)
        op = _BY_KEY[rng.choice(["sensory_substitution", "emotional_contrast", "action_drift"])]
        skeletons.append(SceneSkeleton(
            goal="暂时离开调查主线，用日常场景暴露异常。",
            pov=pov.name,
            surface_action=f"{pov.name}做一件与主线无关的日常小事。",
            latent_conflict="平静的表面下，人物的欲望与恐惧仍在暗流。",
            improv_direction=f"{op.name}：{op.directive}",
            motif_variation=self._motif_line(),
            info_boundary=self._boundary(pov.name),
            exit_point="在读者感到不安、却说不出为什么时停下。",
            source="离题即兴",
        ))

        # D) character arc — if there is an arc to move
        for character in self.characters:
            if character.arc_from and character.arc_to:
                skeletons.append(SceneSkeleton(
                    goal=f"推进 {character.name} 的人物弧：{character.arc_from} → {character.arc_to}",
                    pov=character.name,
                    surface_action=f"{character.name}面临一次考验其世界观的选择。",
                    latent_conflict=f"{character.contradiction or '内在矛盾'}被推到台前。",
                    improv_direction="行动偏航：让人物做出一个计划外、但符合其欲望的选择。",
                    motif_variation=self._motif_line(),
                    info_boundary=self._boundary(character.name),
                    exit_point="在人物做出选择、但尚未承担后果时结束。",
                    source="人物弧",
                ))
                break

        rng.shuffle(skeletons)
        return skeletons[:count]

    def _motif_line(self) -> str:
        motif = self.motifs.all()[0] if self.motifs.all() else None
        if not motif:
            return "（暂无动机）"
        stage = max(1, min(4, motif.count + 1))
        return f"{motif.name} → 第{stage}次（{STAGES[stage]}）：{STAGE_HINT[STAGES[stage]]}"
