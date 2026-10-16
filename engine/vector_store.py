"""Vector memory — a persistent, embedding-optional semantic store.

Unlike the in-memory lexical `MemoryIndex`, this keeps vectors on disk so a
long project can be searched across sessions. It uses a real embedding model
when one is available (sentence-transformers) and degrades to CJK-bigram
lexical vectors otherwise — same interface either way.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from engine import semantic_similarity as sem
from engine import textutil as tu


def _cos_list(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


@dataclass
class VItem:
    id: str
    kind: str
    number: int
    text: str
    lex: Dict[str, float] = field(default_factory=dict)
    emb: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "number": self.number,
                "text": self.text, "emb": self.emb}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "VItem":
        text = d.get("text", "")
        return cls(d.get("id", ""), d.get("kind", ""), int(d.get("number", 0)),
                   text, tu.vector(text), d.get("emb"))


class VectorStore:
    def __init__(self, *, use_embedding: bool = True) -> None:
        self.use_embedding = use_embedding
        self.items: List[VItem] = []
        self.backend = "lexical"

    # -- building -----------------------------------------------------------
    def add_many(self, rows: List[Tuple[str, str, int, str]]) -> "VectorStore":
        texts = [t for (*_, t) in rows]
        embs: List[Optional[List[float]]] = [None] * len(texts)
        if self.use_embedding:
            vecs = sem._embed(texts)
            if vecs is not None:
                embs = vecs
                self.backend = "embedding"
        for (iid, kind, number, text), emb in zip(rows, embs):
            self.items.append(VItem(iid, kind, number, text, tu.vector(text), emb))
        return self

    def add(self, iid: str, kind: str, number: int, text: str) -> "VectorStore":
        return self.add_many([(iid, kind, number, text)])

    def rebuild_from_book(self, book) -> "VectorStore":
        rows = []
        for ch in book.chapters():
            rows.append((ch.id, "chapter", ch.number,
                         " ".join(v for v in (ch.summary, ch.conflict, ch.outcome,
                                              ch.key_action, ch.hook_to, ch.character_change) if v)))
        return self.add_many(rows)

    # -- query --------------------------------------------------------------
    def _qvec(self, text: str):
        if self.backend == "embedding":
            v = sem._embed([text])
            if v is not None:
                return "emb", v[0]
        return "lex", tu.vector(text)

    def query(self, text: str, k: int = 3, kind: Optional[str] = None
              ) -> List[Tuple[float, VItem]]:
        mode, qv = self._qvec(text)
        out: List[Tuple[float, VItem]] = []
        for it in self.items:
            if kind and it.kind != kind:
                continue
            if mode == "emb" and it.emb is not None:
                s = _cos_list(qv, it.emb)
            else:
                s = tu.cosine(qv, it.lex)
            out.append((s, it))
        out.sort(key=lambda x: x[0], reverse=True)
        return out[:k]

    def __len__(self) -> int:
        return len(self.items)

    # -- persistence --------------------------------------------------------
    def save(self, path: Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {"backend": self.backend,
                   "items": [it.to_dict() for it in self.items]}
        target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: Path, *, use_embedding: bool = True) -> "VectorStore":
        store = cls(use_embedding=use_embedding)
        target = Path(path)
        if not target.exists():
            return store
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return store
        store.backend = payload.get("backend", "lexical")
        store.items = [VItem.from_dict(d) for d in payload.get("items", [])]
        return store
