"""Outline expander — grow a BookPlan into volumes and chapter cards.

Progressive structure, not a single megaprompt. Structure templates let the
story serve the novel rather than the novel serving a fixed three-act mould.
Deterministic and reproducible given a seed; the LLM path (in BookPlanner)
can replace it, but this is always the safe fallback.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional

from core.book_plan import BookPlan
from core.chapter_plan import (ChapterPlan, CharacterDecision, KnowledgeChange,
                               RelationshipChange)
from core.character import Character
from core.relationship import RelationshipMap
from core.theme import Theme
from core.volume_plan import VolumePlan

TEMPLATES: Dict[str, List[str]] = {
    "linear_causality": ["建立", "推进", "升级", "中点转折", "低谷", "高潮", "收束"],
    "mystery": ["设谜", "调查", "误导", "发现", "反转", "解释", "收束"],
    "multi_pov": ["A线", "B线", "交织", "对撞", "汇合", "代价", "收束"],
    "ensemble": ["群像·起", "群像·散", "聚焦", "交叉", "汇聚", "代价", "收束"],
    "nonlinear_puzzle": ["碎片", "倒叙", "拼接", "缺口", "指认", "重组", "回应"],
    "custom": ["起", "承", "转", "合"],
}
TEMPLATE_LABELS = {
    "linear_causality": "线性因果",
    "mystery": "悬疑调查",
    "multi_pov": "多视角",
    "ensemble": "群像",
    "nonlinear_puzzle": "非线性拼图",
    "custom": "自定义",
}


# functions where the cast should converge on the protagonist's POV
CONVERGE_FUNCS = {"高潮", "收束", "反转", "汇合", "重组", "指认", "回应"}
# functions where a relationship is most likely to shift
REL_CHANGE_FUNCS = CONVERGE_FUNCS | {"危机", "低谷", "转折", "对撞", "中点转折"}
MULTI_POV_TEMPLATES = {"multi_pov", "ensemble"}


def _sequence(template: str, n: int) -> List[str]:
    seq = TEMPLATES.get(template, TEMPLATES["linear_causality"])
    if n <= 1:
        return [seq[0]]
    return [seq[round(i * (len(seq) - 1) / (n - 1))] for i in range(n)]


class OutlineExpander:
    def __init__(self, theme: Theme, cast, *, relationships: Optional[RelationshipMap] = None,
                 harmony=None, story_state=None) -> None:
        self.theme = theme
        self.characters: List[Character] = [
            c if isinstance(c, Character) else Character(name=str(c)) for c in (cast or [])
        ] or [Character(name="主角")]
        self.cast = [c.name for c in self.characters]
        self.relationships = relationships or RelationshipMap()
        self._pov_characters = [c for c in self.characters if getattr(c, "pov", True)] or self.characters
        self._by_id = {c.effective_id: c for c in self.characters}
        # offline path also respects world rules and the story state
        self.harmony = harmony
        self.story_state = story_state
        self._forbidden = [b for b in (harmony.forbidden if harmony else []) if b]
        self._secret_reveals = story_state.forbidden_reveals() if story_state else []
        self._curve = list(harmony.emotion_curve) if harmony else []

    def _sanitize(self, text: str) -> str:
        out = text or ""
        for bad in self._forbidden:
            if bad in out:
                out = out.replace(bad, "（略）")
        for secret in self._secret_reveals:
            if secret and secret in out:
                out = "（按设定，此处不揭露）"
        return out

    def expand(
        self,
        book: BookPlan,
        chapter_count: int,
        *,
        template: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> BookPlan:
        chapter_count = max(1, int(chapter_count))
        template = template or book.structure_template or "linear_causality"
        book.structure_template = template
        rng = random.Random(seed if seed is not None else 0)

        functions = _sequence(template, chapter_count)
        povs = self._pov_plan(chapter_count, template, rng)
        motifs = (self.theme.motifs or self.theme.symbols) or ["意象"]
        turns = book.key_turns or [f"阶段{i+1}" for i in range(1)]

        # thread schedule: introduce in the first half, reveal per revelation_delay
        delay = float(book.params.get("revelation_delay", 0.5))
        threads: List[str] = [t[:16] for t in turns]
        schedule: Dict[str, Dict[str, int]] = {}
        for j, thread in enumerate(threads):
            intro = min(chapter_count - 1, int(j * (chapter_count * 0.5) / max(1, len(threads))))
            span = max(1, int((chapter_count - intro) * (0.5 + 0.4 * delay)))
            reveal = min(chapter_count - 1, intro + span)
            schedule[thread] = {"intro": intro, "reveal": reveal}

        chapters: List[ChapterPlan] = []
        prev_hook = f"{book.premise}（故事由此启动）" if book.premise else "故事由此启动。"
        for i in range(chapter_count):
            fn = functions[i]
            turn = turns[i % len(turns)]
            pov_char = povs[i]
            if template in MULTI_POV_TEMPLATES and fn in CONVERGE_FUNCS:
                # converge on the declared protagonist (not list order)
                pov_char = self._by_id.get(book.primary_character_id,
                                           self._pov_characters[0])
            pov = pov_char.name
            pov_id = pov_char.effective_id
            involved = [pov_id]
            # rotating co-participant (may be a non-POV character) so the whole
            # cast gets used and relationships can move across chapters
            if len(self.characters) > 1:
                other = self.characters[(i + 1) % len(self.characters)]
                if other.effective_id not in involved:
                    involved.append(other.effective_id)
            active_threads = [t for t, s in schedule.items() if s["intro"] == i]
            reveal_threads = [t for t, s in schedule.items() if s["reveal"] == i and s["intro"] != i]
            ch_motifs = [motifs[i % len(motifs)], motifs[(i + 1) % len(motifs)]]
            ch_motifs = list(dict.fromkeys(ch_motifs))  # dedupe, keep order

            curve = (self._curve[int(round((i / max(1, chapter_count - 1)) * (len(self._curve) - 1)))]
                     if self._curve else "")
            action = self._sanitize(self._action(fn, pov, turn))
            conflict = self._sanitize(self._conflict(fn, turn, pov, book))
            outcome = self._sanitize(self._outcome(fn, turn))
            hook_to = self._hook(fn, turn, i, chapter_count)
            info_line = self._sanitize(self._info(fn, reveal_threads))
            char_change = self._sanitize(self._char_change(fn, pov)) + (f"（情绪坐标：{curve}）" if curve else "")
            decisions = [CharacterDecision(character_id=pov_id, decision=action,
                                           motivation=pov_char.current_goal or pov_char.desire or "")]
            knowledge = ([KnowledgeChange(character_id=pov_id, change=info_line,
                                          source=f"第 {i + 1} 章 · {action[:20]}")]
                         if info_line else [])
            rel_changes = self._relationship_changes(fn, involved)

            chapters.append(ChapterPlan(
                number=i + 1,
                title=f"{fn}·{turn[:12]}" if turn else fn,
                function=fn,
                pov=pov,
                pov_character_id=pov_id,
                characters_involved=involved,
                character_decisions=decisions,
                knowledge_changes=knowledge,
                relationship_changes=rel_changes,
                premise=prev_hook,
                key_action=action,
                conflict=conflict,
                outcome=outcome,
                stakes=self._sanitize(self._stakes(book)),
                info_change=info_line,
                character_change=char_change,
                threads=active_threads + reveal_threads,
                motifs=ch_motifs,
                hook_from=prev_hook,
                hook_to=hook_to,
                summary=f"{pov}面临「{turn[:14]}」：{conflict}；{outcome}",
            ))
            prev_hook = hook_to

        book.volumes = self._group_volumes(book, chapters, template)
        return book

    def _pov_plan(self, n: int, template: str, rng: random.Random) -> List[Character]:
        """Distribute viewpoints sensibly per structure template (POV-eligible only)."""
        cast = self._pov_characters
        m = len(cast)
        if m == 1:
            return [cast[0]] * n
        if template == "ensemble":
            # contiguous arcs, balanced, order shuffled
            order = cast[:]
            rng.shuffle(order)
            sizes = [n // m] * m
            for i in range(n % m):
                sizes[i] += 1
            seq: List[Character] = []
            for c, size in zip(order, sizes):
                seq.extend([c] * size)
            return seq
        if template == "multi_pov":
            # interleaved but balanced; shuffle each round and rotate the seam
            # so the same viewpoint never runs on across a cycle boundary
            order = cast[:]
            rng.shuffle(order)
            seq: List[Character] = []
            while len(seq) < n:
                cycle = order[:]
                if seq and len(cycle) > 1 and cycle[0] is seq[-1]:
                    cycle = cycle[1:] + cycle[:1]
                seq.extend(cycle)
            return seq[:n]
        return [cast[i % m] for i in range(n)]

    # -- field synthesis ----------------------------------------------------
    def _conflict(self, fn: str, turn: str, pov: str, book: BookPlan) -> str:
        return f"{pov}的欲望与既有局面在「{turn[:14]}」上发生碰撞（{fn}）"

    def _outcome(self, fn: str, turn: str) -> str:
        return f"事件推进：{turn[:16]}，处境发生变化，但代价随之而来"

    def _action(self, fn: str, pov: str, turn: str) -> str:
        return f"{pov}围绕「{turn[:14]}」采取行动"

    def _stakes(self, book: BookPlan) -> str:
        return book.main_conflict or "人物关系的存续"

    def _info(self, fn: str, reveals: List[str]) -> str:
        if reveals:
            return "揭示：" + "、".join(reveals)
        return "信息被保留、延迟或误导"

    def _char_change(self, fn: str, pov: str) -> str:
        return f"{pov}对核心命题的判断出现shift（{fn}）"

    def _relationship_changes(self, fn: str, involved: List[str]) -> List[dict]:
        """On turning-point chapters, move one defined relationship (if present)."""
        if fn not in REL_CHANGE_FUNCS or not self.relationships.relationships:
            return []
        inv = set(involved)
        for r in self.relationships.relationships:
            if r.source_id in inv and r.target_id in inv:
                change = r.possible_transition or (
                    f"围绕「{(r.conflict or '共同处境')[:14]}」，关系出现松动")
                return [RelationshipChange(pair=[r.source_id, r.target_id], change=change,
                                           cause=r.pressure_point or "")]
        return []

    def _hook(self, fn: str, turn: str, i: int, n: int) -> str:
        if i >= n - 1:
            return "回扣开篇提出的问题，给出回应。"
        return f"由「{turn[:14]}」引出一个新的问题，留给下一章。"

    def _group_volumes(self, book: BookPlan, chapters: List[ChapterPlan], template: str) -> List[VolumePlan]:
        n = len(chapters)
        vcount = 1 if n <= 4 else 2 if n <= 9 else 3
        size = (n + vcount - 1) // vcount
        volumes: List[VolumePlan] = []
        for v in range(vcount):
            chunk = chapters[v * size:(v + 1) * size]
            if not chunk:
                continue
            first, last = chunk[0], chunk[-1]
            turns = list(dict.fromkeys([c.title for c in chunk if "转折" in c.function or "高潮" in c.function])) or [last.title]
            volumes.append(VolumePlan(
                number=v + 1,
                title=f"第{v+1}卷·{first.function}→{last.function}",
                goal=f"完成从「{first.function}」到「{last.function}」的阶段目标",
                opening_state=first.premise,
                key_turns=turns,
                climax=last.summary,
                outcome=f"第{v+1}卷结束时：{last.outcome}",
                sets_up_next=last.hook_to,
                chapters=chunk,
            ))
        return volumes
