"""Theme — the "head" melody of the novel.

In jazz the head (e.g. the two phrases of *So What*) is stated then varied.
Here the theme is a proposition the whole novel improvises around. It must
never be stated literally; it should be *heard* through detail.
"""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import Field

from core.base import Model


class Theme(Model):
    title: str = ""
    question: str = ""
    statement: str = ""
    emotions: List[str] = Field(default_factory=list)
    symbols: List[str] = Field(default_factory=list)
    motifs: List[str] = Field(default_factory=list)

    def describe(self) -> Dict[str, Any]:
        """Structured view, kept close to the spec's `describe()`."""
        return {
            "主题": self.title,
            "核心问题": self.question,
            "主题陈述": self.statement,
            "情绪": list(self.emotions),
            "象征": list(self.symbols),
            "动机": list(self.motifs),
        }

    def as_prompt(self) -> str:
        lines = [f"主题命题: {self.title or '(未命名)'}"]
        if self.question:
            lines.append(f"核心追问(不可直说): {self.question}")
        if self.statement:
            lines.append(f"主题陈述(只能被暗示): {self.statement}")
        if self.emotions:
            lines.append("情绪色彩: " + "、".join(self.emotions))
        if self.symbols:
            lines.append("象征物: " + "、".join(self.symbols))
        if self.motifs:
            lines.append("核心动机: " + "、".join(self.motifs))
        return "\n".join(lines) if lines else "(空主题)"

    @property
    def keywords(self) -> List[str]:
        """Lexical anchors used by the evaluator."""
        out: List[str] = []
        out.extend(self.symbols)
        out.extend(self.motifs)
        out.extend(self.emotions)
        if self.statement:
            out.append(self.statement)
        if self.question:
            out.append(self.question)
        if self.title:
            out.append(self.title)
        return [k for k in out if k]
