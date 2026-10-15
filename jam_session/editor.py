"""Editor — compares candidates, removes contradictions, integrates a proposal.

Nothing is auto-promoted to canonical story: the Editor only proposes a scene,
and flags any candidate that would reveal a secret / unrevealed thread early.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from engine.planning_llm import generate_json
from jam_session.director import JamBrief


@dataclass
class JamResult:
    brief: JamBrief
    solo: List[str] = field(default_factory=list)
    observer: List[str] = field(default_factory=list)
    proposal: str = ""
    chosen: str = ""
    notes: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "brief": self.brief.to_dict(),
            "solo": self.solo,
            "observer": self.observer,
            "proposal": self.proposal,
            "chosen": self.chosen,
            "notes": self.notes,
            "removed": self.removed,
        }


class Editor:
    def run(self, brief: JamBrief, solo: List[str], observer: List[str], *,
            story_state=None, llm=None) -> JamResult:
        forbidden = story_state.forbidden_reveals(brief.pov) if story_state else []
        removed: List[str] = []

        def screen(items: List[str]) -> List[str]:
            kept: List[str] = []
            for item in items:
                if any(f and f in item for f in forbidden):
                    removed.append(item)
                else:
                    kept.append(item)
            return kept

        solo_kept = screen(solo)
        observer_kept = screen(observer)

        notes: List[str] = []
        notes.append("Editor：已排除与已知秘密／未到期线索冲突的候选。" if removed
                     else "Editor：无候选与已知事实冲突。")
        notes.append("提示：并非每次即兴都要制造伏笔或冲突；平淡、失败的行动也可保留。")

        chosen_solo = solo_kept[0] if solo_kept else "（无有效独奏动作）"
        chosen_obs = observer_kept[0] if observer_kept else "（无环境细节）"
        proposal = (
            f"{brief.goal}。本轮方向：{brief.direction}"
            f"以 {brief.pov or '主角'} 的视角：{chosen_solo}"
            f"同时让 {chosen_obs} 在旁存在。保留未知：本章不解释原因。"
            "退出点：在读者开始不安但尚未明白时收束。"
        )
        chosen = chosen_solo

        llm_proposal = self._from_llm(brief, solo_kept, observer_kept, llm)
        if llm_proposal:
            proposal = llm_proposal
            chosen = llm_proposal

        return JamResult(brief=brief, solo=solo, observer=observer,
                         proposal=proposal, chosen=chosen, notes=notes, removed=removed)

    def _from_llm(self, brief, solo, observer, llm) -> Optional[str]:
        if llm is None or getattr(llm, "name", "") in ("mock", ""):
            return None
        prompt = (
            "你是即兴小说的『编辑』。把导演方向、独奏动作与观察细节整合成**一个**场景提案"
            "（仍是提案，不是成稿）：保留未知、排除与已知事实矛盾者、不要自动升级为正式设定。\n"
            f"方向：{brief.direction}\n场景/意图：{brief.goal}；视角：{brief.pov}\n"
            f"独奏候选：{solo}\n观察候选：{observer}\n"
            '输出 JSON：{"proposal":""}'
        )
        data = generate_json(llm, prompt)
        if data and str(data.get("proposal", "")).strip():
            return str(data["proposal"]).strip()
        return None
