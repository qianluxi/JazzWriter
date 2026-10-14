"""Command-line bandstand for the Novel Jazz Engine."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.improviser import MODES, STYLES
from engine.composer import Take
from engine.evaluator import Evaluation
from session import Session
from store import DATA_DIR, CHAPTERS_DIR, save_take

console = Console()


def _setup_console() -> None:
    """Force UTF-8 so CJK text renders on legacy Windows consoles."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

_DEFAULT_STORY = """theme:
  title: "蒸汽时代的人类孤独"
  question: "技术在进步，人是否更接近幸福"
  statement: "我们造出了轰鸣的机器，却学会了更安静地彼此远离。"
  emotions: [孤独, 怀疑, 希望]
  symbols: [蒸汽, 雾, 老机械]
  motifs: [蒸汽, 阀门]

world:
  world: "蒸汽工业城市，齿轮与管道构成城市的血管。"
  rules:
    - 蒸汽能源重塑了社会，阶层以能否接触核心机械划分
    - 技术事故被系统性掩盖
  forbidden: [魔法, 超自然解释]
  soft_constraints:
    - 允许非线性回忆
  emotion_curve: [平静, 不安, 疑惑, 发现, 否认, 理解]
"""

_DEFAULT_CHARACTERS = """characters:
  - name: 林
    role: 检修工程师
    desire: 查清父亲那场事故的真相
    fear: 发现父亲也是共谋，而自己正重复他
    memory: 童年时父亲消失在泄压的白雾里
    worldview: 任何故障都有可查明的原因
    contradiction: 相信理性，却在做决定时凭直觉
    voice: 短句，专业术语夹在日常里
    rules:
      - 遇到未知：先测量，再记录，最后才允许害怕
      - 遇到危险：把情绪压进技术动作里
      - 遇到过去：回避，用工作转移
    arc_from: 相信技术中立
    arc_to: 承认技术是人的欲望的延长
  - name: 苏
    role: 档案管理员
    desire: 让被抹去的名字重新出现
    fear: 自己保存的记忆也被改写
    memory: 亲手烧掉过一份名单
    worldview: 记忆即权力
    contradiction: 守护真相，却依赖谎言生存
    voice: 缓慢、反问、留白
    rules:
      - 遇到权威：既不服从也不正面冲撞
      - 遇到弱者：多说一句
"""

_DEFAULT_MOTIFS = """motifs:
  - name: 蒸汽
    note: 从工业力量到生命隐喻
    history: []
  - name: 阀门
    note: 控制与失控之间
    history: []
"""


# -- helpers -------------------------------------------------------------------
def _read_scene(args) -> str:
    if args.scene:
        return args.scene if isinstance(args.scene, str) else " ".join(args.scene)
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    try:
        return input("场景 > ").strip()
    except EOFError:
        return ""


def _show_take(take: Take, evaluation: Optional[Evaluation]) -> None:
    title = (
        f"第 {take.chapter} 章 · {take.mode} · {take.style} · POV {take.pov}"
    )
    console.print(Panel(take.text, title=title, border_style="cyan", padding=(1, 2)))
    if take.harmony_violations:
        console.print(
            "[red]⚠ 违反硬约束: " + "、".join(take.harmony_violations) + "[/red]"
        )
    if evaluation:
        _show_evaluation(evaluation)


def _show_evaluation(evaluation: Evaluation) -> None:
    table = Table(title="回听评价 · Listen-back", show_header=True, header_style="bold magenta")
    table.add_column("维度")
    table.add_column("分数", justify="right")
    table.add_column("条")
    labels = {
        "theme": "主题一致性",
        "character": "人物一致性",
        "emotion": "情绪和声",
        "motif": "动机复用",
        "novelty": "新鲜度",
        "harmony": "和声合规",
    }
    for key, value in evaluation.metrics.items():
        bar = "█" * int(round(value * 10))
        table.add_row(labels.get(key, key), f"{value:.0%} {bar}", "")
    table.add_row("总分", f"[bold]{evaluation.overall:.0%}[/bold]", f"评级 {evaluation.grade}")
    console.print(table)
    for note in evaluation.notes:
        console.print(f"  [yellow]·[/yellow] {note}")


def _build_session(args) -> Session:
    data_dir = Path(args.data) if getattr(args, "data", None) else DATA_DIR
    return Session.load(data_dir=data_dir, provider=getattr(args, "provider", None))


def _save(take: Take, evaluation: Evaluation, session: Session, index: int, no_save: bool):
    if no_save:
        return
    md, js = save_take(take, evaluation, index=index)
    session.record_motifs(take)
    session.persist_motifs()
    console.print(f"[green]已保存[/green] {md.name} / {js.name}")


# -- commands ------------------------------------------------------------------
def cmd_status(args) -> int:
    session = _build_session(args)
    console.print(
        Panel(
            session.theme.as_prompt(),
            title="主题旋律 · Theme",
            border_style="green",
        )
    )
    console.print(
        Panel(session.harmony.as_prompt(), title="叙事和声 · Harmony", border_style="blue")
    )
    table = Table(title="乐手 · Characters", header_style="bold")
    table.add_column("名字")
    table.add_column("角色")
    table.add_column("欲望")
    table.add_column("恐惧")
    for c in session.characters.values():
        table.add_row(c.name, c.role, c.desire, c.fear)
    console.print(table)

    mt = Table(title="动机 · Motifs", header_style="bold")
    mt.add_column("动机")
    mt.add_column("次数", justify="right")
    mt.add_column("意义演变")
    for m in session.motifs.all():
        mt.add_row(m.name, str(m.count), " → ".join(m.meanings) or "-")
    console.print(mt)
    console.print(f"[dim]LLM provider: {session.provider_name}[/dim]")
    return 0


