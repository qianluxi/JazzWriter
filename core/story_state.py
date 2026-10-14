"""StoryState — the lightweight "story bible" for long-form continuity.

The single most important distinction here is between *kinds of truth*:

- established fact   — has happened, in the world (status="confirmed")
- suspected          — a character believes/mistrusts it, unproven
- secret             — the author knows it; the characters do not
- candidate          — a creative proposal not yet adopted as canon

Nothing random may silently overwrite a confirmed fact, and no character may
know a secret before the story gives them a source. Keeping these apart is what
lets a novel survive dozens of improvised chapters.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import Field

from core.base import Model

FACT_STATUS = ("confirmed", "suspected", "secret", "candidate")
THREAD_STATUS = ("open", "hinted", "revealed", "closed")


class Fact(Model):
    id: str
    statement: str
    first_chapter: int = 0
    status: str = "confirmed"  # confirmed | suspected | secret | candidate
    tags: List[str] = Field(default_factory=list)


class CharacterKnowledge(Model):
    known: List[str] = Field(default_factory=list)      # fact ids they know
    suspected: List[str] = Field(default_factory=list)  # fact ids they suspect
    unknown: List[str] = Field(default_factory=list)    # fact ids they must not know
    secrets: List[str] = Field(default_factory=list)    # things they hide


class Thread(Model):
    id: str
    question: str
    introduced_chapter: int = 0
    status: str = "open"  # open | hinted | revealed | closed
    reveal_before_chapter: Optional[int] = None


class Event(Model):
    chapter: int
    event: str


class StoryState(Model):
    chapter: int = 0
    established_facts: List[Fact] = Field(default_factory=list)
    character_knowledge: Dict[str, CharacterKnowledge] = Field(default_factory=dict)
    open_threads: List[Thread] = Field(default_factory=list)
    recent_events: List[Event] = Field(default_factory=list)

    # -- lookups ------------------------------------------------------------
    def fact(self, fact_id: str) -> Optional[Fact]:
        for f in self.established_facts:
            if f.id == fact_id:
                return f
        return None

    def facts(self, *statuses: str) -> List[Fact]:
        if not statuses:
            return list(self.established_facts)
        return [f for f in self.established_facts if f.status in statuses]

    def confirmed(self) -> List[Fact]:
        return self.facts("confirmed")

    def secrets(self) -> List[Fact]:
        return self.facts("secret")

    def knowledge(self, name: str) -> CharacterKnowledge:
        if name not in self.character_knowledge:
            self.character_knowledge[name] = CharacterKnowledge()
        return self.character_knowledge[name]

    def open_thread_list(self) -> List[Thread]:
        return [t for t in self.open_threads if t.status in ("open", "hinted")]

    def threads_due(self, chapter: int) -> List[Thread]:
        out = []
        for t in self.open_thread_list():
            if t.reveal_before_chapter is not None and chapter >= t.reveal_before_chapter:
                out.append(t)
        return out

    # -- constraints --------------------------------------------------------
    def protected_statements(self) -> List[str]:
        """Confirmed facts that no improvised change may contradict."""
        return [f.statement for f in self.confirmed()]

    def forbidden_reveals(self, pov: Optional[str] = None) -> List[str]:
        """Things this scene must NOT reveal yet.

        Secrets the POV cannot know, plus open threads that are not due.
        """
        items = [f.statement for f in self.secrets()]
        if pov:
            k = self.knowledge(pov)
            for fid in k.unknown:
                fact = self.fact(fid)
                if fact:
                    items.append(fact.statement)
        seen = set()
        out = []
        for item in items:
            if item and item not in seen:
                seen.add(item)
                out.append(item)
        return out

    # -- prompt view --------------------------------------------------------
    def summary(self) -> str:
        lines: List[str] = []
        if self.chapter:
            lines.append(f"当前进度: 第 {self.chapter} 章")
        confirmed = self.confirmed()
        if confirmed:
            lines.append("已确定的事实(不可篡改):")
            lines += [f"  - [{f.id}] {f.statement}" for f in confirmed]
        suspected = self.facts("suspected")
        if suspected:
            lines.append("人物怀疑但未证实:")
            lines += [f"  - [{f.id}] {f.statement}" for f in suspected]
        secrets = self.secrets()
        if secrets:
            lines.append("作者已知的秘密(人物尚不知情，不可提前揭露):")
            lines += [f"  - [{f.id}] {f.statement}" for f in secrets]
        threads = self.open_thread_list()
        if threads:
            lines.append("未解决的线索:")
            lines += [f"  - [{t.id}] {t.question}（状态 {t.status}）" for t in threads]
        if self.recent_events:
            lines.append("近期事件:")
            lines += [f"  - 第 {e.chapter} 章: {e.event}" for e in self.recent_events[-5:]]
        return "\n".join(lines) if lines else "(尚未建立故事状态)"

    def as_constraints(self) -> List[str]:
        out = []
        if self.confirmed():
            out.append("不得与已确定的事实矛盾")
        if self.secrets() or self.open_thread_list():
            out.append("不得提前揭露作者保留的秘密或未到期的线索")
        return out

    def record_event(self, chapter: int, event: str) -> None:
        self.recent_events.append(Event(chapter=chapter, event=event))
        self.chapter = max(self.chapter, chapter)
