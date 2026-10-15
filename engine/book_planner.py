"""Book planner — story-level improvisation and whole-book synthesis.

Two responsibilities:

1. ``ideas()``     — from one premise, propose N *materially different* story
   hypotheses (different causal machinery / truth nature / relations / ending).
2. ``build()``     — turn a chosen hypothesis into a BookPlan (synopsis, key
   turns, ending) and expand it into volumes and chapter cards.

Uses the LLM when available (great with opencode); otherwise a deterministic
generator keeps everything working offline and testable.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from core.book_plan import BookPlan
from core.character import Character
from core.chapter_plan import ChapterPlan
from core.story_idea import StoryIdea
from core.theme import Theme
from core.volume_plan import VolumePlan
from engine.outline_expander import OutlineExpander, TEMPLATE_LABELS
from engine.planning_llm import generate_json

CAUSAL = [
    "事故是系统性隐瞒的结果，责任无法归于单个人",
    "事故源于一个善意的决定，被时间放大成灾难",
    "事故源于证据体系本身的缺陷，而不是某个坏人",
    "事故源于对同一段过去的集体误记",
    "事故是多方各自合理选择的叠加后果",
    "事故源于一次被误读的信号或记录",
]
TRUTH = [
    "真相是技术性的，可以被查明",
    "真相是人的，可以被理解但无法轻易原谅",
    "真相不可完全归结，只剩理解与代价",
    "真相取决于叙述者，记忆并不可靠",
    "真相被刻意保留在幕后，只在边缘显现",
]
RELATION = [
    "父亲是共谋者，主角在追查中重演他",
    "父亲是替罪者，真正的问题在别处",
    "父亲是受害者，主角的愤怒需要重新安放",
    "父亲并不在场，却被写成故事的核心",
    "主角与父亲互为镜像，无法互相拯救",
]
ENDING = [
    "以理解收束，但不和解",
    "开放结局，核心问题被重新提出",
    "揭露之后更加孤独",
    "付出高昂代价后获得部分修复",
    "循环回到开头的问题，只是换了人",
]


class BookPlanner:
    def __init__(
        self,
        theme: Theme,
        characters: List[Character],
        params,
        llm=None,
    ) -> None:
        self.theme = theme
        self.characters = list(characters)
        self.params = params
        self.llm = llm

    # -- helpers ------------------------------------------------------------
    def _limit(self, pool: List[str], divergence: float) -> int:
        return max(2, min(len(pool), round(2 + divergence * (len(pool) - 2))))

    def _cast(self) -> List[str]:
        return [c.name for c in self.characters] or ["主角"]

    # -- story-level ideas --------------------------------------------------
    def ideas(self, premise: str, *, count: Optional[int] = None, seed: Optional[int] = None) -> List[StoryIdea]:
        count = max(2, int(count or self.params.branch_count))
        llm_ideas = self._ideas_from_llm(premise, count)
        if llm_ideas:
            return llm_ideas

        rng = random.Random(seed if seed is not None else (self.params.seed or 0))
        kc = self._limit(CAUSAL, self.params.causal_variation)
        kt = self._limit(TRUTH, 0.6)
        kr = self._limit(RELATION, 0.6)
        ke = self._limit(ENDING, self.params.idea_divergence)

        ideas: List[StoryIdea] = []
        for i in range(count):
            causal = CAUSAL[i % kc]
            truth = TRUTH[(i * 2 + 1) % kt]
            relation = RELATION[(i + 3) % kr]
            ending = ENDING[(i * 2) % ke]
            ideas.append(StoryIdea(
                id=f"idea{i + 1:02d}",
                label=f"方向{chr(65 + i)} · {causal[:10]}",
                premise=f"{premise}｜{causal}",
                causal_mechanism=causal,
                truth_nature=truth,
                character_relation=relation,
                ending_direction=ending,
            ))

        ref = ideas[0]
        ref.distinctness = 0.0
        ref.differentiators = ["基准路线"]
        ref.rationale = "作为比较基准：最直接、最容易被想到的走向。"
        dims = [("因果", "causal_mechanism"), ("真相", "truth_nature"),
                ("关系", "character_relation"), ("结局", "ending_direction")]
        for idea in ideas[1:]:
            diffs = [label for label, attr in dims if getattr(idea, attr) != getattr(ref, attr)]
            idea.differentiators = diffs
            idea.distinctness = round(len(diffs) / 4, 2)
            idea.rationale = "改变" + ("、".join(diffs) if diffs else "细节") + "，提供不同的因果与意义走向。"
        return ideas

    # -- whole-book build ---------------------------------------------------
    def build(
        self,
        premise: str,
        idea: StoryIdea,
        *,
        chapters: int = 12,
        template: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> BookPlan:
        template = template or "linear_causality"
        book = BookPlan(
            title=self.theme.title or "未命名",
            logline=premise,
            premise=premise,
            question=self.theme.question or self.theme.statement,
            main_conflict=f"围绕「{idea.causal_mechanism[:20]}」；{idea.character_relation[:16]}",
            cast=self._cast(),
            key_turns=self._key_turns(idea),
            ending=idea.ending_direction,
            structure_template=template,
            chosen_idea=idea,
            params=self.params.to_dict(),
        ).stamp()

        llm_book = self._book_from_llm(book, premise, idea, chapters, template)
        if llm_book is not None:
            return llm_book
        return OutlineExpander(self.theme, book.cast).expand(
            book, chapters, template=template,
            seed=seed if seed is not None else (self.params.seed or 0),
        )

    def _key_turns(self, idea: StoryIdea) -> List[str]:
        return [
            "开篇：以一个具体、可被质疑的事件建立核心问题",
            f"第一次发现：与「{idea.causal_mechanism[:12]}」相关的证据浮现",
            "中点：主角追查问题的方式本身被证明有缺陷",
            f"危机：{idea.character_relation[:16]}",
            f"收束：{idea.ending_direction}",
        ]

    # -- LLM paths (optional) ----------------------------------------------
    def _ideas_from_llm(self, premise: str, count: int) -> Optional[List[StoryIdea]]:
        cast = "、".join(self._cast())
        prompt = (
            f"故事前提：{premise}\n"
            f"主题命题：{self.theme.question or self.theme.title}\n"
            f"人物：{cast}\n"
            f"故事方向差异度 idea_divergence={self.params.idea_divergence}，因果变化 causal_variation={self.params.causal_variation}\n\n"
            f"请给出 {count} 个**实质不同**的故事方案。每个方案必须改变「因果机制／真相性质／人物关系走向／结局方向」中的至少一项，"
            "而不是换一种写法。\n"
            '输出 JSON：{"ideas":[{"label":"","premise":"","causal_mechanism":"","truth_nature":"",'
            '"character_relation":"","ending_direction":"","rationale":""}]}'
        )
        data = generate_json(self.llm, prompt)
        if not data or not isinstance(data.get("ideas"), list):
            return None
        ideas: List[StoryIdea] = []
        for i, item in enumerate(data["ideas"][:count]):
            if not isinstance(item, dict):
                continue
            idea = StoryIdea(
                id=f"idea{i + 1:02d}",
                label=str(item.get("label", f"方向{chr(65 + i)}")),
                premise=str(item.get("premise", premise)),
                causal_mechanism=str(item.get("causal_mechanism", "")),
                truth_nature=str(item.get("truth_nature", "")),
                character_relation=str(item.get("character_relation", "")),
                ending_direction=str(item.get("ending_direction", "")),
                rationale=str(item.get("rationale", "")),
            )
            if idea.is_viable:
                ideas.append(idea)
        if len(ideas) < 2:
            return None
        ref = ideas[0]
        dims = [("因果", "causal_mechanism"), ("真相", "truth_nature"),
                ("关系", "character_relation"), ("结局", "ending_direction")]
        for idea in ideas:
            diffs = [label for label, attr in dims if getattr(idea, attr) != getattr(ref, attr)]
            idea.differentiators = diffs
            idea.distinctness = round(len(diffs) / 4, 2)
        return ideas

    def _book_from_llm(
        self, book: BookPlan, premise: str, idea: StoryIdea, chapters: int, template: str
    ) -> Optional[BookPlan]:
        cast = "、".join(self._cast())
        prompt = (
            f"故事前提：{premise}\n"
            f"选定方案：因果={idea.causal_mechanism}；真相={idea.truth_nature}；"
            f"关系={idea.character_relation}；结局={idea.ending_direction}\n"
            f"人物：{cast}\n"
            f"结构模板：{TEMPLATE_LABELS.get(template, template)}（{template}）\n"
            f"章节数：{chapters}；连续性约束 continuity_strength={self.params.continuity_strength}\n\n"
            f"请生成全书结构与 {chapters} 张章节摘要卡片。每章都要有：功能、POV、起因、关键行动、"
            "冲突、结果、代价、信息变化、人物变化、涉及线索、意象、与上下章的因果联系。"
            "线索需有引入与回收。只输出 JSON：\n"
            '{"logline":"","main_conflict":"","key_turns":[""],"ending":"",'
            '"volumes":[{"title":"","goal":"","opening_state":"","climax":"","outcome":"","sets_up_next":"",'
            '"chapters":[{"number":1,"title":"","function":"","pov":"","premise":"","key_action":"",'
            '"conflict":"","outcome":"","stakes":"","info_change":"","character_change":"",'
            '"threads":[],"motifs":[],"hook_from":"","hook_to":"","summary":""}]}]}'
        )
        data = generate_json(self.llm, prompt, max_tokens=8000)
        if not data or not isinstance(data.get("volumes"), list):
            return None
        try:
            chapters_out: List[ChapterPlan] = []
            volumes: List[VolumePlan] = []
            for vi, vitem in enumerate(data["volumes"]):
                if not isinstance(vitem, dict):
                    continue
                vchapters = []
                for citem in vitem.get("chapters", []):
                    if not isinstance(citem, dict):
                        continue
                    number = int(citem.get("number", len(chapters_out) + 1))
                    vchapters.append(ChapterPlan(
                        number=number,
                        title=str(citem.get("title", "")),
                        function=str(citem.get("function", "")),
                        pov=str(citem.get("pov", "")),
                        premise=str(citem.get("premise", "")),
                        key_action=str(citem.get("key_action", "")),
                        conflict=str(citem.get("conflict", "")),
                        outcome=str(citem.get("outcome", "")),
                        stakes=str(citem.get("stakes", "")),
                        info_change=str(citem.get("info_change", "")),
                        character_change=str(citem.get("character_change", "")),
                        threads=[str(x) for x in citem.get("threads", [])],
                        motifs=[str(x) for x in citem.get("motifs", [])],
                        hook_from=str(citem.get("hook_from", "")),
                        hook_to=str(citem.get("hook_to", "")),
                        summary=str(citem.get("summary", "")),
                    ))
                chapters_out.extend(vchapters)
                volumes.append(VolumePlan(
                    number=vi + 1,
                    title=str(vitem.get("title", f"第{vi + 1}卷")),
                    goal=str(vitem.get("goal", "")),
                    opening_state=str(vitem.get("opening_state", "")),
                    key_turns=[str(x) for x in vitem.get("key_turns", [])],
                    climax=str(vitem.get("climax", "")),
                    outcome=str(vitem.get("outcome", "")),
                    sets_up_next=str(vitem.get("sets_up_next", "")),
                    chapters=vchapters,
                ))
        except Exception:  # noqa: BLE001
            return None
        if len(chapters_out) < max(3, chapters // 2):
            return None
        # renumber sequentially to keep the map consistent
        for i, ch in enumerate(sorted(chapters_out, key=lambda c: c.number), start=1):
            ch.number = i
        book.logline = str(data.get("logline", book.logline)) or book.logline
        book.main_conflict = str(data.get("main_conflict", book.main_conflict)) or book.main_conflict
        if data.get("key_turns"):
            book.key_turns = [str(x) for x in data["key_turns"]]
        book.ending = str(data.get("ending", book.ending)) or book.ending
        book.volumes = volumes
        return book
