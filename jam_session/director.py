"""Director — decides what this jam round explores, and its limits."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from engine.planning_llm import generate_json


@dataclass
class JamBrief:
    scene: str
    goal: str = ""
    direction: str = ""
    pov: str = ""
    constraints: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"scene": self.scene, "goal": self.goal, "direction": self.direction,
                "pov": self.pov, "constraints": self.constraints}


class Director:
    def run(self, scene: str, *, pov: str = "", book=None, chapter=None,
            params=None, llm=None) -> JamBrief:
        brief = self._from_llm(scene, pov, book, chapter, llm)
        if brief is not None:
            return brief

        goal = chapter.summary if (chapter and chapter.summary) else scene
        direction = self._direction(chapter, params)
        constraints: List[str] = []
        if chapter:
            if chapter.function:
                constraints.append(f"功能定位：{chapter.function}")
            if chapter.conflict:
                constraints.append(f"围绕冲突：{chapter.conflict}")
            if chapter.outcome:
                constraints.append(f"指向结果：{chapter.outcome}")
            if chapter.hook_to:
                constraints.append(f"保留驱动：{chapter.hook_to}")
        return JamBrief(scene=scene, goal=goal, direction=direction, pov=pov, constraints=constraints)

    @staticmethod
    def _direction(chapter, params) -> str:
        delay = getattr(params, "revelation_delay", 0.5) if params else 0.5
        if delay >= 0.6:
            return "延迟揭露：本章只给现象，不解释原因，把确认推后。"
        if delay <= 0.3:
            return "适度交代：允许本章给出一个明确的发现或确认。"
        return "推进而不揭底：让信息有增量，但保留核心问题。"

    def _from_llm(self, scene, pov, book, chapter, llm) -> Optional[JamBrief]:
        if llm is None or getattr(llm, "name", "") in ("mock", ""):
            return None
        chapter_desc = chapter.summary if chapter else scene
        prompt = (
            f"你是即兴小说的『导演』。本轮的场景/章节意图：{chapter_desc}\n"
            f"视角人物：{pov}\n"
            f"请给出本轮要探索的方向与限制。输出 JSON："
            '{"goal":"","direction":"","constraints":[""]}'
        )
        data = generate_json(llm, prompt)
        if not data:
            return None
        return JamBrief(scene=scene, goal=str(data.get("goal", scene)),
                        direction=str(data.get("direction", "")), pov=pov,
                        constraints=[str(x) for x in data.get("constraints", [])])
