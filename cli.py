"""Command-line bandstand for the Novel Jazz Engine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.chapter_plan import FIELD_NAMES, apply_text, to_text
from core.improviser import MODES, STYLES
from engine.composer import Take
from engine.evaluator import Evaluation
from engine.outline_expander import TEMPLATE_LABELS
from engine.semantic_similarity import MODES as EVAL_MODES
from improvisation.improvisation_score import MODE_PRESETS
from session import Session
from store import (
    DATA_DIR,
    CHAPTERS_DIR,
    load_advice,
    load_runs,
    save_take,
)

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

# 即兴层：受控的偏移(Controlled Divergence)
jazz:
  mode: classic_jazz      # classic_jazz | bebop | free_jazz
  creativity: 0.5         # 创造程度
  randomness: 0.4         # 随机扰动
  motif_reuse: 0.8        # 主题重复
  character_freedom: 0.6  # 人物自主性
  surprise_level: 0.5     # 剧情转折
  style_distance: 0.3     # 语言变化
"""

_DEFAULT_CHARACTERS = """characters:
  - id: lin
    name: 林
    tier: core
    pov: true
    role: 检修工程师
    desire: 查清父亲那场事故的真相
    fear: 发现父亲也是共谋，而自己正重复他
    memory: 童年时父亲消失在泄压的白雾里
    worldview: 任何故障都有可查明的原因
    contradiction: 相信理性，却在做决定时凭直觉
    voice: 短句，专业术语夹在日常里
    blind_spots:
      - 认为一切都能靠技术还原，忽略当时的人际与政治压力
    capabilities:
      - 熟练的检修与测量
    constraints:
      - 缺乏调阅密档的权限
    current_goal: 找到父亲值夜那天被改动的记录
    rules:
      - 遇到未知：先测量，再记录，最后才允许害怕
      - 遇到危险：把情绪压进技术动作里
    arc_from: 相信技术中立
    arc_to: 承认技术是人的欲望的延长
  - id: su
    name: 苏
    tier: core
    pov: true
    role: 档案管理员
    desire: 让被抹去的名字重新出现
    fear: 自己保存的记忆也被改写
    memory: 亲手烧掉过一份名单
    worldview: 记忆即权力
    contradiction: 守护真相，却依赖谎言生存
    voice: 缓慢、反问、留白
    blind_spots:
      - 把记忆当作唯一真相，忽略记忆也会被权力塑造
    secrets:
      - 烧掉名单时私藏了其中一页
    current_goal: 让名字重见，同时保住自己
    arc_from: 守护档案
    arc_to: 成为档案本身
  - id: wei
    name: 魏
    tier: core
    pov: true
    role: 退休的车间主任
    desire: 保住当年那批工人的饭碗与体面
    fear: 旧事被公开后会连累活着的人
    contradiction: 想被理解，却一直阻止别人知道真相
    blind_spots:
      - 相信沉默就是保护
    secrets:
      - 签署了封存命令，并改动了值班表
    current_goal: 阻止林翻出那一晚
    arc_from: 以沉默保护他人
    arc_to: 承认沉默也是一种伤害
  - id: chen
    name: 陈
    tier: supporting
    pov: true
    role: 夜班清洁工
    desire: 保住这份工作，不被牵进麻烦
    fear: 被当作替罪者
    memory: 那晚他见过一个不该出现的人
    worldview: 少说少错
    contradiction: 想说真话，又怕没人信
    blind_spots:
      - 低估自己看见的东西的价值
    secrets:
      - 知道那晚有人进过控制室
    current_goal: 离事故远一点
  - id: zhao
    name: 赵
    tier: supporting
    pov: false
    role: 工段安全调查员
    desire: 尽快结案，维持系统运转
    fear: 案子翻出来会暴露监管失效
    worldview: 稳定的结论比真相更安全
    contradiction: 明知有疑点，仍推动盖章结案
    blind_spots:
      - 把系统稳定等同于正义
    secrets:
      - 上级授意压低事故等级
    current_goal: 把事故定性为设备老化
"""

_DEFAULT_RELATIONSHIPS = """relationships:
  - source_id: lin
    target_id: su
    type: 调查者与档案管理者
    mutual_interest: 林需要苏保存的档案重建事故；苏需要林的行动让名字重见
    conflict: 林要求公开原始记录，苏担心公开会暴露自己的过去
    asymmetry: 林有调查行动力，苏握有信息
    initial_state: 互相戒备的交易关系
    pressure_point: 林要求查看被烧毁名单所剩的那一页
    possible_transition: 从交易走向有限信任，或因是否公开而决裂
  - source_id: lin
    target_id: wei
    type: 晚辈与前辈
    mutual_interest: 林把魏当作父亲的旧同事；魏对林抱愧疚
    conflict: 魏要阻止翻案，林执意追查
    asymmetry: 魏知内情，林只有直觉
    pressure_point: 值班表被改动的事实浮现
    possible_transition: 魏从阻挡转为背负，或彻底沉默
  - source_id: chen
    target_id: zhao
    type: 目击者与调查者
    mutual_interest: 陈想脱身，赵想结案
    conflict: 赵需要陈的证词支持“设备老化”，陈怕被牵连
    asymmetry: 赵有权，陈无地位
    pressure_point: 陈被要求签一份他没读过的证词
    possible_transition: 陈说谎自保，或在压力下松口
"""

