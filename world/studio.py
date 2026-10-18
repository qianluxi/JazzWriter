"""WorldStudio: the orchestrator behind the standalone worldview workbench.

Each studio owns an independent data directory ``worlds/<slug>`` holding
``world.json`` (machine) and ``world.md`` (the deliverable). It reuses only the
proven infrastructure (providers, JSON planning helper) and never writes into a
novel project until the author explicitly exports.
"""

from __future__ import annotations

import json
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
from world.util import slugify

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
        return self.root / self.slug

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

    # -- graft mode ---------------------------------------------------------
    def graft(
        self,
        source_text: str,
        op: str,
        *,
        source_name: str = "",
        second_text: Optional[str] = None,
    ) -> WorldDoc:
        skeleton = self.grafter.extract(source_text, source_name=source_name, title=self.doc.title)
        second = self.grafter.extract(second_text, source_name="外来材料") if second_text else None
        doc, _ = self.grafter.transform(skeleton, op, self.doc.seed, second=second)
        doc.created_at = self.doc.created_at
        self.doc = doc
        return self.doc

    def skeleton(self, source_text: str, *, source_name: str = "") -> Skeleton:
        return self.grafter.extract(source_text, source_name=source_name, title=self.doc.title)

    # -- persistence --------------------------------------------------------
    def save(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.json_path.write_text(
            json.dumps(self.doc.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return self.json_path

    def export(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = emit.write_markdown(self.doc, self.md_path)
        self.save()
        return path

    @classmethod
    def load(cls, slug: str, *, root: Optional[Path] = None, provider: Optional[str] = None, llm=None) -> "WorldStudio":
        root = Path(root) if root else WORLDS_DIR
        path = root / slug / "world.json"
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
