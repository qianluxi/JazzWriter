"""Persistence: read the score (YAML) and write recordings (takes)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from core.character import Character
from core.harmony import Harmony
from core.motif import MotifLibrary
from core.theme import Theme
from engine.composer import Take
from engine.evaluator import Evaluation

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
CHAPTERS_DIR = OUTPUT_DIR / "chapters"


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_story(path: Optional[Path] = None) -> Tuple[Theme, Harmony]:
    data = _load_yaml(path or (DATA_DIR / "story.yaml"))
    theme = Theme.from_dict(data.get("theme", {}))
    harmony = Harmony.from_dict(data.get("world", {}))
    return theme, harmony


def load_jazz(path: Optional[Path] = None) -> Dict[str, Any]:
    data = _load_yaml(path or (DATA_DIR / "story.yaml"))
    return data.get("jazz", {}) or {}


def load_characters(path: Optional[Path] = None) -> Dict[str, Character]:
    data = _load_yaml(path or (DATA_DIR / "characters.yaml"))
    result: Dict[str, Character] = {}
    for item in data.get("characters", []):
        character = Character.from_dict(item)
        result[character.name] = character
    return result


def load_motifs(path: Optional[Path] = None) -> MotifLibrary:
    data = _load_yaml(path or (DATA_DIR / "motifs.yaml"))
    return MotifLibrary.from_dict(data)


def save_motifs(library: MotifLibrary, path: Optional[Path] = None) -> Path:
    target = path or (DATA_DIR / "motifs.yaml")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(library.to_dict(), fh, allow_unicode=True, sort_keys=False)
    return target


def _slug(text: str) -> str:
    keep = [c for c in text if c.isalnum() or c in "-_"]
    return ("".join(keep).strip("-_") or "take")[:24]


def save_take(
    take: Take,
    evaluation: Optional[Evaluation] = None,
    *,
    outdir: Optional[Path] = None,
    index: int = 1,
) -> Tuple[Path, Path]:
    """Write a take as Markdown (human) + JSON (machine). Returns both paths."""
    base = outdir or CHAPTERS_DIR
    base.mkdir(parents=True, exist_ok=True)
    stem = f"ch{take.chapter:03d}_take{index:02d}_{_slug(take.style)}"
    md_path = base / f"{stem}.md"
    json_path = base / f"{stem}.json"

    header = [
        "---",
        f"chapter: {take.chapter}",
        f"mode: {take.mode}",
        f"style: {take.style}",
        f"pov: {take.pov}",
        f"provider: {take.provider}",
        f"created_at: {take.created_at}",
    ]
    if evaluation:
        header.append(f"grade: {evaluation.grade}")
        header.append(f"overall: {round(evaluation.overall, 3)}")
    header.append("---")
    md_path.write_text("\n".join(header) + "\n\n" + take.text + "\n", encoding="utf-8")

    payload: Dict[str, Any] = {"take": take.to_dict()}
    if evaluation:
        payload["evaluation"] = evaluation.as_dict()
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return md_path, json_path


def read_take(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8")
