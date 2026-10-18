"""Export a WorldDoc as a plain Markdown worldview file."""

from __future__ import annotations

from pathlib import Path
from typing import List

from world.checker import WorldChecker
from world.graph import DependencyGraph
from world.idea_forge import DIMENSION_LABELS
from world.models import KIND_LABELS, WorldDoc

_SECTION_ORDER = (
    "consequence", "knowledge", "institution", "history",
    "geography", "conflict", "motif",
)
_PROP_LABELS = {
    "observability": "可观测性", "scarcity": "稀缺性", "enforcement": "执行方式",
    "cost": "代价", "mutability": "可变性",
}
_DIFF_LABELS = {
    "inherit": "继承", "remove": "删除", "modify": "修改",
    "add": "新增", "downstream": "下游影响",
}


def _entry_line(entity) -> str:
    lock = " 🔒已锁定" if entity.locked else ""
    basis = f"\n  - 依据：{entity.basis}" if entity.basis else ""
    return f"- {entity.label()}：{entity.statement}{lock}{basis}"


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
        if idea.dimensions:
            lines.append("- **五维（世界机制的五个维度）**：")
            for key, label in DIMENSION_LABELS.items():
                value = idea.dimensions.get(key, "")
                if value:
                    lines.append(f"  - {label}：{value}")
        lines.append("")

    lines.append("## 核心规则")
    lines.append("")
    for entity in doc.of_kind("rule"):
        lines.append(_entry_line(entity))
    lines.append("")

    if doc.rule_properties:
        lines.append("## 规则属性（推导起点）")
        lines.append("")
        for key, value in doc.rule_properties.items():
            basis = doc.rule_property_basis.get(key, "")
            suffix = f"（{basis}）" if basis else ""
            lines.append(f"- {_PROP_LABELS.get(key, key)}：{value}{suffix}")
        lines.append("")

    for kind in _SECTION_ORDER:
        group = doc.of_kind(kind)
        if not group:
            continue
        lines.append(f"## {KIND_LABELS.get(kind, kind)}")
        lines.append("")
        for entity in group:
            lines.append(_entry_line(entity))
        lines.append("")

    locked = [e for e in doc.entities if e.locked]
    if locked:
        lines.append("## 锁定条目")
        lines.append("")
        for entity in locked:
            lines.append(f"- {entity.id}｜{KIND_LABELS.get(entity.kind, entity.kind)}｜{entity.name}")
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

    graph = DependencyGraph(doc)
    rule_impacts = [r for r in (graph.impact_report(e.id) for e in doc.of_kind("rule"))
                    if r["transitive"]]
    if rule_impacts:
        lines.append("## 规则依赖与影响")
        lines.append("")
        for report in rule_impacts:
            lines.append(f"- 若修改「{report['name']}」，受影响：{'、'.join(report['transitive'])}")
        lines.append("")

    issues = [i for i in WorldChecker().check(doc) if not str(i.get("basis", "")).startswith("依赖图")]
    if issues:
        lines.append("## 一致性提示")
        lines.append("")
        for issue in issues:
            tag = "⚠" if issue["level"] == "warn" else "·"
            basis = f"（依据：{issue['basis']}；把握：{issue['confidence']}）" if issue.get("basis") else ""
            lines.append(f"- {tag} {issue['message']}{basis}")
        lines.append("")

    if doc.graft_diff:
        lines.append("## 嫁接变形记录")
        lines.append("")
        for key in ("inherit", "remove", "modify", "add", "downstream"):
            values = doc.graft_diff.get(key)
            if values:
                lines.append(f"- **{_DIFF_LABELS.get(key, key)}**：{'；'.join(values)}")
        lines.append("")

    if doc.provenance:
        lines.append("## 来源与变形")
        lines.append("")
        for note in doc.provenance:
            lines.append(f"- {note}")
        lines.append("")

    if doc.notes:
        lines.append("## 生成提示")
        lines.append("")
        for note in doc.notes:
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
