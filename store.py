"""Persistence: read the score (YAML) and write recordings (takes)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from core.book_plan import BookPlan
from core.character import Character
from core.harmony import Harmony
from core.motif import MotifLibrary
from core.relationship import RelationshipMap
from core.story_state import StoryState
from core.theme import Theme
from engine.composer import Take
from engine.evaluator import Evaluation

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
PREVIEW_DIR = ROOT / "preview"
OUTPUT_DIR = ROOT / "output"
CHAPTERS_DIR = OUTPUT_DIR / "chapters"
RUNS_DIR = OUTPUT_DIR / "runs"
ADVICE_PATH = OUTPUT_DIR / "advice_history.jsonl"
BOOK_PLAN_PATH = OUTPUT_DIR / "book_plan.json"
BOOK_OUTLINE_PATH = OUTPUT_DIR / "book_outline.md"
VECTOR_STORE_PATH = OUTPUT_DIR / "vector_store.json"
STATE_PATH = DATA_DIR / "story_state.yaml"
JAZZ_STATE_PATH = DATA_DIR / "jazz_state.yaml"
MOTIF_DEF_PATH = DATA_DIR / "motifs.yaml"
MOTIF_STATE_PATH = DATA_DIR / "motif_state.yaml"
RELATIONSHIPS_PATH = DATA_DIR / "relationships.yaml"


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
    """Load characters keyed by *stable id* (falls back to name).

    Keying by name silently dropped characters that share a display name; keying
    by ``effective_id`` keeps every character so relationship endpoints resolve
    and duplicate-id checks can see them.
    """
    data = _load_yaml(path or (DATA_DIR / "characters.yaml"))
    result: Dict[str, Character] = {}
    for item in data.get("characters", []):
        character = Character.from_dict(item)
        key = character.effective_id
        if key in result:  # duplicate stable id -> keep both under a unique key
            i = 2
            while f"{key}#{i}" in result:
                i += 1
            key = f"{key}#{i}"
        result[key] = character
    return result


def load_relationships(path: Optional[Path] = None) -> RelationshipMap:
    data = _load_yaml(path or RELATIONSHIPS_PATH)
    return RelationshipMap.from_dict(data) if data else RelationshipMap()


def save_relationships(rel_map: RelationshipMap, path: Optional[Path] = None) -> Path:
    target = path or RELATIONSHIPS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(rel_map.to_dict(), fh, allow_unicode=True, sort_keys=False)
    return target


def load_motifs(
    path: Optional[Path] = None,
    state_path: Optional[Path] = None,
) -> MotifLibrary:
    """Load motif *definitions* from motifs.yaml, then overlay runtime history
    from the (gitignored) motif_state.yaml so the tracked sample stays clean."""
    data = _load_yaml(path or MOTIF_DEF_PATH)
    library = MotifLibrary.from_dict(data)
    state = _load_yaml(state_path or MOTIF_STATE_PATH)
    if state:
        for item in state.get("motifs", []):
            name = item.get("name")
            if not name:
                continue
            motif = library.get(name)
            if item.get("note"):
                motif.note = item["note"]
            motif.history = list(item.get("history", []))
    return library


def save_motifs(library: MotifLibrary, path: Optional[Path] = None) -> Path:
    """Persist runtime history to motif_state.yaml (not the tracked definitions)."""
    target = path or MOTIF_STATE_PATH
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


# -- run records (full, reproducible performance logs) -------------------------
def save_run(record: Dict[str, Any], *, outdir: Optional[Path] = None) -> Path:
    base = outdir or RUNS_DIR
    base.mkdir(parents=True, exist_ok=True)
    run_id = record.get("run_id") or "run"
    path = base / f"{run_id}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_runs(*, outdir: Optional[Path] = None) -> List[Dict[str, Any]]:
    base = outdir or RUNS_DIR
    if not base.exists():
        return []
    records: List[Dict[str, Any]] = []
    for path in sorted(base.glob("*.json")):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return records


def load_run(run_id: str, *, outdir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    base = outdir or RUNS_DIR
    path = base / f"{run_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# -- story state (lightweight story bible) -------------------------------------
def load_story_state(path: Optional[Path] = None) -> StoryState:
    data = _load_yaml(path or STATE_PATH)
    return StoryState.from_dict(data) if data else StoryState()


def save_story_state(state: StoryState, path: Optional[Path] = None) -> Path:
    target = path or STATE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(state.to_dict(), fh, allow_unicode=True, sort_keys=False)
    return target


# -- jazz runtime state & advice history ---------------------------------------
def load_jazz_state(path: Optional[Path] = None) -> Dict[str, Any]:
    data = _load_yaml(path or JAZZ_STATE_PATH)
    return data.get("jazz", data) if data else {}


def save_jazz_state(params_dict: Dict[str, Any], path: Optional[Path] = None) -> Path:
    target = path or JAZZ_STATE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        yaml.safe_dump({"jazz": params_dict}, fh, allow_unicode=True, sort_keys=False)
    return target


def append_advice(record: Dict[str, Any], path: Optional[Path] = None) -> Path:
    target = path or ADVICE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return target


def save_book_plan(book: BookPlan, path: Optional[Path] = None) -> Path:
    target = path or BOOK_PLAN_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(book.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def load_book_plan(path: Optional[Path] = None) -> Optional[BookPlan]:
    target = path or BOOK_PLAN_PATH
    if not target.exists():
        return None
    try:
        return BookPlan.from_dict(json.loads(target.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def export_book_outline(book: BookPlan, path: Optional[Path] = None) -> Path:
    """Write a human-readable Markdown outline of the whole book plan."""
    target = path or BOOK_OUTLINE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = [f"# {book.title or '未命名'}", ""]
    if book.logline:
        lines += [f"**核心创意**：{book.logline}", ""]
    if book.question:
        lines += [f"**核心命题**：{book.question}", ""]
    if book.main_conflict:
        lines += [f"**主要冲突**：{book.main_conflict}", ""]
    lines += [f"**结构模板**：{book.structure_template}"]
    if book.cast:
        lines += [f"**人物**：{'、'.join(book.cast)}"]
    if book.key_turns:
        lines += ["", "## 关键转折"]
        lines += [f"- {t}" for t in book.key_turns]
    if book.ending:
        lines += ["", f"**结局**：{book.ending}"]
    lines += [""]
    for vol in book.volumes:
        lines += [f"## 第 {vol.number} 卷 · {vol.title}", ""]
        for label, value in (("目标", vol.goal), ("开端状态", vol.opening_state),
                             ("高潮", vol.climax), ("阶段结果", vol.outcome),
                             ("承接下一卷", vol.sets_up_next)):
            if value:
                lines.append(f"- **{label}**：{value}")
        lines.append("")
        for ch in vol.chapters:
            mark = "🔒" if ch.locked else ""
            lines.append(f"### 第 {ch.number} 章 · {ch.title} {mark}")
            for label, value in (("功能", ch.function), ("POV", ch.pov),
                                 ("起因", ch.premise), ("关键行动", ch.key_action),
                                 ("冲突", ch.conflict), ("结果", ch.outcome),
                                 ("代价", ch.stakes), ("信息变化", ch.info_change),
                                 ("人物变化", ch.character_change),
                                 ("线索", "、".join(ch.threads)),
                                 ("意象", "、".join(ch.motifs)),
                                 ("驱向下一章", ch.hook_to)):
                if value:
                    lines.append(f"- **{label}**：{value}")
            lines.append("")
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def load_advice(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    target = path or ADVICE_PATH
    if not target.exists():
        return []
    out: List[Dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
