"""Novel Jazz Engine — entry point.

Run with a subcommand for the full CLI::

    python main.py status
    python main.py play "冬夜，学校食堂，一台旧机器仍在运行" --pov 林
    python main.py takes "同上" --styles 冷静观察 象征增强 心理深入

Run with no arguments for an offline demo of the prompt/take/evaluation loop.
"""

from __future__ import annotations

import sys


def demo() -> int:
    """A tiny offline performance so the pipeline is visible without an API key."""
    from rich.console import Console
    from rich.panel import Panel

    from cli import _setup_console
    from session import Session

    _setup_console()

    console = Console()
    session = Session.load()
    scene = "冬夜。学校食堂。学生们发现一台早已报废的蒸汽机仍在运行。"
    improver = session.improviser("林")

    console.rule("[bold]Novel Jazz Engine · Demo[/bold]")
    console.print(Panel(session.theme.as_prompt(), title="主题旋律 Theme", border_style="green"))
    console.print(Panel(improver.create_prompt(scene)[:1200] + "\n…", title="即兴 Prompt (节选)", border_style="dim"))

    take, evaluation = session.play(scene, pov="林", chapter=1, total_chapters=12)
    console.print(Panel(take.text, title="Take", border_style="cyan"))
    console.print(evaluation.as_dict())
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return demo()
    from cli import main as cli_main

    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
