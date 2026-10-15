"""Memory & deviation — lightweight semantic memory over the book.

Three layers, mirroring the expert's recommendation:

* exact state       — facts / timeline / knowledge (see core.story_state)
* structured memory — arcs, threads, motif evolution (read from BookPlan)
* semantic memory   — similar situations, near-duplicate passages (this module)

Embeddings are optional: the lexical vector (CJK bigrams) always works offline
and is good enough to *find* suspect passages; final fact checks stay rule-based.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, pstdev
from typing import Dict, List, Optional, Tuple

from core.book_plan import BookPlan
from core.chapter_plan import ChapterPlan
from core.motif import MotifLibrary
from core.story_state import StoryState
from core.theme import Theme
from engine import semantic_similarity as sem
from engine import textutil as tu


@dataclass
class MemoryItem:
    id: str
    kind: str
    number: int
    text: str
    vector: Dict[str, float] = field(default_factory=dict)


class MemoryIndex:
    def __init__(self) -> None:
        self.items: List[MemoryItem] = []

    def add(self, item_id: str, kind: str, number: int, text: str) -> None:
        self.items.append(MemoryItem(item_id, kind, number, text, tu.vector(text)))

    def add_book(self, book: BookPlan) -> "MemoryIndex":
        for ch in book.chapters():
            self.add(ch.id, "chapter", ch.number, chapter_text(ch))
        return self

    def query(self, text: str, k: int = 3) -> List[Tuple[float, MemoryItem]]:
        v = tu.vector(text)
        scored = [(tu.cosine(v, it.vector), it) for it in self.items]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:k]

    def duplicates(self, threshold: float = 0.55) -> List[Dict]:
        out: List[Dict] = []
        for i in range(len(self.items)):
            for j in range(i + 1, len(self.items)):
                a, b = self.items[i], self.items[j]
                s = tu.cosine(a.vector, b.vector)
                if s >= threshold:
                    out.append({"a": a.id, "b": b.id, "score": round(s, 3),
                                "a_number": a.number, "b_number": b.number})
        out.sort(key=lambda d: d["score"], reverse=True)
        return out


def chapter_text(ch: ChapterPlan) -> str:
    return " ".join(v for v in (ch.summary, ch.conflict, ch.outcome,
                                ch.key_action, ch.hook_to, ch.character_change) if v)


@dataclass
class DeviationReport:
    theme_similarity: List[Dict] = field(default_factory=list)
    drift_chapters: List[int] = field(default_factory=list)
    duplicates: List[Dict] = field(default_factory=list)
    arc_gaps: List[str] = field(default_factory=list)
    motif_usage: Dict[str, int] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict:
        return {
            "theme_similarity": self.theme_similarity,
            "drift_chapters": self.drift_chapters,
            "duplicates": self.duplicates,
            "arc_gaps": self.arc_gaps,
            "motif_usage": self.motif_usage,
            "issues": self.issues,
        }


def analyze_book(
    book: BookPlan,
    theme: Theme,
    *,
    motifs: Optional[MotifLibrary] = None,
    story_state: Optional[StoryState] = None,
    dup_threshold: float = 0.55,
) -> DeviationReport:
    report = DeviationReport()
    chapters = book.chapters()
    if not chapters:
        report.issues.append("尚未生成结构，无法分析。")
        return report

    # -- theme drift (semantic similarity of each chapter to the theme) -----
    theme_text = " ".join(theme.keywords)
    sims: List[float] = []
    for ch in chapters:
        s = sem.similarity(chapter_text(ch), theme_text) if theme_text else 0.0
        sims.append(s)
        report.theme_similarity.append({"number": ch.number, "score": round(s, 3)})
    if len(sims) >= 3 and pstdev(sims) > 1e-6:
        m, sd = mean(sims), pstdev(sims)
        for ch, s in zip(chapters, sims):
            if s < m - 1.5 * sd and s < 0.5 * m:
                report.drift_chapters.append(ch.number)
        if report.drift_chapters:
            report.issues.append(
                "主题偏离：第 " + "、".join(map(str, report.drift_chapters))
                + " 章与全书主题的关联明显偏弱，确认是否有意为之。")

    # -- near-duplicate chapters --------------------------------------------
    index = MemoryIndex().add_book(book)
    report.duplicates = index.duplicates(dup_threshold)
    for dup in report.duplicates[:3]:
        report.issues.append(
            f"疑似重复：第 {dup['a_number']} 章与第 {dup['b_number']} 章高度相似（{dup['score']:.0%}）。")

    # -- character arc coverage ---------------------------------------------
    cast = book.cast or []
    for name in cast:
        touched = any(name in (c.character_change or "") or c.pov == name and c.character_change
                      for c in chapters)
        if not touched:
            report.arc_gaps.append(name)
    if report.arc_gaps:
        report.issues.append("人物弧缺失：" + "、".join(report.arc_gaps) + " 全程没有可见变化。")

    # -- motif usage --------------------------------------------------------
    mnames = motifs.names() if motifs else list(theme.motifs)
    for name in mnames:
        report.motif_usage[name] = sum(1 for c in chapters if name in c.motifs)
        if report.motif_usage[name] == 0:
            report.issues.append(f"意象「{name}」在结构中出现 0 次，可能未被使用。")

    # -- continuity (premature reveal in cards) -----------------------------
    if story_state is not None:
        blob = "\n".join(chapter_text(c) for c in chapters)
        hits = [f for f in story_state.forbidden_reveals() if f and f in blob]
        if hits:
            report.issues.append("结构卡片中疑似提前揭露：" + "；".join(hits[:3]) + "。")

    if not report.issues:
        report.issues.append("未发现明显偏离：主题关联、人物弧、意象与连续性基本一致。")
    return report
