"""Observer — non-central details, ambience, edge viewpoints.

Deliberately *not* a foreshadowing machine: some contributions are mundane,
failed, or go nowhere.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from engine.planning_llm import generate_json
from jam_session.director import JamBrief


class Observer:
    def run(self, brief: JamBrief, *, story_state=None,
            motifs: Sequence[str] = (), llm=None) -> List[str]:
        items = self._from_llm(brief, motifs, llm)
        if items:
            return items
        details = [
            "环境反馈：一个边缘物件／声音／温度的变化，不推进也不解释。",
            "边缘视角：一个不在场景中心的人做了一件与主线无关的小事。",
            "平淡项：一个没有结果、失败或犹豫的行动（不必承担伏笔功能）。",
        ]
        if motifs:
            details.append(f"意象旁现：让「{motifs[0]}」出现在与主角无关的位置。")
        return details

    def rebut(self, solo: List[str], brief: JamBrief, llm=None) -> List[str]:
        """Round-2: challenge the Soloist's proposals (what is ignored/too easy)."""
        via = self._rebut_llm(solo, brief, llm)
        if via:
            return via
        out: List[str] = []
        for i, s in enumerate(solo, 1):
            if len(s) < 10:
                out.append(f"反驳{i}：过于笼统，缺少一个可拍摄的具体动作。")
            elif any(w in s for w in ("解释", "说明", "意味着")):
                out.append(f"反驳{i}：有直说风险——主题应被暗示，不要解释。")
            else:
                out.append(f"反驳{i}：可能只是复述既有冲突；需要引入一个小的意外或代价。")
        return out

    def _rebut_llm(self, solo: List[str], brief: JamBrief, llm) -> Optional[List[str]]:
        if llm is None or getattr(llm, "name", "") in ("mock", ""):
            return None
        prompt = (
            "你是即兴小说的『观察者』，现在要**反驳**独奏者的候选：指出哪些太笼统、"
            "哪些在直说主题、哪些只是复述既有冲突。每条给一个具体反驳。不要写正文。\n"
            f"本轮方向：{brief.direction}\n独奏候选：{solo}\n"
            '输出 JSON：{"items":[""]}'
        )
        data = generate_json(llm, prompt)
        if data and isinstance(data.get("items"), list):
            return [str(x) for x in data["items"] if str(x).strip()]
        return None

    def _from_llm(self, brief: JamBrief, motifs: Sequence[str], llm) -> Optional[List[str]]:
        if llm is None or getattr(llm, "name", "") in ("mock", ""):
            return None
        prompt = (
            "你是即兴小说的『观察者』，提供 2-4 个非中心细节／环境反馈／边缘视角。"
            "不要每次都制造伏笔；允许平淡、失败、没有结果的素材。不要写正文。\n"
            f"本轮方向：{brief.direction}\n场景：{brief.scene}\n可用意象：{'、'.join(motifs) or '无'}\n"
            '输出 JSON：{"items":[""]}'
        )
        data = generate_json(llm, prompt)
        if data and isinstance(data.get("items"), list):
            return [str(x) for x in data["items"] if str(x).strip()]
        return None
