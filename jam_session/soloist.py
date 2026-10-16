"""Soloist — proposes actions/observations from a character's own drives."""

from __future__ import annotations

from typing import List, Optional

from core.character import Character
from engine.planning_llm import generate_json
from jam_session.director import JamBrief


class Soloist:
    def run(self, brief: JamBrief, character: Character, *,
            story_state=None, llm=None) -> List[str]:
        items = self._from_llm(brief, character, llm)
        if items:
            return items
        name = character.name or "主角"
        moves = [
            f"{name}出于「{character.desire or '未说出口的欲望'}」采取一个具体行动，而不是向读者解释。",
            f"由「{character.fear or '隐藏的恐惧'}」驱动的回避：他绕开某个话题、物件或人。",
        ]
        if character.memory:
            moves.append(f"记忆滤镜：{character.memory} 让他误读了此刻正在发生的事。")
        if character.contradiction:
            moves.append(f"内在矛盾显形：{character.contradiction}，在行动里露出裂口。")
        return moves

    def respond(self, rebuttals: List[str], character: Character,
                prior: List[str], llm=None) -> List[str]:
        """Round-2: revise the proposals in light of the Observer's rebuttals."""
        via = self._respond_llm(rebuttals, character, prior, llm)
        if via:
            return via
        name = character.name or "主角"
        out: List[str] = []
        for i, p in enumerate(prior, 1):
            out.append(f"修订{i}：{p} → 改成 {name} 的一个具体、可拍摄的动作，不解释，允许失败。")
        return out or [f"修订：{name}用一个具体动作代替解释。"]

    def _respond_llm(self, rebuttals: List[str], character: Character,
                     prior: List[str], llm) -> Optional[List[str]]:
        if llm is None or getattr(llm, "name", "") in ("mock", ""):
            return None
        prompt = (
            "你是即兴小说的『独奏者』。观察者对你的候选提出了反驳，请**修订**你的方向："
            "更具体、不解释、允许失败与偏离。不要写正文。\n"
            f"人物：{character.name}；欲望={character.desire}；恐惧={character.fear}\n"
            f"原候选：{prior}\n观察者反驳：{rebuttals}\n"
            '输出 JSON：{"items":[""]}'
        )
        data = generate_json(llm, prompt)
        if data and isinstance(data.get("items"), list):
            return [str(x) for x in data["items"] if str(x).strip()]
        return None

    def _from_llm(self, brief: JamBrief, character: Character, llm) -> Optional[List[str]]:
        if llm is None or getattr(llm, "name", "") in ("mock", ""):
            return None
        prompt = (
            "你是即兴小说的『独奏者』，只从人物的内在出发，提出 2-4 个可尝试的行动或观察方向。\n"
            f"本轮方向：{brief.direction}\n场景/意图：{brief.goal}\n"
            f"人物：{character.name}；欲望={character.desire}；恐惧={character.fear}；"
            f"记忆={character.memory}；世界观={character.worldview}；矛盾={character.contradiction}\n"
            "不要写正文。输出 JSON：{\"items\":[\"\"]}"
        )
        data = generate_json(llm, prompt)
        if data and isinstance(data.get("items"), list):
            return [str(x) for x in data["items"] if str(x).strip()]
        return None