def cmd_play(args) -> int:
    session = _build_session(args)
    scene = _read_scene(args)
    if not scene:
        console.print("[red]缺少场景。用 --scene 或通过管道传入。[/red]")
        return 2
    if args.show_prompt:
        console.print(Panel(session.improviser(args.pov).create_prompt(scene),
                            title="Prompt", border_style="dim"))
    take, evaluation = session.play(
        scene,
        pov=args.pov,
        mode=args.mode,
        style=args.style,
        chapter=args.chapter,
        total_chapters=args.total,
        previous_summary=args.previous or "",
        extra_instructions=args.extra or "",
    )
    _show_take(take, evaluation)
    _save(take, evaluation, session, index=1, no_save=args.no_save)
    return 0


def cmd_takes(args) -> int:
    session = _build_session(args)
    scene = _read_scene(args)
    if not scene:
        console.print("[red]缺少场景。[/red]")
        return 2
    styles = args.styles or ["冷静观察", "象征增强", "心理深入"]
    results = session.variations(
        scene, pov=args.pov, mode=args.mode, styles=styles,
        chapter=args.chapter, total_chapters=args.total,
    )
    for i, (take, evaluation) in enumerate(results, start=1):
        _show_take(take, evaluation)
        _save(take, evaluation, session, index=i, no_save=args.no_save)
    return 0


def cmd_evaluate(args) -> int:
    session = _build_session(args)
    path = Path(args.file)
    if not path.exists():
        console.print(f"[red]找不到文件: {path}[/red]")
        return 2
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".md":
        parts = text.split("---")
        if len(parts) >= 3:
            text = "---".join(parts[2:]).strip()
    evaluation = session.evaluator(args.pov).evaluate(text)
    _show_evaluation(evaluation)
    return 0


def cmd_motifs(args) -> int:
    session = _build_session(args)
    table = Table(title="动机追踪 · Motif Trace", header_style="bold")
    table.add_column("动机")
    table.add_column("章节", justify="right")
    table.add_column("意义")
    table.add_column("引文")
    for m in session.motifs.all():
        if not m.history:
            table.add_row(m.name, "0", "-", "-")
        for entry in m.history:
            table.add_row(m.name, str(entry.get("chapter", "")), entry.get("meaning", ""),
                          (entry.get("quote", "") or "")[:28])
    console.print(table)
    return 0


def cmd_styles(args) -> int:
    console.print(Panel("\n".join(f"{k}: {v}" for k, v in MODES.items()),
                        title="即兴模式 · Modes", border_style="blue"))
    console.print(Panel("\n".join(f"{k}: {v}" for k, v in STYLES.items()),
                        title="Solo 色彩 · Styles", border_style="green"))
    return 0


def cmd_init(args) -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    files = {
        "story.yaml": _DEFAULT_STORY,
        "characters.yaml": _DEFAULT_CHARACTERS,
        "motifs.yaml": _DEFAULT_MOTIFS,
    }
    for name, content in files.items():
        target = DATA_DIR / name
        if target.exists() and not args.force:
            console.print(f"[yellow]跳过已存在[/yellow] {name}")
            continue
        target.write_text(content, encoding="utf-8")
        console.print(f"[green]写入[/green] {name}")
    (Path(CHAPTERS_DIR)).mkdir(parents=True, exist_ok=True)
    return 0


# -- parser --------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jazzwriter",
        description="Novel Jazz Engine — 像爵士乐手一样即兴写小说。",
    )
    parser.add_argument("--provider", default=None, help="mock | openai (默认 NJE_PROVIDER 或 mock)")
    parser.add_argument("--data", default=None, help="数据目录 (默认 ./data)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="显示主题/人物/和声/动机").set_defaults(func=cmd_status)
    sub.add_parser("styles", help="列出即兴模式与色彩").set_defaults(func=cmd_styles)

    p = sub.add_parser("play", help="生成一章即兴演奏")
    p.add_argument("scene", nargs="*", help="场景描述（也可用管道输入）")
    p.add_argument("--pov", default=None, help="视角人物")
    p.add_argument("--mode", default="classic", choices=list(MODES.keys()))
    p.add_argument("--style", default="现实主义", help=" | ".join(STYLES.keys()))
    p.add_argument("--chapter", type=int, default=1)
    p.add_argument("--total", type=int, default=1, help="全书章节数（用于情绪坐标）")
    p.add_argument("--previous", default=None, help="上文摘要")
    p.add_argument("--extra", default=None, help="额外指令")
    p.add_argument("--show-prompt", action="store_true")
    p.add_argument("--no-save", action="store_true")
    p.set_defaults(func=cmd_play)

    t = sub.add_parser("takes", help="同一场景生成多个版本 (Take)")
    t.add_argument("scene", nargs="*")
    t.add_argument("--pov", default=None)
    t.add_argument("--mode", default="classic", choices=list(MODES.keys()))
    t.add_argument("--styles", nargs="*", default=None, help="要生成的色彩列表")
    t.add_argument("--chapter", type=int, default=1)
    t.add_argument("--total", type=int, default=1)
    t.add_argument("--no-save", action="store_true")
    t.set_defaults(func=cmd_takes)

    e = sub.add_parser("evaluate", help="评价一个已保存的章节文件")
    e.add_argument("file")
    e.add_argument("--pov", default=None)
    e.set_defaults(func=cmd_evaluate)

    sub.add_parser("motifs", help="查看动机追踪").set_defaults(func=cmd_motifs)

    i = sub.add_parser("init", help="写入示例数据文件")
    i.add_argument("--force", action="store_true")
    i.set_defaults(func=cmd_init)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    _setup_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, KeyError) as exc:
        console.print(f"[red]{exc}[/red]")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
