"""Editor — rank candidates, remove contradictions, integrate a proposal.

Nothing is auto-promoted to canonical story: the Editor only proposes a scene,
flags candidates that would reveal a secret / unrevealed thread early, and
*ranks* the survivors so the most valuable idea is kept (the rest stay as
alternatives for the author).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from engine import textutil as tu
from engine.planning_llm import generate_json
from jam_session.director import JamBrief

CLICHES = ["心潮澎湃", "五味杂陈", "不由自主", "恍然大悟", "百感交集", "思绪万千"]


@dataclass
class JamResult:
    brief: JamBrief
    solo: List[str] = field(default_factory=list)
    observer: List[str] = field(default_factory=list)
    proposal: str = ""
    chosen: str = ""
    ranked_solo: List[Dict] = field(default_factory=list)
    ranked_observer: List[Dict] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)
    debate: List[Dict] = field(default_factory=list)      # round-2 exchanges
    attribution: List[Dict] = field(default_factory=list)  # which role contributed what
    rounds: int = 1

    def to_dict(self) -> dict:
        return {
            "brief": self.brief.to_dict(),
            "solo": self.solo,
            "observer": self.observer,
            "proposal": self.proposal,
            "chosen": self.chosen,
            "ranked_solo": self.ranked_solo,
            "ranked_observer": self.ranked_observer,
            "notes": self.notes,
            "removed": self.removed,
            "debate": self.debate,
            "attribution": self.attribution,
            "rounds": self.rounds,
        }


class Editor:
    def run(self, brief: JamBrief, solo: List[str], observer: List[str], *,
            story_state=None, llm=None, rebuttals=None, rounds: int = 1) -> JamResult:
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

        solo_kept = self.rank(screen(solo))
        observer_kept = self.rank(screen(observer))

        notes: List[str] = []
        notes.append("Editor：已排除与已知秘密／未到期线索冲突的候选。" if removed
                     else "Editor：无候选与已知事实冲突。")
        notes.append("提示：并非每次即兴都要制造伏笔或冲突；平淡、失败的行动也可保留。")
        if solo_kept:
            notes.append(f"Editor：保留 {len(solo_kept)} 个独奏候选并排序，采用得分最高者。")
        if rebuttals:
            notes.append(f"Editor：经过一轮反驳（{len(rebuttals)} 条），采用修订后的方向，并标注来源。")

        chosen_solo = solo_kept[0]["text"] if solo_kept else "（无有效独奏动作）"
        chosen_obs = observer_kept[0]["text"] if observer_kept else "（无环境细节）"
        proposal = (
            f"{brief.goal}。本轮方向：{brief.direction}"
            f"以 {brief.pov or '主角'} 的视角：{chosen_solo}"
            f"同时让 {chosen_obs} 在旁存在。保留未知：本章不解释原因。"
            "退出点：在读者开始不安但尚未明白时收束。"
        )
        chosen = chosen_solo

        llm_proposal = self._from_llm(brief, [c["text"] for c in solo_kept],
                                      [c["text"] for c in observer_kept], llm)
        if llm_proposal:
            proposal = llm_proposal
            chosen = llm_proposal

        attribution = [{"source": "soloist", "idea": chosen_solo},
                       {"source": "observer", "idea": chosen_obs}]
        return JamResult(brief=brief, solo=solo, observer=observer,
                         proposal=proposal, chosen=chosen,
                         ranked_solo=solo_kept, ranked_observer=observer_kept,
                         notes=notes, removed=removed,
                         debate=list(rebuttals or []), attribution=attribution, rounds=rounds)

    @staticmethod
    def rank(items: List[str]) -> List[Dict]:
        """Score candidates and return them best-first (with alternatives)."""
        ranked = [{"text": it, "score": Editor.score(it)} for it in items if it.strip()]
        ranked.sort(key=lambda d: d["score"], reverse=True)
        return ranked

    @staticmethod
    def score(text: str) -> float:
        diversity = tu.lexical_diversity(text)
        cliche = tu.contains_any(text, CLICHES)
        concreteness = 1.0 if any(ch.isdigit() or ch in "门阀管雾气" for ch in text) else 0.6
        value = 0.45 + 0.3 * tu.clamp(diversity / 0.85) + 0.2 * concreteness - 0.4 * min(1.0, cliche)
        return round(tu.clamp(value), 3)

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
