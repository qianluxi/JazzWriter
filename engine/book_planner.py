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
from core.harmony import Harmony
from core.story_idea import StoryIdea
from core.story_state import StoryState
from core.theme import Theme
from core.volume_plan import VolumePlan
from engine.outline_expander import OutlineExpander, TEMPLATE_LABELS
from engine.planning_llm import generate_json

OFFLINE = "offline_template"

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
        harmony: Optional[Harmony] = None,
        story_state: Optional[StoryState] = None,
    ) -> None:
        self.theme = theme
        self.characters = list(characters)
        self.params = params
        self.llm = llm
        self.harmony = harmony
        self.story_state = story_state

    # -- constraints (world rules + story state) ----------------------------
    def constraints(self) -> List[str]:
        """Hard constraints that the whole-book plan must respect."""
        out: List[str] = []
        if self.harmony:
            out += [f"世界规则：{r}" for r in self.harmony.rules]
            out += [f"禁忌：{f}" for f in self.harmony.forbidden]
            if self.harmony.emotion_curve:
                out.append("情绪和声：" + "→".join(self.harmony.emotion_curve))
        if self.story_state:
            out += self.story_state.as_constraints()
            out += [f"不可提前揭露：{f}" for f in self.story_state.forbidden_reveals()]
            out += [f"已确定事实：{f.statement}" for f in self.story_state.confirmed()]
        return out

    def _constraints_text(self) -> str:
        return "；".join(self.constraints()) or "（无额外硬约束）"

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
        # deterministic fallback is clearly marked as offline

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
        for idea in ideas:
            idea.generated_by = OFFLINE
        return ideas

    def fuse(
        self,
        a: StoryIdea,
        b: StoryIdea,
        *,
        picks: Optional[Dict[str, str]] = None,
    ) -> StoryIdea:
        """Fuse two hypotheses into one.

        ``picks`` maps a dimension to "a" or "b"; unspecified dimensions blend
        (causal/relation from A, truth/ending from B) so the result is a genuine
        hybrid rather than a copy.
        """
        llm_idea = self._fuse_from_llm(a, b)
        if llm_idea is not None:
            return llm_idea

        picks = picks or {}
        defaults = {"causal_mechanism": "a", "truth_nature": "b",
                    "character_relation": "a", "ending_direction": "b"}

        def choose(dim: str) -> str:
            src = picks.get(dim, defaults[dim])
            return getattr(b if src == "b" else a, dim)

        fused = StoryIdea(
            id="fused",
            label=f"融合 · {a.label[:8]} × {b.label[:8]}",
            premise=f"{a.premise} ／ {b.premise}",
            causal_mechanism=choose("causal_mechanism"),
            truth_nature=choose("truth_nature"),
            character_relation=choose("character_relation"),
            ending_direction=choose("ending_direction"),
            rationale=f"融合 A 的因果与关系、B 的真相与结局，形成新的故事机制。",
        )
        ref = [a, b]
        dims = ["causal_mechanism", "truth_nature", "character_relation", "ending_direction"]
        best = 0.0
        for other in ref:
            diff = sum(1 for d in dims if getattr(fused, d) != getattr(other, d))
            best = max(best, diff / len(dims))
        fused.distinctness = round(best, 2)
        return fused

    def _fuse_from_llm(self, a: StoryIdea, b: StoryIdea) -> Optional[StoryIdea]:
        prompt = (
            "把下面两个故事方案融合成一个新的、更独特的方案（不是拼接，而是取两者之长形成新的因果机制）。\n"
            f"方案A：因果={a.causal_mechanism}；真相={a.truth_nature}；关系={a.character_relation}；结局={a.ending_direction}\n"
            f"方案B：因果={b.causal_mechanism}；真相={b.truth_nature}；关系={b.character_relation}；结局={b.ending_direction}\n"
            '输出 JSON：{"label":"","premise":"","causal_mechanism":"","truth_nature":"",'
            '"character_relation":"","ending_direction":"","rationale":""}'
        )
        data = generate_json(self.llm, prompt)
        if not data:
            return None
        fused = StoryIdea(
            id="fused",
            label=str(data.get("label", "融合方案")),
            premise=str(data.get("premise", a.premise)),
            causal_mechanism=str(data.get("causal_mechanism", "")),
            truth_nature=str(data.get("truth_nature", "")),
            character_relation=str(data.get("character_relation", "")),
            ending_direction=str(data.get("ending_direction", "")),
            rationale=str(data.get("rationale", "由两个方案融合而成。")),
        )
        if not fused.is_viable:
            return None
        fused.distinctness = max(a.distinctness, b.distinctness, 0.5)
        return fused

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
        turns = self._key_turns(idea)
        book = BookPlan(
            title=self.theme.title or "未命名",
            logline=premise,
            premise=premise,
            question=self.theme.question or self.theme.statement,
            synopsis=(f"{premise}。{idea.causal_mechanism}；{idea.character_relation}。"
                      f"中段，{turns[2]}。最终，{idea.ending_direction}。"),
            opening_state="故事开始时，核心人物尚未意识到问题与自身的关系。",
            inciting_incident=f"一个具体事件打破日常：{premise}",
            central_turn=turns[2],
            climax="所有线索在此汇聚，人物被迫做出代价高昂的选择。",
            resolution=idea.ending_direction,
            main_conflict=f"围绕「{idea.causal_mechanism[:20]}」；{idea.character_relation[:16]}",
            cast=self._cast(),
            key_turns=turns,
            ending=idea.ending_direction,
            structure_template=template,
            chosen_idea=idea,
            params=self.params.to_dict(),
            constraints=self.constraints(),
            expected_chapters=chapters,
            generated_by=OFFLINE,
        ).stamp()

        llm_book = self._book_from_llm(book, premise, idea, chapters, template)
        if llm_book is not None:
            return llm_book
        book = OutlineExpander(self.theme, book.cast).expand(
            book, chapters, template=template,
            seed=seed if seed is not None else (self.params.seed or 0),
        )
        for ch in book.chapters():
            ch.source = OFFLINE
        return book

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
            f"硬约束（所有方案都必须遵守，不得与已确定事实/世界规则冲突，不得提前揭露秘密）：{self._constraints_text()}\n"
            f"故事方向差异度 idea_divergence={self.params.idea_divergence}，因果变化 causal_variation={self.params.causal_variation}\n\n"
            f"请给出 {count} 个**实质不同**的故事方案。每个方案必须改变「因果机制／真相性质／人物关系走向／结局方向」中的至少一项，"
            "而不是换一种写法；且必须遵守上面的硬约束。\n"
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
            idea.generated_by = "llm"
        return ideas

    @staticmethod
    def _chapter_from_dict(citem: Dict[str, Any]) -> ChapterPlan:
        return ChapterPlan(
            number=int(citem.get("number", 0) or 0),
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
        )

    @staticmethod
    def _validate_chapters(chs: List[ChapterPlan], expected: int) -> tuple:
        """Strict: exact count and no empty core fields. Never silently accept."""
        if len(chs) != expected:
            return False, f"章数不符：得到 {len(chs)}，需要 {expected}"
        for c in chs:
            if not (c.conflict and c.outcome and c.summary):
                return False, f"第 {c.number} 章字段不完整"
        return True, ""

    def _llm_blueprint(self, premise, idea, template, chapters):
        prompt = (
            f"故事前提：{premise}\n"
            f"选定方案：因果={idea.causal_mechanism}；真相={idea.truth_nature}；"
            f"关系={idea.character_relation}；结局={idea.ending_direction}\n"
            f"人物：{'、'.join(self._cast())}\n"
            f"结构模板：{TEMPLATE_LABELS.get(template, template)}（{template}）；章节总数={chapters}\n"
            f"硬约束（必须遵守）：{self._constraints_text()}\n\n"
            "第一步：只输出全书蓝图（不要逐章卡片）。各卷 chapter_count 之和必须正好等于章节总数。"
            '输出 JSON：{"logline":"","synopsis":"","opening_state":"","inciting_incident":"",'
            '"central_turn":"","climax":"","resolution":"","main_conflict":"","ending":"",'
            '"key_turns":[""],"volume_count":2,'
            '"volumes":[{"title":"","goal":"","opening_state":"","climax":"","outcome":"",'
            '"sets_up_next":"","chapter_count":0}]}'
        )
        data = generate_json(self.llm, prompt, max_tokens=3000)
        return data if isinstance(data, dict) else None

    def _llm_volume(self, vidx, meta, want, premise, idea, template, prior):
        prior_brief = "；".join(f"第{c.number}章 {c.summary[:24]}" for c in prior[-3:]) or "（本卷为开篇）"
        prompt = (
            f"为第 {vidx + 1} 卷生成**恰好 {want} 章**章节卡片。作品前提：{premise}\n"
            f"方案：因果={idea.causal_mechanism}；结局={idea.ending_direction}\n"
            f"本卷目标：{meta.get('goal', '')}；高潮：{meta.get('climax', '')}；阶段结果：{meta.get('outcome', '')}\n"
            f"前文摘要：{prior_brief}\n"
            f"硬约束（必须遵守）：{self._constraints_text()}\n"
            f"每章必须包含：function/pov/premise/key_action/conflict/outcome/stakes/info_change/"
            f"character_change/threads/motifs/hook_from/hook_to/summary，冲突与结果不得为空。\n"
            '只输出 JSON：{"chapters":[{"title":"","function":"","pov":"","premise":"","key_action":"",'
            '"conflict":"","outcome":"","stakes":"","info_change":"","character_change":"",'
            '"threads":[],"motifs":[],"hook_from":"","hook_to":"","summary":""}]}'
            f"（chapters 数组长度必须等于 {want}）"
        )
        data = generate_json(self.llm, prompt, max_tokens=6000)
        return data if isinstance(data, dict) and isinstance(data.get("chapters"), list) else None

    def _book_from_llm(
        self, book: BookPlan, premise: str, idea: StoryIdea, chapters: int, template: str
    ) -> Optional[BookPlan]:
        """Staged planning: blueprint → per-volume chapters → strict validation.

        Any stage that fails, or a result whose chapter count / fields do not
        match exactly, returns ``None`` so the caller falls back to the clearly
        marked offline template.
        """
        if self.llm is None or getattr(self.llm, "name", "") in ("mock", ""):
            return None

        blueprint = self._llm_blueprint(premise, idea, template, chapters)
        if not blueprint:
            return None
        vcount = blueprint.get("volume_count")
        vcount = int(vcount) if isinstance(vcount, (int, float)) and vcount else (1 if chapters <= 4 else 2 if chapters <= 9 else 3)
        vcount = max(1, min(vcount, chapters))
        sizes = [chapters // vcount + (1 if i < chapters % vcount else 0) for i in range(vcount)]

        metas = blueprint.get("volumes") if isinstance(blueprint.get("volumes"), list) else []
        all_chapters: List[ChapterPlan] = []
        assembled: List[VolumePlan] = []
        for v in range(vcount):
            meta = metas[v] if v < len(metas) and isinstance(metas[v], dict) else {}
            vdata = self._llm_volume(v, meta, sizes[v], premise, idea, template, all_chapters)
            if not vdata:
                return None
            vch = [self._chapter_from_dict(ci) for ci in vdata["chapters"] if isinstance(ci, dict)]
            if len(vch) != sizes[v]:
                return None
            all_chapters.extend(vch)
            assembled.append(VolumePlan(
                number=v + 1, title=str(meta.get("title", f"第{v + 1}卷")),
                goal=str(meta.get("goal", "")), opening_state=str(meta.get("opening_state", "")),
                key_turns=[str(x) for x in meta.get("key_turns", [])],
                climax=str(meta.get("climax", "")), outcome=str(meta.get("outcome", "")),
                sets_up_next=str(meta.get("sets_up_next", "")), chapters=vch))

        ok, _err = self._validate_chapters(all_chapters, chapters)
        if not ok:
            return None

        n = 1
        for vol in assembled:
            for ch in vol.chapters:
                ch.number = n
                ch.source = "llm"
                n += 1

        book.logline = str(blueprint.get("logline", book.logline)) or book.logline
        book.synopsis = str(blueprint.get("synopsis", book.synopsis)) or book.synopsis
        book.opening_state = str(blueprint.get("opening_state", book.opening_state)) or book.opening_state
        book.inciting_incident = str(blueprint.get("inciting_incident", book.inciting_incident)) or book.inciting_incident
        book.central_turn = str(blueprint.get("central_turn", book.central_turn)) or book.central_turn
        book.climax = str(blueprint.get("climax", book.climax)) or book.climax
        book.resolution = str(blueprint.get("resolution", book.resolution)) or book.resolution
        book.main_conflict = str(blueprint.get("main_conflict", book.main_conflict)) or book.main_conflict
        if blueprint.get("key_turns"):
            book.key_turns = [str(x) for x in blueprint["key_turns"]]
        book.ending = str(blueprint.get("ending", book.ending)) or book.ending
        book.volumes = assembled
        book.generated_by = "llm"
        return book
