"""World Studio — standalone worldview forge (independent entry point).

Usage:
  python world_studio.py spark "每个人死后都会留下一段从未说出口的记忆" --grow
  python world_studio.py spark "..." --pick 制度世界
  python world_studio.py graft notes/world.txt --op 反转前提 --seed "一个没有夜晚的城市"
  python world_studio.py grow <slug>
  python world_studio.py check <slug>
  python world_studio.py list
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from world.graft import OPS
from world.idea_forge import DIMENSION_LABELS
from world.studio import WorldStudio

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _print_ideas(studio: WorldStudio) -> None:
    for i, idea in enumerate(studio.doc.ideas, start=1):
        dup = f" ⚠与{idea.near_duplicate}机制重复" if idea.near_duplicate else ""
        print(f"[{i}] {idea.label}｜{idea.lens}｜差异度 {idea.distinctness}{dup}")
        print(f"    一句话：{idea.logline}")
        print(f"    核心规则：{idea.core_rule}")
        for key, label in DIMENSION_LABELS.items():
            value = idea.dimensions.get(key, "")
            if value:
                print(f"    {label}：{value}")
        print()


def _print_status(studio: WorldStudio) -> None:
    st = studio.status()
    print(f"《{st['title']}》 slug={st['slug']}  ({st['generation']})")
    print(f"  原型 {st['ideas']} 个，选中：{st['chosen']}")
    print(f"  设定条目 {st['entities']} 条，未决问题 {st['open_questions']} 个，矛盾标注 {st['contradictions']} 条")


def cmd_spark(args) -> int:
    studio = WorldStudio.create(
        args.seed, title=args.title or "", root=_root(args), provider=args.provider
    )
    ideas = studio.raise_ideas(count=args.count)
    print(f"种子：{args.seed}\n")
    _print_ideas(studio)
    warnings = studio.duplicate_warnings()
    if warnings:
        print("⚠ 机制重复提示（标签不同但结构相似）：")
        for warning in warnings:
            print(f"  - {warning}")
        print()
    if args.pick:
        idea = studio.choose(args.pick)
        print(f"已选择：{idea.label}\n")
        studio.grow()
        _print_status(studio)
        path = studio.export()
        print(f"\n已生成 Markdown：{path}")
    else:
        print(f"（保存于 {studio.data_dir}，用 --pick \"<名称或序号>\" 继续生长）")
        studio.save()
    return 0


def cmd_graft(args) -> int:
    source = Path(args.source)
    if not source.exists():
        print(f"找不到源材料：{source}", file=sys.stderr)
        return 2
    if args.op == "世界交叉" and not args.second:
        print("「世界交叉」需要第二份材料：请用 --second <文件> 指定。", file=sys.stderr)
        return 2
    second_text = None
    if args.second:
        second = Path(args.second)
        if not second.exists():
            print(f"找不到交叉材料：{second}", file=sys.stderr)
            return 2
        second_text = second.read_text(encoding="utf-8")
    studio = WorldStudio.graft_new(
        args.seed or source.stem,
        source.read_text(encoding="utf-8"),
        args.op,
        source_name=args.name or source.name,
        second_text=second_text,
        root=_root(args),
        provider=args.provider,
    )
    _print_status(studio)
    diff = studio.doc.graft_diff
    if diff:
        print("\n变形记录（源世界未被修改，本次为派生新世界）：")
        labels = {"inherit": "继承", "remove": "删除", "modify": "修改",
                  "add": "新增", "downstream": "下游影响"}
        for key in ("inherit", "remove", "modify", "add", "downstream"):
            if diff.get(key):
                print(f"  - {labels[key]}：{'；'.join(diff[key])}")
    path = studio.export()
    print(f"\n已生成 Markdown：{path}")
    return 0


def cmd_pick(args) -> int:
    studio = _load(args)
    idea = studio.choose(args.idea)
    studio.save()
    print(f"已选择原型：{idea.label}（{idea.id}）")
    print(f"下一步：python world_studio.py --out <目录> grow {studio.slug}")
    return 0


def cmd_grow(args) -> int:
    studio = _load(args)
    if args.pick:
        studio.choose(args.pick)
    if studio.doc.chosen_idea is None:
        print("尚未选择世界原型。先用 `pick <slug> <原型>` 或 `grow <slug> --pick <原型>` 指定。",
              file=sys.stderr)
        return 2
    studio.grow()
    path = studio.export()
    _print_status(studio)
    print(f"\n已生成 Markdown：{path}")
    return 0


def cmd_check(args) -> int:
    studio = _load(args)
    issues = studio.check()
    warns = [i for i in issues if i["level"] == "warn"]
    notes = [i for i in issues if i["level"] != "warn"]
    for issue in warns:
        ids = ",".join(issue.get("ids", []))
        basis = f"（依据：{issue.get('basis')}；把握：{issue.get('confidence')}）"
        print(f"⚠ [{ids}] {issue['message']}{basis}")
    for issue in notes:
        ids = ",".join(issue.get("ids", []))
        print(f"· [{ids}] {issue['message']}")
    if not warns:
        print("未发现启发式冲突——注意这不等同于“与核心规则一致”（离线不做语义判断）。")
    return 0


def cmd_impact(args) -> int:
    studio = _load(args)
    report = studio.impact(args.entity)
    if not report["transitive"]:
        print(f"「{report['name']}」目前没有下游依赖条目。")
        return 0
    print(f"若修改「{report['name']}」，将牵连：")
    for name in report["transitive"]:
        print(f"  - {name}")
    if report["candidates"]:
        print("其中候选（需复核）：" + "、".join(report["candidates"]))
    return 0


def cmd_edit(args) -> int:
    studio = _load(args)
    try:
        result = studio.edit(args.entity, name=args.name, statement=args.statement,
                             basis=args.basis, state=args.state, confirm=args.yes)
    except (ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    studio.export()
    print(f"已修改 {result['entity']}：{('、'.join(result['changed'])) or '（无变化）'}")
    if result.get("reverify"):
        print("已修改核心规则 → 以下候选条目需要复核：")
        for name in result["reverify"]:
            print(f"  - {name}")
    if result.get("affected"):
        print("全部受影响条目：" + "、".join(result["affected"]))
    return 0


def cmd_state(args) -> int:
    studio = _load(args)
    entity = studio.set_state(args.entity, args.state)
    studio.save()
    print(f"{entity.id} → {entity.state}（已保存）")
    return 0


def cmd_show(args) -> int:
    studio = _load(args)
    _print_status(studio)
    print(f"\n预览：{studio.md_path}")
    return 0


def cmd_list(args) -> int:
    root = _root(args)
    if not root.exists():
        print("（暂无世界观项目）")
        return 0
    for child in sorted(p for p in root.iterdir() if (p / "world.json").exists()):
        try:
            studio = WorldStudio.load(child.name, root=root)
        except Exception:
            continue
        print(f"{child.name:24} {studio.doc.title}")
    return 0


def _root(args) -> Optional[Path]:
    return Path(args.out) if getattr(args, "out", None) else None


def _load(args) -> WorldStudio:
    return WorldStudio.load(args.slug, root=_root(args), provider=args.provider)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="world_studio", description="World Studio · 世界观工坊（独立入口）"
    )
    parser.add_argument("--provider", default="mock", help="mock | opencode | openai（默认 mock 离线）")
    parser.add_argument("--out", default=None, help="世界观数据目录（默认 worlds/）")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("spark", help="从只言片语发散出多个世界原型")
    p.add_argument("seed")
    p.add_argument("--count", type=int, default=4)
    p.add_argument("--pick", default=None, help="选择某个原型（名称或序号）")
    p.add_argument("--title", default=None)
    p.set_defaults(func=cmd_spark)

    p = sub.add_parser("graft", help="导入已有设定并变形改造")
    p.add_argument("source")
    p.add_argument("--op", default="深度变形", choices=list(OPS.keys()))
    p.add_argument("--seed", default=None)
    p.add_argument("--second", default=None, help="世界交叉用的第二份材料")
    p.add_argument("--name", default=None)
    p.add_argument("--title", default=None)
    p.set_defaults(func=cmd_graft)

    p = sub.add_parser("grow", help="生长并导出某个世界观")
    p.add_argument("slug")
    p.add_argument("--pick", default=None, help="选择要生长的原型（名称或序号）")
    p.set_defaults(func=cmd_grow)

    p = sub.add_parser("pick", help="选择世界原型（保存后可用 grow 继续）")
    p.add_argument("slug")
    p.add_argument("idea")
    p.set_defaults(func=cmd_pick)

    p = sub.add_parser("check", help="一致性提示（只报告，不修正）")
    p.add_argument("slug")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("impact", help="列出修改某条目会牵连的下游设定")
    p.add_argument("slug")
    p.add_argument("entity")
    p.set_defaults(func=cmd_impact)

    p = sub.add_parser("state", help="设置条目状态（confirmed/candidate/open/contradiction）")
    p.add_argument("slug")
    p.add_argument("entity")
    p.add_argument("state")
    p.set_defaults(func=cmd_state)

    p = sub.add_parser("edit", help="编辑条目内容（保留 id/来源/依赖；锁定或已确认需 --yes）")
    p.add_argument("slug")
    p.add_argument("entity")
    p.add_argument("--name", default=None)
    p.add_argument("--statement", default=None)
    p.add_argument("--basis", default=None)
    p.add_argument("--state", default=None)
    p.add_argument("--yes", action="store_true", help="确认修改已锁定/已确认条目")
    p.set_defaults(func=cmd_edit)

    p = sub.add_parser("show", help="查看世界观状态")
    p.add_argument("slug")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("list", help="列出本地世界观")
    p.set_defaults(func=cmd_list)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
