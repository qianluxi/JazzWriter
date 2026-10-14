"""Operator engine — turns random choice into a *narrative operation*.

Randomness alone adds noise. What actually changes the story is choosing a
concrete operation: shift attention, swap the sensory channel, let a character
misread, displace information, re-key a motif, invert an emotion, let an action
drift off-plan, or re-read an old clue. Each operator carries a goal, an
applicability condition, hard constraints, and a directive the writer follows.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from core.story_state import StoryState


@dataclass
class Operator:
    key: str
    name: str
    goal: str
    effect: str
    directive: str
    intensity: float = 0.5
    requires: str = ""          # human-readable applicability note
    constraints: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "goal": self.goal,
            "effect": self.effect,
            "directive": self.directive,
            "intensity": self.intensity,
        }


# The first batch of eight operators (expert's table) --------------------------
OPERATORS: List[Operator] = [
    Operator(
        key="attention_shift",
        name="注意力转移",
        goal="从主体转向边缘",
        effect="通过无关人物或不起眼物件间接透露信息",
        directive="本次不要直接推进主线结论：把叙述暂时移向一个边缘人物或不起眼的物件的一个动作，让信息从侧面渗出。",
        requires="场景中存在可被注意的边缘对象（人/物）",
    ),
    Operator(
        key="sensory_substitution",
        name="感官替换",
        goal="改变主要观察通道",
        effect="用温度、声音、气味代替直接视觉解释",
        directive="不要用视觉直接解释发生了什么：改用温度、声音或气味来承担这一段的观察，让读者先感到、后才明白。",
    ),
    Operator(
        key="cognitive_bias",
        name="认知偏差",
        goal="让人物依照自己的经验理解事件",
        effect="产生误解、错觉与人物特有的判断",
        directive="让人物用一个与其世界观一致、但可能错误的方式去理解眼前事件；不纠正他，让偏差留在文本里。",
    ),
    Operator(
        key="information_displacement",
        name="信息错位",
        goal="改变信息出现的顺序",
        effect="先给现象，暂时保留原因",
        directive="先呈现现象与后果，把原因与解释推迟或省略；不要让任何人当场推导出真相。",
    ),
    Operator(
        key="motif_variation",
        name="意象变奏",
        goal="重新分配意象的意义",
        effect="同一个意象在不同章节产生新作用",
        directive="让一个既有核心意象在本次承担新的作用（从实物滑向隐喻、记忆或命题），避免与之前同义复读。",
        requires="存在至少一个既有动机",
    ),
    Operator(
        key="emotional_contrast",
        name="情绪反差",
        goal="让表面行为与潜在情绪不一致",
        effect="以平静的动作表现焦虑，以温和的细节增加不安",
        directive="让人物的表面行为与内在情绪相反：用平静、克制甚至温和的动作承载焦虑或恐惧，不要直接命名情绪。",
    ),
    Operator(
        key="action_drift",
        name="行动偏航",
        goal="允许人物短暂偏离原计划",
        effect="让人物欲望真正影响情节",
        directive="允许人物短暂偏离原定目标，按其欲望做出一个计划外的小动作或选择；这个偏离必须有后果，但可以微小。",
    ),
    Operator(
        key="causal_review",
        name="因果重审",
        goal="改变读者理解已有线索的角度",
        effect="让旧细节产生新的解释，而不是任意篡改事实",
        directive="让一个已经出现的旧细节获得新的解释，从而改变读者对先前事件的理解；不得推翻已确定的事实。",
        requires="存在已出现的旧细节/已确定事实",
    ),
]
_BY_KEY = {op.key: op for op in OPERATORS}


@dataclass
class OperatorPlan:
    operators: List[Operator]
    constraints: dict = field(default_factory=dict)

    def directives(self) -> str:
        if not self.operators:
            return "本次不启用额外即兴操作，靠细节自然推进。"
        lines = ["本次启用以下叙事操作（可组合，但须服从硬约束）："]
        for i, op in enumerate(self.operators, 1):
            lines.append(f"  {i}. [{op.name}] {op.directive}")
        return "\n".join(lines)

    def constraint_lines(self) -> List[str]:
        labels = {
            "preserve_character_motivation": "人物动机必须一致，行动出自其欲望/恐惧/世界观",
            "preserve_established_facts": "不得与已确定的事实矛盾",
            "do_not_reveal_core_mystery": "不得提前揭露核心秘密或未到期的线索",
            "respect_timeline": "不得违反时间线",
        }
        return [labels[k] for k, v in self.constraints.items() if v and k in labels]

    def to_dict(self) -> dict:
        return {
            "operators": [op.to_dict() for op in self.operators],
            "constraints": dict(self.constraints),
        }


class OperatorEngine:
    def __init__(self, rng: Optional[random.Random] = None) -> None:
        self.rng = rng or random.Random()

    def _applicable(self, op: Operator, state: Optional[StoryState], has_motifs: bool) -> bool:
        if op.key == "motif_variation" and not has_motifs:
            return False
        if op.key == "causal_review" and not (state and (state.confirmed() or state.recent_events)):
            return False
        return True

    def select(
        self,
        *,
        creativity: float = 0.5,
        randomness: float = 0.4,
        motif_reuse: float = 0.8,
        state: Optional[StoryState] = None,
        has_motifs: bool = True,
        k: Optional[int] = None,
    ) -> OperatorPlan:
        pool = [op for op in OPERATORS if self._applicable(op, state, has_motifs)]

        if k is None:
            k = 1
            if creativity > 0.5:
                k += 1
            if randomness > 0.55:
                k += 1
            k = max(1, min(3, k))
        k = min(k, len(pool))

        # bias toward motif_variation when the author wants motif reuse
        chosen: List[Operator] = []
        if has_motifs and self.rng.random() < motif_reuse * 0.6:
            chosen.append(_BY_KEY["motif_variation"])
        remaining = [op for op in pool if op not in chosen]
        if k - len(chosen) > 0:
            chosen += self.rng.sample(remaining, k - len(chosen))
        chosen = chosen[:k]
        self.rng.shuffle(chosen)

        constraints = {
            "preserve_character_motivation": True,
            "preserve_established_facts": bool(state and state.confirmed()),
            "do_not_reveal_core_mystery": bool(state and (state.secrets() or state.open_thread_list())),
            "respect_timeline": True,
        }
        return OperatorPlan(operators=chosen, constraints=constraints)
