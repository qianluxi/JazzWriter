"""WorldStudio: the orchestrator behind the standalone worldview workbench.

Each studio owns an independent data directory ``worlds/<slug>`` holding
``world.json`` (machine) and ``world.md`` (the deliverable). It reuses only the
proven infrastructure (providers, JSON planning helper) and never writes into a
novel project until the author explicitly exports.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from llm import get_provider
from store import ROOT
from world.checker import WorldChecker
from world.expander import WorldExpander
from world.graft import GraftEngine, Skeleton
from world.graph import DependencyGraph
from world.idea_forge import IdeaForge
from world.models import STATES, WorldDoc, WorldIdea
from world import emit
from world.util import is_plain_name, slugify

WORLDS_DIR = ROOT / "worlds"


class WorldStudio:
    def __init__(
        self,
        seed: str,
        *,
        title: str = "",
        slug: str = "",
        root: Optional[Path] = None,
        llm=None,
        provider: Optional[str] = None,
    ) -> None:
        self.root = Path(root) if root else WORLDS_DIR
        self.slug = slug or slugify(title or seed)
        self.llm = llm if llm is not None else get_provider(provider)
        self.forge = IdeaForge(self.llm)
        self.expander = WorldExpander(self.llm)
        self.grafter = GraftEngine(self.llm)
        self.checker = WorldChecker()
        self.doc = WorldDoc(
            title=title or seed[:24] or "未命名世界",
            seed=seed,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            generation=self._generation(),
        )

    # -- construction -------------------------------------------------------
    @classmethod
    def create(
        cls,
        seed: str,
        *,
        title: str = "",
        root: Optional[Path] = None,
        provider: Optional[str] = None,
        llm=None,
    ) -> "WorldStudio":
        studio = cls(seed, title=title, root=root, provider=provider, llm=llm)
        base = studio.root
        slug = studio.slug
        i = 2
        while (base / slug).exists():
            slug = f"{studio.slug}-{i}"
            i += 1
        studio.slug = slug
        return studio

    @property
    def data_dir(self) -> Path:
        return self._validated_dir()

    def _validated_dir(self) -> Path:
        """Resolve ``root/<slug>`` and require it to stay directly under root."""
        root = Path(self.root).resolve()
        if not is_plain_name(self.slug):
            raise ValueError(f"非法世界观名称（slug）：{self.slug!r}")
        target = (root / self.slug).resolve()
        if target.parent != root:
            raise ValueError(f"世界观路径越界：{self.slug!r} 不在 {root}")
        return target

    @property
    def md_path(self) -> Path:
        return self.data_dir / "world.md"

    @property
    def json_path(self) -> Path:
        return self.data_dir / "world.json"

    def _generation(self) -> str:
        name = getattr(self.llm, "name", "") if self.llm is not None else ""
        return "llm" if name and name != "mock" else "offline_template"

    # -- spark mode ---------------------------------------------------------
    def raise_ideas(self, count: int = 4) -> List[WorldIdea]:
        self.doc.ideas = self.forge.ideas(self.doc.seed, count=count)
        self.doc.generation = self._generation()
        return self.doc.ideas

    def choose(self, ref: str) -> WorldIdea:
        idea = self._resolve_idea(ref)
        idea.status = "confirmed"
        self.doc.chosen_idea = idea
        return idea

    def grow(self) -> WorldDoc:
        if self.doc.chosen_idea is None:
            raise ValueError("先 choose 一个世界原型，再 grow")
        self.doc.generation = self._generation()
        return self.expander.expand(self.doc)

    def check(self):
        return self.checker.check(self.doc, self.llm)

    def impact(self, entity_id: str) -> dict:
        return DependencyGraph(self.doc).impact_report(entity_id)

    def duplicate_warnings(self) -> List[str]:
        return self.forge.duplicate_warnings(self.doc.ideas)

    def set_state(self, ref: str, state: str) -> WorldEntity:
        if state not in STATES:
            raise ValueError(f"unknown state: {state}（可用：{', '.join(STATES)}）")
        entity = self.doc.by_id(ref)
        if entity is None:
            raise KeyError(f"unknown entity: {ref}")
        entity.state = state
        if state != "confirmed":
            entity.locked = False
        return entity

    def lock(self, ref: str, locked: bool = True) -> None:
        entity = self.doc.by_id(ref)
        if entity is None:
            raise KeyError(f"unknown entity: {ref}")
        self.doc.lock(ref, locked)

    def edit(
        self,
        ref: str,
        *,
        name: Optional[str] = None,
        statement: Optional[str] = None,
        basis: Optional[str] = None,
        state: Optional[str] = None,
        confirm: bool = False,
    ) -> dict:
        """Edit a structured entry, preserving id / source / depends_on / lock.

        Editing a locked or already-confirmed entry requires ``confirm=True``.
        Editing a rule's statement returns the downstream entries to re-review.
        """
        entity = self.doc.by_id(ref)
        if entity is None:
            raise KeyError(f"unknown entity: {ref}")
        if (entity.locked or entity.state == "confirmed") and not confirm:
            raise ValueError(f"条目 {ref} 已锁定或已确认，需显式确认（confirm=True）才能修改。")
        if state is not None and state not in STATES:
            raise ValueError(f"unknown state: {state}（可用：{', '.join(STATES)}）")
        changed: List[str] = []
        for field, value in (("name", name), ("statement", statement), ("basis", basis)):
            if value is not None and getattr(entity, field) != value:
                setattr(entity, field, value)
                changed.append(field)
        if state is not None and entity.state != state:
            entity.state = state
            changed.append("state")
        result: dict = {"entity": entity.id, "changed": changed}
        if entity.kind == "rule" and ("statement" in changed or "name" in changed):
            report = DependencyGraph(self.doc).impact_report(entity.id)
            result["reverify"] = report["candidates"]
            result["affected"] = report["transitive"]
        return result

    # -- graft mode ---------------------------------------------------------
    def graft(
        self,
        source_text: str,
        op: str,
        *,
        source_name: str = "",
        second_text: Optional[str] = None,
    ) -> WorldDoc:
        if op == "世界交叉" and not second_text:
            raise ValueError("「世界交叉」需要第二份材料（second_text）。")
        skeleton = self.grafter.extract(source_text, source_name=source_name, title=self.doc.title)
        second = self.grafter.extract(second_text, source_name="外来材料") if second_text else None
        doc, _ = self.grafter.transform(skeleton, op, self.doc.seed, second=second)
        doc.created_at = self.doc.created_at
        self.doc = doc
        return self.doc

    @classmethod
    def graft_new(
        cls,
        seed: str,
        source_text: str,
        op: str,
        *,
        source_name: str = "",
        second_text: Optional[str] = None,
        root: Optional[Path] = None,
        provider: Optional[str] = None,
        llm=None,
    ) -> "WorldStudio":
        """Derive a **new** world from a source, leaving any current world intact."""
        studio = cls.create(seed, title=f"{op}·{seed}", root=root, provider=provider, llm=llm)
        studio.graft(source_text, op, source_name=source_name, second_text=second_text)
        return studio

    def skeleton(self, source_text: str, *, source_name: str = "") -> Skeleton:
        return self.grafter.extract(source_text, source_name=source_name, title=self.doc.title)

    # -- persistence --------------------------------------------------------
    def save(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.doc.to_dict(), ensure_ascii=False, indent=2)
        self._atomic_write(self.json_path, payload)
        return self.json_path

    def export(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._atomic_write(self.md_path, emit.build_markdown(self.doc))
        self.save()
        return self.md_path

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        """Write via a same-directory temp file + atomic replace, keeping one backup."""
        tmp = path.parent / (path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        if path.exists():
            backup = path.parent / (path.name + ".bak")
            try:
                backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            except OSError:
                pass
        os.replace(tmp, path)

    @classmethod
    def load(cls, slug: str, *, root: Optional[Path] = None, provider: Optional[str] = None, llm=None) -> "WorldStudio":
        root = Path(root) if root else WORLDS_DIR
        if not is_plain_name(slug):
            raise ValueError(f"非法世界观名称（slug）：{slug!r}")
        root_resolved = root.resolve()
        target = (root_resolved / slug).resolve()
        if target.parent != root_resolved:
            raise ValueError(f"世界观路径越界：{slug!r}")
        path = target / "world.json"
        if not path.exists():
            raise FileNotFoundError(f"no such world: {slug}")
        data = json.loads(path.read_text(encoding="utf-8"))
        studio = cls(data.get("seed", ""), slug=slug, root=root, provider=provider, llm=llm)
        studio.doc = WorldDoc.from_dict(data)
        return studio

    def status(self) -> dict:
        return {
            "slug": self.slug,
            "title": self.doc.title,
            "seed": self.doc.seed,
            "ideas": len(self.doc.ideas),
            "chosen": self.doc.chosen_idea.label if self.doc.chosen_idea else None,
            "entities": len(self.doc.entities),
            "open_questions": len(self.doc.open_questions),
            "contradictions": len(self.doc.contradictions),
            "generation": self.doc.generation,
        }

    # -- helpers ------------------------------------------------------------
    def _resolve_idea(self, ref: str) -> WorldIdea:
        for i, idea in enumerate(self.doc.ideas, start=1):
            if ref in (idea.id, idea.label, str(i)):
                return idea
        raise KeyError(f"unknown idea: {ref}")
