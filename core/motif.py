"""Motif — a recurring figure whose *meaning* mutates.

A motif is not just a repeated word; it is the same thing signifying something
new each time it returns (蒸汽 = 工业力量 → 危险 → 生命 → 文明代价).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class Motif:
    def __init__(self, name: str, note: str = "") -> None:
        self.name = name
        self.note = note
        self.history: List[Dict[str, Any]] = []

    # -- mutation of meaning ------------------------------------------------
    def add_usage(self, chapter: int, meaning: str = "", quote: str = "") -> None:
        self.history.append(
            {"chapter": chapter, "meaning": meaning, "quote": quote}
        )

    def trace(self) -> List[Dict[str, Any]]:
        return list(self.history)

    @property
    def count(self) -> int:
        return len(self.history)

    @property
    def latest_meaning(self) -> str:
        return self.history[-1]["meaning"] if self.history else ""

    @property
    def meanings(self) -> List[str]:
        return [h["meaning"] for h in self.history if h["meaning"]]

    def as_prompt(self) -> str:
        if not self.history:
            return f"- {self.name}: 尚未出现" + (f"（{self.note}）" if self.note else "")
        seen = " → ".join(m or "?" for m in self.meanings) or "?"
        return f"- {self.name}: 已出现 {self.count} 次，意义演变 [{seen}]；本次需给出新一轮变奏"

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "note": self.note, "history": self.history}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Motif":
        motif = cls(data.get("name", ""), data.get("note", ""))
        motif.history = list(data.get("history", []))
        return motif


class MotifLibrary:
    """A collection of motifs with lightweight persistence helpers."""

    def __init__(self, motifs: Optional[List[Motif]] = None) -> None:
        self._motifs: Dict[str, Motif] = {}
        for motif in motifs or []:
            self._motifs[motif.name] = motif

    def get(self, name: str) -> Motif:
        if name not in self._motifs:
            self._motifs[name] = Motif(name)
        return self._motifs[name]

    def ensure(self, names: List[str]) -> None:
        for name in names:
            self.get(name)

    def add_usage(self, name: str, chapter: int, meaning: str = "", quote: str = "") -> Motif:
        motif = self.get(name)
        motif.add_usage(chapter, meaning, quote)
        return motif

    def all(self) -> List[Motif]:
        return [self._motifs[k] for k in sorted(self._motifs.keys())]

    def names(self) -> List[str]:
        return [m.name for m in self.all()]

    def as_prompt(self, only: Optional[List[str]] = None) -> str:
        selected = [self.get(n) for n in only] if only else self.all()
        if not selected:
            return "(暂无动机)"
        return "\n".join(m.as_prompt() for m in selected)

    def to_dict(self) -> Dict[str, Any]:
        return {"motifs": [m.to_dict() for m in self.all()]}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MotifLibrary":
        return cls([Motif.from_dict(d) for d in data.get("motifs", [])])
