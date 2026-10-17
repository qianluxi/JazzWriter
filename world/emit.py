"""Export a WorldDoc as a plain Markdown worldview file."""

from __future__ import annotations

from pathlib import Path
from typing import List

from world.checker import WorldChecker
from world.models import KIND_LABELS, WorldDoc

_SECTION_ORDER = (
    "consequence", "knowledge", "institution", "history",
    "geography", "conflict", "motif",
)


def build_markdown(doc: WorldDoc) -> str:
    lines: List[str] = []
    lines.append(f"# {doc.title or '未命名世界'}")
    lines.append("")
    if doc.seed:
        lines.append(f"> 灵感种子：{doc.seed}")
        lines.append("")
    if doc.premise:
        lines.append(doc.premise)
        lines.append("")
    if doc.chosen_idea:
        idea = doc.chosen_idea
        lines.append("## 世界原型")
        lines.append("")
        lines.append(f"- **取向**：{idea.label}（{idea.lens}）")
        lines.append(f"- **一句话**：{idea.logline}")
        lines.append("")

    lines.append("## 核心规则")
    lines.append("")
    for entity in doc.of_kind("rule"):
        lines.append(f"- {entity.label()}：{entity.statement}")
        if entity.locked:
            lines.append("  - 🔒 已锁定")
    lines.append("")

    for kind in _SECTION_ORDER:
        group = doc.of_kind(kind)
        if not group:
            continue
        lines.append(f"## {KIND_LABELS.get(kind, kind)}")
        lines.append("")
        for entity in group:
            lines.append(f"- {entity.label()}：{entity.statement}")
        lines.append("")

    if doc.open_questions:
        lines.append("## 未决问题")
        lines.append("")
        for q in doc.open_questions:
            lines.append(f"- [ ] {q}")
        lines.append("")

    if doc.contradictions:
        lines.append("## 有意保留的矛盾")
        lines.append("")
        for c in doc.contradictions:
            lines.append(f"- {c}")
        lines.append("")

    issues = WorldChecker().check(doc)
    if issues:
        lines.append("## 一致性提示")
        lines.append("")
        for issue in issues:
            tag = "⚠" if issue["level"] == "warn" else "·"
            lines.append(f"- {tag} {issue['message']}")
        lines.append("")

    if doc.provenance:
        lines.append("## 来源与变形")
        lines.append("")
        for note in doc.provenance:
            lines.append(f"- {note}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"*由 World Studio 生成 · 生成方式：{doc.generation} · {doc.created_at}*")
    lines.append("")
    return "\n".join(lines)


def write_markdown(doc: WorldDoc, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_markdown(doc), encoding="utf-8")
    return path
