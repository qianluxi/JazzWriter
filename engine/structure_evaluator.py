"""Structure evaluator — score the *story*, not the prose.

Six dimensions, each reported with concrete issues (and *not* folded into one
authoritative number). Open endings / slow chapters are not mechanically
punished: the report says so explicitly when a template permits them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.book_plan import BookPlan
from engine import textutil as tu
from engine.narrative_reviewer import NarrativeReviewer
from engine.plot_validator import OPEN_TEMPLATES, PlotValidator

DIMENSIONS = {
    "idea_uniqueness": "创意独特性",
    "completeness": "故事完整性",
    "causal_continuity": "因果连续性",
    "character_change": "人物变化",
    "chapter_contribution": "章节贡献",
    "foreshadowing": "伏笔与回收",
}


@dataclass
class StructureReport:
    dimensions: Dict[str, float]
    overall: float
    validation: List[str] = field(default_factory=list)   # layer 1: hard checks
    review: List[Dict] = field(default_factory=list)      # layer 2: narrative
    notes: List[str] = field(default_factory=list)

    @property
    def issues(self) -> List[str]:
        """Backward-compatible view of the hard validation issues."""
        return self.validation

    def as_dict(self) -> Dict:
        return {
            "dimensions": {k: round(v, 3) for k, v in self.dimensions.items()},
            "overall": round(self.overall, 3),
            "validation": self.validation,
            "review": self.review,
            "notes": self.notes,
        }


class StructureEvaluator:
    def __init__(self, reviewer: Optional[NarrativeReviewer] = None, relationships=None) -> None:
        self.reviewer = reviewer
        self.relationships = relationships

    def evaluate(self, book: BookPlan) -> StructureReport:
        chapters = book.chapters()
        n = max(1, len(chapters))
        notes: List[str] = []

        # 1. idea uniqueness
        distinct = (book.chosen_idea.distinctness if book.chosen_idea else 0.5) or 0.5
        motifs_used = {m for ch in chapters for m in ch.motifs}
        motif_variety = min(1.0, len(motifs_used) / 6)
        idea = tu.clamp(0.6 * distinct + 0.4 * motif_variety)

        # 2. completeness
        has_q = 1.0 if (book.question or book.logline) else 0.0
        has_end = 1.0 if book.ending else 0.0
        last = chapters[-1] if chapters else None
        responds = 1.0 if (last and any(k in f"{last.outcome}{last.hook_to}{book.ending}"
                                        for k in ("回应", "回答", "理解", "问题", "命题"))) else 0.4
        completeness = tu.clamp((has_q + has_end + responds) / 3)

        # 3. causal continuity
        well_formed = sum(1 for c in chapters if c.premise and c.outcome) / n
        chained = 0
        pairs = list(zip(chapters, chapters[1:]))
        for prev, cur in pairs:
            if prev.hook_to and cur.hook_from and prev.hook_to.strip() == cur.hook_from.strip():
                chained += 1
        chain_ratio = chained / len(pairs) if pairs else 1.0
        causal = tu.clamp(0.5 * well_formed + 0.5 * chain_ratio)

        # 4. character change
        change_ratio = sum(1 for c in chapters if c.character_change) / n
        povs = {c.pov for c in chapters if c.pov}
        pov_ratio = len(povs) / max(1, len(book.cast))
        character = tu.clamp(0.6 * change_ratio + 0.4 * min(1.0, pov_ratio))

        # 5. chapter contribution
        contrib = sum(
            1 for c in chapters
            if c.function and (c.threads or c.motifs or c.character_change)
        ) / n
        contribution = tu.clamp(contrib)

        # 6. foreshadowing
        app: Dict[str, int] = {}
        for c in chapters:
            for t in c.threads:
                app[t] = app.get(t, 0) + 1
        if app:
            closed = sum(1 for v in app.values() if v >= 2)
            foreshadow = tu.clamp(closed / len(app))
        else:
            foreshadow = 0.4
            notes.append("未检测到明确线索，伏笔维度参考价值有限。")

        dims = {
            "idea_uniqueness": idea,
            "completeness": completeness,
            "causal_continuity": causal,
            "character_change": character,
            "chapter_contribution": contribution,
            "foreshadowing": foreshadow,
        }
        overall = sum(dims.values()) / len(dims)

        validation = [i.message for i in PlotValidator().validate(book, relationships=self.relationships)]
        reviewer = self.reviewer or NarrativeReviewer()
        review = [f.to_dict() for f in reviewer.review(book)]
        if book.structure_template in OPEN_TEMPLATES:
            notes.append("该结构模板允许开放结局；未回收的线索不一定算缺陷。")
        notes.append("问题清单优先于分数：请先看具体问题，再决定方案是否值得写。")
        return StructureReport(dimensions=dims, overall=overall,
                               validation=validation, review=review, notes=notes)