_DEFAULT_STORY_STATE = """chapter: 0
established_facts: []
character_knowledge: {}
open_threads: []
recent_events: []
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

    if evaluation.signals:
        labels = {
            "non_obviousness": "非显然性",
            "implicit_expression": "隐含表达",
            "narrative_increment": "叙事增量",
            "continuity": "连续性",
            "repetition_risk": "重复风险(越低越好)",
        }
        st = Table(title="文学回听 · Listen-back signals", header_style="bold cyan")
        st.add_column("维度")
        st.add_column("值", justify="right")
        for key, value in evaluation.signals.items():
            st.add_row(labels.get(key, key), f"{value:.0%}")
        console.print(st)
    for note in evaluation.listening:
        console.print(f"  [cyan]♪[/cyan] {note}")


_JAZZ_KEYS = ["creativity", "randomness", "motif_reuse",
              "character_freedom", "surprise_level", "style_distance"]
_STRUCT_KEYS = ["idea_divergence", "causal_variation", "character_agency",
                "motif_transformation", "revelation_delay", "branch_count",
                "continuity_strength"]


def _jazz_overrides(args) -> dict:
    out = {}
    for key in _JAZZ_KEYS + _STRUCT_KEYS:
        value = getattr(args, key, None)
        if value is not None:
            out[key] = value
    return out


def _show_cue(take: Take) -> None:
    cue = take.cue or {}
    if not cue:
        return
    jazz_seed = cue.get("jazz_seed", {})
    rhythm = cue.get("rhythm", {})
    solo = cue.get("solo", {})
    lines = [f"模式: {cue.get('mode')}　随机种子: {cue.get('seed_int')}"]
    if jazz_seed:
        lines.append("色彩: 情绪 {emotion}／视角 {perspective}／象征 {symbol}".format(
            emotion=jazz_seed.get("emotion", "-"),
            perspective=jazz_seed.get("perspective", "-"),
            symbol=jazz_seed.get("symbol", "-"),
        ))
    if rhythm:
        lines.append(f"节奏: {rhythm.get('name')}（{rhythm.get('pace')}）")
    if solo:
        lines.append(f"独奏: {solo.get('character')} · {solo.get('instrument')}")
    for m in cue.get("motifs", []):
        lines.append(f"动机变奏: {m.get('name')} → 第{m.get('stage')}次（{m.get('mode')}）")
    operators = (cue.get("operators", {}) or {}).get("operators", [])
    if operators:
        lines.append("叙事操作: " + "、".join(op.get("name", "") for op in operators))
    surprises = cue.get("surprises", [])
    if surprises:
        for s in surprises:
            lines.append(f"受控意外: [{s.get('category')}] {s.get('detail')}")
    else:
        lines.append("受控意外: 无")
    console.print(Panel("\n".join(lines), title="即兴决策 · Jazz Cue", border_style="yellow"))


def _show_advice(advice) -> None:
    d = advice.to_dict()
    console.print(Panel("\n".join(d["notes"]), title="下一轮调整建议 · Conductor", border_style="magenta"))


def _build_session(args) -> Session:
    data_dir = Path(args.data) if getattr(args, "data", None) else DATA_DIR
    return Session.load(
        data_dir=data_dir,
        provider=getattr(args, "provider", None),
        eval_mode=getattr(args, "eval_mode", "lexical"),
    )


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
    for col in ("名字", "ID", "层级", "POV", "角色", "欲望"):
        table.add_column(col)
    for c in session.characters.values():
        table.add_row(c.name, c.effective_id, c.tier, "✓" if c.pov else "—", c.role, c.desire)
    console.print(table)
    if session.relationships.relationships:
        console.print(f"[dim]人物关系 {len(session.relationships.relationships)} 条[/dim]")

    mt = Table(title="动机 · Motifs", header_style="bold")
    mt.add_column("动机")
    mt.add_column("次数", justify="right")
    mt.add_column("意义演变")
    for m in session.motifs.all():
        mt.add_row(m.name, str(m.count), " → ".join(m.meanings) or "-")
    console.print(mt)
    console.print(Panel(session.story_state.summary(),
                        title="故事状态 · Story State", border_style="yellow"))
    jz = session.jazz.to_dict()
    console.print("[dim]即兴参数: " + "，".join(f"{k}={v}" for k, v in jz.items() if k != "seed") + "[/dim]")
    console.print(f"[dim]LLM provider: {session.provider_name}　eval: {session.eval_mode}[/dim]")
    return 0


def cmd_play(args) -> int:
    session = _build_session(args)
    scene = _read_scene(args)
    if not scene:
        console.print("[red]缺少场景。用 --scene 或通过管道传入。[/red]")
        return 2
    take, evaluation = session.play(
        scene,
        pov=args.pov,
        style=args.style,
        chapter=args.chapter,
        total_chapters=args.total,
        previous_summary=args.previous or "",
        extra_instructions=args.extra or "",
        jazz_mode=args.mode,
        seed=args.seed,
        overrides=_jazz_overrides(args),
        previous_texts=session.recent_texts(5),
    )
    if args.show_prompt:
        console.print(Panel(take.prompt, title="Prompt (实际调用)", border_style="dim"))
    _show_cue(take)
    _show_take(take, evaluation)
    _show_advice(session.advise(take, evaluation))
    if args.suggest:
        _show_suggestions(session.plan(take, evaluation))
    _save(take, evaluation, session, index=1, no_save=args.no_save)
    return 0


def _show_suggestions(skeletons) -> None:
    if not skeletons:
        return
    lines = []
    for i, sk in enumerate(skeletons, 1):
        lines.append(f"{chr(64+i)}. {sk.goal}")
        lines.append(f"    POV {sk.pov} · {sk.surface_action}")
        lines.append(f"    即兴方向: {sk.improv_direction}")
        lines.append(f"    信息边界: {sk.info_boundary}")
        lines.append(f"    退出点: {sk.exit_point}")
    console.print(Panel("\n".join(lines), title="下一轮即兴建议 · Next Scenes", border_style="green"))


def cmd_takes(args) -> int:
    session = _build_session(args)
    scene = _read_scene(args)
    if not scene:
        console.print("[red]缺少场景。[/red]")
        return 2
    styles = args.styles or ["冷静观察", "象征增强", "心理深入"]
    results = session.variations(
        scene, pov=args.pov, styles=styles,
        chapter=args.chapter, total_chapters=args.total,
        jazz_mode=args.mode, seed=args.seed, overrides=_jazz_overrides(args),
        explore=getattr(args, "explore", False),
    )
    for i, (take, evaluation) in enumerate(results, start=1):
        _show_cue(take)
        _show_take(take, evaluation)
        _save(take, evaluation, session, index=i, no_save=args.no_save)
    return 0


def _read_scenes(args) -> List[str]:
    if getattr(args, "file", None):
        text = Path(args.file).read_text(encoding="utf-8")
    else:
        text = "\n".join(args.scenes or [])
    lines = [ln.strip() for ln in text.splitlines()]
    return [ln for ln in lines if ln and not ln.startswith("#")]


def cmd_book(args) -> int:
    session = _build_session(args)
    if getattr(args, "from_plan", False):
        try:
            results = session.render_book_from_plan(
                pov=args.pov, style=args.style, jazz_mode=args.mode,
                seed=args.seed, overrides=_jazz_overrides(args), save=not args.no_save)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            return 2
        console.print("[dim]由 output/book_plan.json 的结构渲染正文 …[/dim]")
    else:
        scenes = _read_scenes(args)
        if not scenes:
            console.print("[red]缺少场景。每章一行，或使用 --file 指定文件。[/red]")
            return 2
        if args.chapters and len(scenes) < args.chapters:
            console.print(f"[red]只提供了 {len(scenes)} 个场景，却请求 {args.chapters} 章。[/red]")
            console.print("[yellow]已停止：V2.0 不再循环复用同一场景。[/yellow]")
            console.print("[dim]请补充每章场景，或先 `python main.py outline --build` 生成结构，"
                          "再用 `python main.py book --from-plan` 渲染。[/dim]")
            return 2
        console.print(f"[dim]拟演奏 {len(scenes)} 章 …[/dim]")
        results = session.compose_book(
            scenes, pov=args.pov, style=args.style, styles=args.style_cycle or None,
            jazz_mode=args.mode, seed=args.seed, overrides=_jazz_overrides(args),
            save=not args.no_save, update_state=args.update_state)

    summary = Table(title="全书概览 · Book", header_style="bold")
    for col in ("章", "场景", "风格", "种子", "总分", "评级"):
        summary.add_column(col)
    for i, take, evaluation in results:
        title = f"第 {i} 章 · {take.mode} · {take.style} · POV {take.pov}"
        console.print(Panel(take.text, title=title, border_style="cyan", padding=(1, 2)))
        _show_cue(take)
        _show_evaluation(evaluation)
        seed_shown = take.cue.get("seed_int") if take.cue else ""
        summary.add_row(str(i), take.scene[:24], take.style, str(seed_shown),
                        f"{evaluation.overall:.0%}", evaluation.grade)
    console.print(summary)
    if not args.no_save:
        console.print("[green]章节已保存到 output/chapters/[/green]")
    console.print("[dim]提示：用 `python main.py history` 查看趋势，`python main.py advice` 看参数建议。[/dim]")
    return 0


def _read_premise(args) -> str:
    if getattr(args, "premise", None):
        return " ".join(args.premise).strip()
    if getattr(args, "file", None):
        return Path(args.file).read_text(encoding="utf-8").strip()
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    return ""


def _print_ideas(ideas) -> None:
    table = Table(title="故事方案 · 五维对照", header_style="bold")
    for col in ("#", "标签", "因果机制", "信息结构/真相", "人物关系", "结局", "主题解释", "差异度"):
        table.add_column(col)
    for i, idea in enumerate(ideas, 1):
        table.add_row(str(i), idea.label, idea.causal_mechanism, idea.truth_nature,
                      idea.character_relation, idea.ending_direction, idea.theme_reading,
                      f"{idea.distinctness:.0%}")
    console.print(table)
    if len(ideas) > 1:
        base = ideas[0]
        console.print("  [dim]与方案1不同的维度：[/dim]")
        for i, idea in enumerate(ideas[1:], 2):
            console.print(f"    {i}: {'、'.join(idea.differentiators) or '无'}")


def _print_chapter_map(book) -> None:
    table = Table(title=f"全书结构 · {book.title}（{book.structure_template}）", header_style="bold")
    for col in ("章", "功能", "POV", "冲突", "结果", "线索", "状态"):
        table.add_column(col)
    for ch in book.chapters():
        mark = "🔒锁定" if ch.locked else ch.status
        table.add_row(str(ch.number), ch.function, ch.pov,
                      ch.conflict[:20], ch.outcome[:20],
                      "、".join(ch.threads)[:16], mark)
    console.print(table)


def _print_structure(report) -> None:
    # 问题清单优先，分数其次
    if report.validation:
        console.print("[yellow]结构校验（硬问题）：[/yellow]")
        for issue in report.validation[:12]:
            console.print(f"  · {issue}")
    review = getattr(report, "review", []) or []
    if review:
        console.print("[cyan]叙事审阅（含依据）：[/cyan]")
        for f in review[:8]:
            ch = f"第{f['chapter']}章 " if f.get("chapter") else ""
            ev = f"　依据：{f['evidence']}" if f.get("evidence") else ""
            console.print(f"  · {ch}{f['issue']}{ev}")
    table = Table(title="结构评价 · Structure（分数仅供参考）", header_style="bold")
    table.add_column("维度")
    table.add_column("分数", justify="right")
    labels = {
        "idea_uniqueness": "创意独特性", "completeness": "故事完整性",
        "causal_continuity": "因果连续性", "character_change": "人物变化",
        "chapter_contribution": "章节贡献", "foreshadowing": "伏笔与回收",
        "relationship_evolution": "关系演变",
    }
    for k, v in report.dimensions.items():
        table.add_row(labels.get(k, k), f"{v:.0%}")
    table.add_row("综合", f"[bold]{report.overall:.0%}[/bold]")
    console.print(table)
    for note in report.notes:
        console.print(f"  [dim]{note}[/dim]")


def _print_synopsis(book) -> None:
    if not book.synopsis:
        return
    lines = [f"核心创意：{book.logline}", f"梗概：{book.synopsis}"]
    for label, value in (("开端", book.opening_state), ("触发事件", book.inciting_incident),
                         ("关键转折", book.central_turn), ("高潮", book.climax),
                         ("结局处理", book.resolution)):
        if value:
            lines.append(f"{label}：{value}")
    lines.append(f"（生成方式：{'模型' if book.generated_by == 'llm' else '离线模板'}）")
    console.print(Panel("\n".join(lines), title="全书梗概 · Synopsis", border_style="green"))


def cmd_outline(args) -> int:
    session = _build_session(args)

    if args.lock is not None:
        session.lock_chapter(args.lock)
        console.print(f"[green]已锁定第 {args.lock} 章[/green]")
        _print_chapter_map(session.book)
        return 0
    if args.unlock is not None:
        session.unlock_chapter(args.unlock)
        console.print(f"[green]已解锁第 {args.unlock} 章[/green]")
        return 0
    if args.lock_field or args.unlock_field:
        spec = args.lock_field or args.unlock_field
        try:
            number, field_name = int(spec[0]), spec[1]
        except (ValueError, IndexError):
            console.print("[red]用法：--lock-field N FIELD（如 --lock-field 3 conflict）[/red]")
            return 2
        if field_name not in FIELD_NAMES:
            console.print(f"[yellow]未知字段 {field_name}；可用：{'、'.join(FIELD_NAMES)}[/yellow]")
            return 2
        if args.lock_field:
            session.lock_field(number, field_name)
            console.print(f"[green]已锁定第 {number} 章的字段 {field_name}[/green]")
        else:
            session.unlock_field(number, field_name)
            console.print(f"[green]已解锁第 {number} 章的字段 {field_name}[/green]")
        ch = session.book.chapter(number)
        console.print(f"[dim]当前锁定字段：{ch.locked_fields or '无'}[/dim]")
        return 0
    if args.edit is not None:
        if not args.file:
            console.print("[red]--edit 需要配合 --file 指定卡片文本（字段：值）。[/red]")
            return 2
        try:
            book = session._require_book()
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            return 2
        chapter = book.chapter(args.edit)
        if chapter is None:
            console.print(f"[red]第 {args.edit} 章不存在[/red]")
            return 2
        apply_text(chapter, Path(args.file).read_text(encoding="utf-8"))
        session.save_book()
        console.print(f"[green]已更新第 {args.edit} 章卡片[/green]")
        console.print(Panel(to_text(chapter), title=f"第 {args.edit} 章", border_style="cyan"))
        return 0
    if args.edit_json is not None:
        if not args.file:
            console.print("[red]--edit-json 需要配合 --file 指定 JSON。[/red]")
            return 2
        try:
            book = session._require_book()
            data = json.loads(Path(args.file).read_text(encoding="utf-8"))
        except (ValueError, json.JSONDecodeError) as exc:
            console.print(f"[red]{exc}[/red]")
            return 2
        if book.chapter(args.edit_json) is None:
            console.print(f"[red]第 {args.edit_json} 章不存在[/red]")
            return 2
        session.update_chapter(args.edit_json, data)
        console.print(f"[green]已用 JSON 更新第 {args.edit_json} 章[/green]")
        return 0
    if args.fuse:
        premise = _read_premise(args)
        if not premise:
            console.print("[red]--fuse 需要故事前提（参数 / --file / 管道）。[/red]")
            return 2
        ideas = session.story_ideas(premise, count=args.branches, seed=args.seed)
        a, b = args.fuse[0] - 1, args.fuse[1] - 1
        try:
            fused = session.fuse_ideas(ideas, a, b, seed=args.seed)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            return 2
        rows = session.fuse_compare(ideas[a], ideas[b], fused)
        ftable = Table(title="融合对照 · What the fusion changed", header_style="bold")
        for col in ("维度", f"方案A({a + 1})", f"方案B({b + 1})", "融合采用", "取自"):
            ftable.add_column(col)
        for r in rows:
            ftable.add_row(r["dimension"], r["a"], r["b"], r["fused"], r["from"])
        console.print(ftable)
        console.print(Panel(
            f"标签：{fused.label}\n差异度：{fused.distinctness:.0%}\n理由：{fused.rationale}",
            title="融合方案 · Fused Idea", border_style="magenta"))
        console.print("[dim]把它作为方案 1 采纳即可：`outline ... --build --pick 1`（当前实现下融合方案需在 GUI 中使用）。[/dim]")
        return 0
    if args.reimprovise is not None:
        try:
            candidates = session.reimprovise_candidates(args.reimprovise, seed=args.seed)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            return 2
        if args.adopt is None:
            console.print(f"[bold]第 {args.reimprovise} 章的即兴候选（不会自动覆盖原卡片）：[/bold]")
            for i, c in enumerate(candidates, 1):
                tag = "模型" if c.source == "llm" else "离线模板"
                console.print(f"  [{i}] {c.label}　（{tag}）　改动字段：{', '.join(c.changed_fields) or '无'}")
            console.print("[dim]用 --adopt K 采纳某个候选；可加 --regen a,b 同时重生成后续章节。[/dim]")
            return 0
        k = args.adopt - 1
        if not (0 <= k < len(candidates)):
            console.print(f"[red]--adopt 超出范围（1..{len(candidates)}）[/red]")
            return 2
        try:
            book, affected = session.apply_candidate(candidates[k])
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            return 2
        console.print(f"[green]已采纳候选 {args.adopt}[/green]（第 {args.reimprovise} 章）；锁定字段保持不变。")
        if args.regen:
            if args.regen.lower() == "all":
                target = book.affected_downstream(args.reimprovise)
            else:
                try:
                    target = [int(x) for x in args.regen.split(",") if x.strip()]
                except ValueError:
                    console.print("[red]--regen 需要逗号分隔的章号或 all[/red]")
                    return 2
            target = [n for n in target if n != args.reimprovise]
            book, done = session.regenerate_chapters(sorted(set(target)), seed=args.seed)
            console.print(f"[dim]同时重生成：{done}[/dim]")
        console.print(f"[dim]可能受影响的后续章节：{affected}[/dim]")
        _print_chapter_map(book)
        return 0
    if args.export:
        try:
            path = session.export_outline()
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            return 2
        console.print(f"[green]已导出结构[/green] → {path}")
        return 0
    if args.validate:
        try:
            report = session.validate_book()
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            return 2
        _print_structure(report)
        return 0

    premise = _read_premise(args)
    if not premise:
        console.print("[red]缺少故事前提。用参数、--file 或管道提供。[/red]")
        return 2

    ideas = session.story_ideas(premise, count=args.branches, seed=args.seed)
    _print_ideas(ideas)

    if args.build or args.pick is not None:
        pick = (args.pick - 1) if args.pick else 0
        if pick < 0 or pick >= len(ideas):
            console.print(f"[red]--pick 超出范围（共 {len(ideas)} 个方案）[/red]")
            return 2
        console.print(f"[dim]采纳方案 {pick + 1}，展开为 {args.chapters} 章 …[/dim]")
        book = session.build_book(premise, ideas, pick=pick, chapters=args.chapters,
                                  template=args.template, seed=args.seed)
        _print_synopsis(book)
        _print_chapter_map(book)
        report = session.validate_book(book)
        _print_structure(report)
        console.print("[dim]下一步：`outline --lock N` 锁定认可章节；`outline --reimprovise N` "
                      "重新即兴；`outline --export` 导出；`book --from-plan` 渲染正文。[/dim]")
    return 0


def cmd_jam(args) -> int:
    session = _build_session(args)
    scene = _read_scene(args)
    if not scene:
        console.print("[red]缺少场景。[/red]")
        return 2
    result = session.jam(scene, pov=args.pov, chapter_number=args.chapter,
                         use_llm=not getattr(args, "no_llm", False))
    console.print(Panel(
        f"目标：{result.brief.goal}\n方向：{result.brief.direction}\n"
        f"约束：" + ("；".join(result.brief.constraints) or "（无）"),
        title="导演 · Director", border_style="blue"))
    console.print(Panel("\n".join(f"- {m}" for m in result.solo),
                        title="独奏 · Soloist", border_style="green"))
    console.print(Panel("\n".join(f"- {d}" for d in result.observer),
                        title="观察 · Observer", border_style="cyan"))
    body = result.proposal
    if result.notes:
        body += "\n\n备注：\n" + "\n".join(f"· {n}" for n in result.notes)
    if result.removed:
        body += "\n\n被排除（疑似提前揭露）：\n" + "\n".join(f"· {r}" for r in result.removed)
    console.print(Panel(body, title="编辑 · Editor 提案", border_style="magenta"))

    if args.render:
        take, evaluation = session.jam_to_take(
            result, pov=args.pov, style=args.style, jazz_mode=args.mode,
            seed=args.seed, overrides=_jazz_overrides(args), chapter=args.chapter or 1,
            total_chapters=args.total, save=not args.no_save)
        _show_take(take, evaluation)
    return 0


def cmd_report(args) -> int:
    session = _build_session(args)
    try:
        report = session.deviation_report()
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        return 2
    lines = [f"· {issue}" for issue in report.issues]
    console.print(Panel("\n".join(lines), title="偏离检测 · Deviation", border_style="yellow"))
    md, html = session.write_report()
    console.print(f"[green]故事板已导出[/green] → {md.name} / {html.name}")
    if getattr(args, "open", False):
        try:
            import os
            os.startfile(str(html))  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            console.print(f"[dim]无法自动打开：{exc}[/dim]")
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


def cmd_chars(args) -> int:
    session = _build_session(args)
    usage = session.character_usage()
    table = Table(title="人物库 · Characters", header_style="bold")
    for col in ("ID", "名字", "层级", "POV", "参与章", "欲望"):
        table.add_column(col)
    for row in usage:
        c = session.characters[row["name"]]
        table.add_row(row["id"], row["name"], row["tier"], "✓" if row["pov"] else "—",
                      "、".join(str(n) for n in row["chapters"]) or "—", c.desire)
    console.print(table)
    idle = session.idle_characters()
    if idle:
        console.print(f"[yellow]未参与任何章节的人物：{idle}（检查是否闲置）[/yellow]")
    if session.relationships.relationships:
        console.print(Panel(session.relationships_brief(),
                            title="人物关系网络 · Relationships", border_style="blue"))
        rt = Table(title="关系变化 · Relationship Changes", header_style="bold")
        for col in ("关系", "类型", "在哪些章发生变化"):
            rt.add_column(col)
        for row in session.relationship_changes_view():
            marks = "、".join(f"第{c['chapter']}章" for c in row["changes"]) or "从未变化"
            rt.add_row("↔".join(row["pair"]), row["type"], marks)
        console.print(rt)
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


def cmd_jazz(args) -> int:
    session = _build_session(args)
    current = session.jazz
    console.print(Panel(
        "\n".join(f"{k}: {v}" for k, v in current.to_dict().items() if k != "seed"),
        title="当前即兴参数 · Jazz Params (data/story.yaml)", border_style="yellow"))

    table = Table(title="模式预设 · Mode Presets", header_style="bold")
    table.add_column("模式")
    for key in _JAZZ_KEYS:
        table.add_column(key, justify="right")
    for mode, preset in MODE_PRESETS.items():
        table.add_row(mode, *[f"{preset[k]:.2f}" for k in _JAZZ_KEYS])
    console.print(table)
    return 0


def cmd_history(args) -> int:
    records = load_runs()
    if args.run_id:
        records = [r for r in records if r.get("run_id") == args.run_id]
    if args.chapter is not None:
        records = [r for r in records if r.get("chapter") == args.chapter]
    if not records:
        console.print("[yellow]暂无运行记录 (output/runs)。先执行一次 play。[/yellow]")
        return 0

    metric = args.metric

    def sort_key(rec):
        ev = rec.get("evaluation", {})
        if metric == "overall" or not metric:
            return ev.get("overall", 0.0)
        return ev.get("metrics", {}).get(metric, 0.0)

    records = sorted(records, key=sort_key)
    if args.limit:
        records = records[-args.limit:]

    table = Table(title="演奏历史 · History", header_style="bold")
    for col in ("章节", "时间", "种子", "模式", "风格", "总分", "评级", "文件"):
        table.add_column(col)
    for rec in records:
        ev = rec.get("evaluation", {})
        table.add_row(
            str(rec.get("chapter", "")),
            (rec.get("created_at", "") or "")[11:19],
            str(rec.get("seed", "")),
            rec.get("mode", ""),
            rec.get("style", ""),
            f"{ev.get('overall', 0):.0%}",
            ev.get("grade", ""),
            rec.get("run_id", ""),
        )
    console.print(table)

    # trend stats
    overalls = [r.get("evaluation", {}).get("overall", 0.0) for r in records]
    metrics_keys = ["theme", "character", "emotion", "motif", "novelty", "harmony"]
    per_metric = {
        k: sum(r.get("evaluation", {}).get("metrics", {}).get(k, 0.0) for r in records) / len(records)
        for k in metrics_keys
    }
    by_mode: dict = {}
    for r in records:
        m = r.get("mode", "?")
        by_mode.setdefault(m, []).append(r.get("evaluation", {}).get("overall", 0.0))
    stat_lines = [f"样本数: {len(records)}　平均总分: {sum(overalls)/len(overalls):.0%}"]
    stat_lines.append("维度均值: " + "，".join(f"{k} {v:.0%}" for k, v in per_metric.items()))
    stat_lines.append("分模式均分: " + "，".join(
        f"{m} {sum(v)/len(v):.0%}({len(v)})" for m, v in sorted(by_mode.items())))
    stat_lines.append("注：不同章节阶段任务不同，横向比较请参考相近章节/模式。")
    console.print(Panel("\n".join(stat_lines), title="趋势统计 · Trends", border_style="blue"))
    return 0


def cmd_advice(args) -> int:
    session = _build_session(args)
    history = load_advice()
    pending = [a for a in history if a.get("after") and not a.get("applied")]
    if not pending:
        console.print("[yellow]暂无待审核的参数建议。[/yellow]")
        return 0
    latest = pending[-1]

    if args.apply:
        path = session.apply_advice(
            _advice_from_dict(latest),
            run_id=latest.get("run_id", ""), note=args.note or "",
        )
        console.print(f"[green]已应用最新建议[/green] → {path.name}")
        return 0

    lines = [f"来源运行: {latest.get('run_id', '-')}（第 {latest.get('chapter', '?')} 章）"]
    for note in latest.get("notes", []):
        lines.append("· " + note)
    before = latest.get("before", {})
    after = latest.get("after", {})
    keys = ["creativity", "randomness", "motif_reuse", "character_freedom", "surprise_level", "style_distance"]
    lines.append("参数变更:")
    for k in keys:
        b, a = before.get(k), after.get(k)
        if b is not None and a is not None and abs(b - a) > 1e-9:
            lines.append(f"  {k}: {b:.2f} → {a:.2f}")
    console.print(Panel("\n".join(lines), title="待审核建议 · Pending Advice", border_style="magenta"))
    console.print("[dim]使用 `advice --apply` 显式应用；默认不自动修改默认乐谱。[/dim]")
    return 0


def _advice_from_dict(record):
    from feedback.conductor import Advice
    from improvisation.improvisation_score import JazzParams
    return Advice(
        metrics={}, deltas=record.get("deltas", {}),
        suggested=JazzParams.from_dict(record.get("after", {})),
        notes=record.get("notes", []),
    )


def cmd_plan(args) -> int:
    session = _build_session(args)
    skeletons = session.plan(count=args.count, seed=args.seed)
    _show_suggestions(skeletons)
    return 0


def cmd_init(args) -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    files = {
        "story.yaml": _DEFAULT_STORY,
        "characters.yaml": _DEFAULT_CHARACTERS,
        "relationships.yaml": _DEFAULT_RELATIONSHIPS,
        "motifs.yaml": _DEFAULT_MOTIFS,
        "story_state.yaml": _DEFAULT_STORY_STATE,
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
def _add_jazz_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--mode", default="classic_jazz", choices=list(MODE_PRESETS.keys()),
                   help="即兴模式: classic_jazz | bebop | free_jazz")
    p.add_argument("--seed", type=int, default=None, help="随机种子（可复现一次演奏）")
    p.add_argument("--creativity", type=float, default=None)
    p.add_argument("--randomness", type=float, default=None)
    p.add_argument("--motif-reuse", dest="motif_reuse", type=float, default=None)
    p.add_argument("--character-freedom", dest="character_freedom", type=float, default=None)
    p.add_argument("--surprise-level", dest="surprise_level", type=float, default=None)
    p.add_argument("--style-distance", dest="style_distance", type=float, default=None)


def _add_structure_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--idea-divergence", dest="idea_divergence", type=float, default=None)
    p.add_argument("--causal-variation", dest="causal_variation", type=float, default=None)
    p.add_argument("--character-agency", dest="character_agency", type=float, default=None)
    p.add_argument("--motif-transformation", dest="motif_transformation", type=float, default=None)
    p.add_argument("--revelation-delay", dest="revelation_delay", type=float, default=None)
    p.add_argument("--branch-count", dest="branch_count", type=int, default=None)
    p.add_argument("--continuity-strength", dest="continuity_strength", type=float, default=None)


def build_parser() -> argparse.ArgumentParser:
    from version import __version__

    parser = argparse.ArgumentParser(
        prog="jazzwriter",
        description="Novel Jazz Engine — 长篇小说结构即兴引擎。",
    )
    parser.add_argument("--version", action="version", version=f"JazzWriter {__version__}")
    parser.add_argument("--provider", default=None,
                        help="mock | opencode | openai (默认 NJE_PROVIDER 或 mock)")
    parser.add_argument("--data", default=None, help="数据目录 (默认 ./data)")
    parser.add_argument("--eval-mode", dest="eval_mode", default="lexical", choices=list(EVAL_MODES),
                        help="评价方式: lexical | embedding | hybrid")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="显示主题/人物/和声/动机/故事状态").set_defaults(func=cmd_status)
    sub.add_parser("styles", help="列出即兴模式与色彩").set_defaults(func=cmd_styles)
    sub.add_parser("jazz", help="显示即兴参数与模式预设").set_defaults(func=cmd_jazz)

    p = sub.add_parser("play", help="生成一章即兴演奏")
    p.add_argument("scene", nargs="*", help="场景描述（也可用管道输入）")
    p.add_argument("--pov", default=None, help="视角人物")
    p.add_argument("--style", default="现实主义", help=" | ".join(STYLES.keys()))
    p.add_argument("--chapter", type=int, default=1)
    p.add_argument("--total", type=int, default=1, help="全书章节数（用于情绪坐标）")
    p.add_argument("--previous", default=None, help="上文摘要")
    p.add_argument("--extra", default=None, help="额外指令")
    p.add_argument("--show-prompt", action="store_true", help="打印实际调用模型的完整 prompt")
    p.add_argument("--suggest", action="store_true", help="生成后给出下一章场景骨架")
    p.add_argument("--no-save", action="store_true")
    _add_jazz_options(p)
    p.set_defaults(func=cmd_play)

    t = sub.add_parser("takes", help="同一场景生成多个版本 (Take)")
    t.add_argument("scene", nargs="*")
    t.add_argument("--pov", default=None)
    t.add_argument("--styles", nargs="*", default=None, help="要生成的色彩列表")
    t.add_argument("--chapter", type=int, default=1)
    t.add_argument("--total", type=int, default=1)
    t.add_argument("--explore", action="store_true",
                   help="模式B：同一主题多次独立即兴（各 Take 使用不同 Cue/路径）")
    t.add_argument("--no-save", action="store_true")
    _add_jazz_options(t)
    t.set_defaults(func=cmd_takes)

    bk = sub.add_parser("book", help="顺序生成全书（每个场景一章，自动衔接）")
    bk.add_argument("scenes", nargs="*", help="每章场景（可多行）；也可用 --file")
    bk.add_argument("--file", default=None, help="从文本文件读取，每行一章（# 开头为注释）")
    bk.add_argument("--pov", default=None)
    bk.add_argument("--style", default="现实主义")
    bk.add_argument("--style-cycle", dest="style_cycle", nargs="*", default=None,
                    help="按章轮流使用的 Solo 色彩")
    bk.add_argument("--chapters", type=int, default=None, help="期望章数（不足将报错，不再循环复用）")
    bk.add_argument("--from-plan", dest="from_plan", action="store_true",
                    help="用 output/book_plan.json 的章节结构渲染正文")
    bk.add_argument("--update-state", dest="update_state", action="store_true",
                    help="把本次进度写回 data/story_state.yaml")
    bk.add_argument("--no-save", action="store_true")
    _add_jazz_options(bk)
    _add_structure_options(bk)
    bk.set_defaults(func=cmd_book)

    ol = sub.add_parser("outline", help="故事结构即兴：发散方案→采纳→展开→校验→导出")
    ol.add_argument("premise", nargs="*", help="故事前提（也可 --file 或管道）")
    ol.add_argument("--file", default=None)
    ol.add_argument("--branches", type=int, default=None, help="故事方案数量")
    ol.add_argument("--chapters", type=int, default=12)
    ol.add_argument("--template", default="linear_causality", choices=list(TEMPLATE_LABELS.keys()),
                    help="结构模板: " + " | ".join(TEMPLATE_LABELS))
    ol.add_argument("--pick", type=int, default=None, help="采纳第几个方案(1起)并展开全书结构")
    ol.add_argument("--build", action="store_true", help="采纳方案并展开结构（等价 --pick 1）")
    ol.add_argument("--fuse", nargs=2, type=int, metavar=("A", "B"), default=None,
                    help="融合两个故事方案（编号从 1 起）")
    ol.add_argument("--edit", type=int, default=None,
                    help="用 --file 的卡片文本(字段：值)更新指定章")
    ol.add_argument("--edit-json", dest="edit_json", type=int, default=None,
                    help="用 --file 的 JSON 更新指定章（支持嵌套人物/关系字段）")
    ol.add_argument("--reimprovise", type=int, default=None, help="为指定章生成即兴候选")
    ol.add_argument("--adopt", type=int, default=None, help="采纳第 K 个重新即兴候选")
    ol.add_argument("--regen", default=None,
                    help="配合 --adopt：逗号分隔要重生成的章号，或 all")
    ol.add_argument("--lock", type=int, default=None, help="锁定指定章")
    ol.add_argument("--unlock", type=int, default=None, help="解锁指定章")
    ol.add_argument("--lock-field", dest="lock_field", nargs=2, metavar=("N", "FIELD"),
                    default=None, help="锁定某章的单个字段（如 --lock-field 3 conflict）")
    ol.add_argument("--unlock-field", dest="unlock_field", nargs=2, metavar=("N", "FIELD"),
                    default=None, help="解锁某章的单个字段")
    ol.add_argument("--validate", action="store_true", help="校验已保存的 BookPlan")
    ol.add_argument("--export", action="store_true", help="导出结构为 Markdown")
    _add_jazz_options(ol)
    _add_structure_options(ol)
    ol.set_defaults(func=cmd_outline)

    h = sub.add_parser("history", help="查看演奏历史与趋势")
    h.add_argument("--chapter", type=int, default=None)
    h.add_argument("--limit", type=int, default=None, help="只显示最近 N 次")
    h.add_argument("--metric", default="overall", help="排序依据: overall|theme|character|novelty|...")
    h.add_argument("--run-id", dest="run_id", default=None)
    h.set_defaults(func=cmd_history)

    a = sub.add_parser("advice", help="查看/应用下一轮参数建议")
    a.add_argument("--apply", action="store_true", help="显式应用最新建议到 jazz_state.yaml")
    a.add_argument("--note", default=None)
    a.set_defaults(func=cmd_advice)

    pl = sub.add_parser("plan", help="提出下一章场景骨架")
    pl.add_argument("--count", type=int, default=3)
    pl.add_argument("--seed", type=int, default=None)
    pl.set_defaults(func=cmd_plan)

    jm = sub.add_parser("jam", help="Jam Session：导演→独奏→观察→编辑")
    jm.add_argument("scene", nargs="*", help="场景（也可管道输入）")
    jm.add_argument("--pov", default=None)
    jm.add_argument("--chapter", type=int, default=None, help="对应 BookPlan 的章号（可选）")
    jm.add_argument("--total", type=int, default=1)
    jm.add_argument("--style", default="现实主义")
    jm.add_argument("--render", action="store_true", help="用 Editor 提案渲染正文")
    jm.add_argument("--no-save", action="store_true")
    jm.add_argument("--no-llm", dest="no_llm", action="store_true", help="强制确定性（不使用模型）")
    _add_jazz_options(jm)
    jm.set_defaults(func=cmd_jam)

    rp = sub.add_parser("report", help="导出故事板（md/html）+ 偏离检测")
    rp.add_argument("--open", action="store_true", help="导出后用浏览器打开 HTML")
    rp.set_defaults(func=cmd_report)

    e = sub.add_parser("evaluate", help="评价一个已保存的章节文件")
    e.add_argument("file")
    e.add_argument("--pov", default=None)
    e.set_defaults(func=cmd_evaluate)

    sub.add_parser("motifs", help="查看动机追踪").set_defaults(func=cmd_motifs)
    sub.add_parser("chars", help="查看人物库、使用情况与关系网络").set_defaults(func=cmd_chars)

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
