"""Small text helpers for worldview work (CJK-friendly, dependency free)."""

from __future__ import annotations

import re
from typing import List

_CLAUSE_SPLIT = re.compile(r"[。！？；，、,.!?;:\n\r\t]+")
_STOP = {
    "一个", "一种", "这个", "那个", "他们", "我们", "你们", "自己", "因为", "所以",
    "但是", "而且", "可以", "已经", "没有", "什么", "怎么", "如果", "只是", "只有",
}


def clauses(text: str) -> List[str]:
    parts = [p.strip() for p in _CLAUSE_SPLIT.split(text or "")]
    return [p for p in parts if p]


def terms(text: str, limit: int = 6) -> List[str]:
    """Distinctive phrases: 2-10 char clauses, minus a tiny stop list."""
    out: List[str] = []
    for part in clauses(text):
        if 2 <= len(part) <= 10 and part not in _STOP and part not in out:
            out.append(part)
        if len(out) >= limit:
            break
    return out


def slugify(text: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", (text or "").strip())
    return (s.strip("-")[:40]) or "world"


def is_plain_name(name: str) -> bool:
    """A slug must be a single directory name: no separators, no traversal."""
    if not name or name in (".", ".."):
        return False
    if any(sep in name for sep in ("/", "\\", ":", "\0")):
        return False
    return ".." not in name
