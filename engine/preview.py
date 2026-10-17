"""Manuscript preview — a self-contained reader page for GitHub Pages.

Turn rendered chapters into one standalone HTML file (no assets, no JS
framework) that can be published to ``docs/preview/`` and served at
``https://<user>.github.io/<repo>/preview/``.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine.textutil import word_count

_STYLE = """
:root{--ink:#1c1b19;--sub:#777;--paper:#faf8f3;--rule:#e5e0d5}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
 font-family:"Songti SC","Source Han Serif SC","Noto Serif SC",Georgia,serif;
 line-height:1.9}
header{padding:56px 20px 24px;text-align:center;border-bottom:1px solid var(--rule)}
header h1{margin:0 0 8px;font-size:30px;letter-spacing:2px}
header .q{color:var(--sub);font-size:14px}
nav{max-width:760px;margin:0 auto;padding:16px;text-align:center;border-bottom:1px solid var(--rule)}
nav a{color:#8a6d3b;text-decoration:none;margin:0 8px;font-size:13px}
nav a:hover{text-decoration:underline}
main{max-width:760px;margin:0 auto;padding:32px 22px 80px}
section{margin:0 0 56px;padding-bottom:8px}
section h2{font-size:19px;font-weight:600;margin:40px 0 18px;color:#5c4b2e}
section p{margin:0 0 1.05em;text-indent:2em;font-size:17px}
footer{max-width:760px;margin:0 auto;padding:20px 22px 60px;color:var(--sub);
 font-size:12px;text-align:center;border-top:1px solid var(--rule)}
.updated{color:var(--sub);font-size:12px}
.wc{color:#bbb;font-weight:400;font-size:12px;margin-left:10px}
"""


def build_manuscript_html(title: str, chapters: List[Dict], *, subtitle: str = "",
                          question: str = "", updated: str = "") -> str:
    """chapters: list of {number, title, pov, text}."""
    chapters = sorted(chapters, key=lambda c: c.get("number", 0))
    nav = "".join(
        f'<a href="#ch{c["number"]}">第{c["number"]}章</a>' for c in chapters)
    sections = []
    total = 0
    for c in chapters:
        text = c.get("text") or ""
        total += word_count(text)
        para = "".join(f"<p>{html.escape(p.strip())}</p>"
                       for p in text.splitlines() if p.strip())
        heading = f'第 {c["number"]} 章　{html.escape(c.get("title", ""))}' if c.get("title") \
            else f'第 {c["number"]} 章'
        heading += f'<span class="wc">{word_count(text)} 字</span>'
        sections.append(f'<section id="ch{c["number"]}"><h2>{heading}</h2>{para}</section>')
    sub = html.escape(subtitle or "")
    q = html.escape(question or "")
    up = html.escape(updated or "")
    stats = f"共 {len(chapters)} 章 · 全书 {total} 字"
    return f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title or '正文预览')}</title><style>{_STYLE}</style></head><body>
<header><h1>{html.escape(title or '正文预览')}</h1>
<p class="q">{q}</p><p class="q">{sub}</p></header>
<nav>{nav}</nav>
<main>{''.join(sections) or '<p style="text-indent:0;color:#777">（还没有正文，先在 JazzWriter 里“按结构渲染正文”。）</p>'}</main>
<footer>JazzWriter · 在线正文预览 · {stats} · 更新于 {up}</footer>
</body></html>"""


def write_preview(out_dir: Path, filename: str, content: str) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / filename
    target.write_text(content, encoding="utf-8")
    return target


def rebuild_index(out_dir: Path, *, site_title: str = "JazzWriter 正文预览") -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    items = sorted(p for p in out_dir.glob("*.html") if p.name != "index.html")
    links = "".join(
        f'<li><a href="{html.escape(p.name)}">{html.escape(p.stem)}</a></li>' for p in items)
    page = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(site_title)}</title><style>{_STYLE}
ul{{list-style:none;padding:0}} li{{margin:10px 0;font-size:16px}}
</style></head><body>
<header><h1>{html.escape(site_title)}</h1><p class="q">选择一部作品阅读</p></header>
<main><ul>{links or '<li style="color:#777">（暂无预览）</li>'}</ul></main>
<footer>JazzWriter</footer></body></html>"""
    target = out_dir / "index.html"
    target.write_text(page, encoding="utf-8")
    return target


def slugify(text: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", (text or "").strip())
    return (s.strip("-")[:40]) or "default"


def git_publish(repo_root, message: str, *, add_path: str = "docs/preview") -> Dict[str, Any]:
    """git add/commit/push one preview path. Never raises; returns status."""
    import subprocess

    def run(args):
        return subprocess.run(["git", "-C", str(repo_root)] + args,
                              capture_output=True, text=True, timeout=60)

    try:
        if run(["rev-parse", "--is-inside-work-tree"]).returncode != 0:
            return {"pushed": False, "message": "not a git repo"}
        run(["add", add_path])
        commit = run(["commit", "-m", message])
        combined = (commit.stdout or "") + (commit.stderr or "")
        if commit.returncode != 0 and "nothing to commit" not in combined:
            return {"pushed": False, "message": combined.strip()[:200]}
        last = ""
        for _ in range(3):  # transient network resets are common; retry a few times
            push = run(["push", "origin", "HEAD"])
            if push.returncode == 0:
                return {"pushed": True, "message": "pushed"}
            last = ((push.stderr or push.stdout) or "").strip()[:200]
        return {"pushed": False, "message": last}
    except Exception as exc:  # noqa: BLE001
        return {"pushed": False, "message": str(exc)}
