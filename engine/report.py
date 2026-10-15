"""Report — export the storyboard as Markdown and a self-contained HTML page.

Views: motif timeline, character-arc map, thread (foreshadowing) panel, and the
deviation findings. No external assets — the HTML opens in any browser.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.book_plan import BookPlan
from core.motif import MotifLibrary
from core.theme import Theme
from engine.memory import DeviationReport, analyze_book

REPORT_MD = "story_report.md"
REPORT_HTML = "story_report.html"


def _chapter_numbers(book: BookPlan) -> List[int]:
    return book.chapter_numbers()


def _motif_timeline(book: BookPlan, theme: Theme, motifs: Optional[MotifLibrary]) -> Tuple[List[str], Dict[str, List[int]]]:
    names = motifs.names() if motifs else list(theme.motifs)
    rows: Dict[str, List[int]] = {}
    for name in names:
        rows[name] = [c.number for c in book.chapters() if name in c.motifs]
    return names, rows


def _arc_map(book: BookPlan) -> Dict[str, Dict[str, List[int]]]:
    rows: Dict[str, Dict[str, List[int]]] = {}
    for name in book.cast:
        pov = [c.number for c in book.chapters() if c.pov == name]
        change = [c.number for c in book.chapters() if name in (c.character_change or "")]
        rows[name] = {"pov": pov, "change": change}
    return rows


def _thread_panel(book: BookPlan) -> List[Dict]:
    panel = []
    for thread in book.all_threads():
        chs = [c.number for c in book.chapters() if thread in c.threads]
        panel.append({
            "thread": thread,
            "intro": chs[0] if chs else None,
            "last": chs[-1] if chs else None,
            "count": len(chs),
            "status": "closed" if len(chs) >= 2 else "open",
        })
    return panel


def build_markdown(book: BookPlan, theme: Theme, motifs: Optional[MotifLibrary],
                   deviation: Optional[DeviationReport]) -> str:
    nums = _chapter_numbers(book)
    names, motif_rows = _motif_timeline(book, theme, motifs)
    arcs = _arc_map(book)
    threads = _thread_panel(book)

    lines: List[str] = [f"# {book.title or '未命名'} · 故事板", ""]
    if book.logline:
        lines.append(f"- 核心创意：{book.logline}")
    if book.question:
        lines.append(f"- 核心命题：{book.question}")
    lines.append(f"- 结构模板：{book.structure_template}")
    if book.cast:
        lines.append(f"- 人物：{'、'.join(book.cast)}")
    lines.append("")

    lines.append("## 动机演变时间线")
    lines.append("| 意象 | " + " | ".join(str(n) for n in nums) + " |")
    lines.append("|" + "---|" * (len(nums) + 1))
    for name in names:
        cells = ["●" if m in motif_rows[name] else "" for m in nums]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## 人物弧线图")
    lines.append("| 人物 | " + " | ".join(str(n) for n in nums) + " |")
    lines.append("|" + "---|" * (len(nums) + 1))
    for name, m in arcs.items():
        cells = []
        for n in nums:
            mark = ""
            if n in m["pov"]:
                mark += "●"
            if n in m["change"]:
                mark += "△"
            cells.append(mark)
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines.append("\n● = 视角　△ = 该人物出现变化")
    lines.append("")

    lines.append("## 线索与伏笔面板")
    lines.append("| 线索 | 引入 | 最后出现 | 次数 | 状态 |")
    lines.append("|---|---|---|---|---|")
    for t in threads:
        lines.append(f"| {t['thread']} | {t['intro']} | {t['last']} | {t['count']} | {t['status']} |")
    lines.append("")

    if deviation is not None:
        lines.append("## 偏离检测")
        for issue in deviation.issues:
            lines.append(f"- {issue}")
        lines.append("")

    lines.append("## 分卷与章节")
    for vol in book.volumes:
        lines.append(f"### 第 {vol.number} 卷 · {vol.title}")
        for ch in vol.chapters:
            lock = " 🔒" if ch.locked else ""
            lines.append(f"- 第 {ch.number} 章 [{ch.function}] {ch.pov}：{ch.summary}{lock}")
        lines.append("")
    return "\n".join(lines)


def _bar(score: float) -> str:
    return "█" * int(round(score * 20))


def build_html(book: BookPlan, theme: Theme, motifs: Optional[MotifLibrary],
               deviation: Optional[DeviationReport]) -> str:
    nums = _chapter_numbers(book)
    names, motif_rows = _motif_timeline(book, theme, motifs)
    arcs = _arc_map(book)
    threads = _thread_panel(book)

    def esc(x) -> str:
        return html.escape(str(x))

    def table(headers: List[str], rows: List[List[str]]) -> str:
        th = "".join(f"<th>{esc(h)}</th>" for h in headers)
        trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
        return f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"

    motif_rows_html = []
    for name in names:
        cells = ["●" if m in motif_rows[name] else "" for m in nums]
        motif_rows_html.append([esc(name)] + cells)

    arc_rows_html = []
    for name, m in arcs.items():
        cells = []
        for n in nums:
            mark = ("●" if n in m["pov"] else "") + ("△" if n in m["change"] else "")
            cells.append(mark or "&nbsp;")
        arc_rows_html.append([esc(name)] + cells)

    thread_rows_html = [[esc(t["thread"]), esc(t["intro"]), esc(t["last"]),
                         esc(t["count"]), esc(t["status"])] for t in threads]

    issues_html = "".join(f"<li>{esc(i)}</li>" for i in (deviation.issues if deviation else []))
    chapters_html = ""
    for vol in book.volumes:
        chapters_html += f"<h3>第 {vol.number} 卷 · {esc(vol.title)}</h3><ul>"
        for ch in vol.chapters:
            lock = " 🔒" if ch.locked else ""
            chapters_html += (f"<li><b>第 {ch.number} 章</b> [{esc(ch.function)}] "
                              f"{esc(ch.pov)}：{esc(ch.summary)}{lock}</li>")
        chapters_html += "</ul>"

    return f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(book.title or '未命名')} · 故事板</title>
<style>
 body{{font-family:"Microsoft YaHei UI","Segoe UI",sans-serif;margin:24px;color:#222;max-width:1100px}}
 h1{{margin:0 0 4px}} h2{{margin-top:28px;border-bottom:2px solid #eee;padding-bottom:4px}}
 table{{border-collapse:collapse;margin:8px 0;font-size:13px}}
 th,td{{border:1px solid #ddd;padding:4px 8px;text-align:center}}
 th{{background:#f5f7fa}} td:first-child,th:first-child{{text-align:left;white-space:nowrap}}
 .meta{{color:#555}} .issues li{{color:#a33}}
</style></head><body>
<h1>{esc(book.title or '未命名')} · 故事板</h1>
<p class="meta">模板 {esc(book.structure_template)} · 人物 {esc('、'.join(book.cast))}<br>
{esc(book.logline)}</p>
<h2>动机演变时间线</h2>
{table(['意象'] + [str(n) for n in nums], motif_rows_html)}
<h2>人物弧线图</h2>
{table(['人物'] + [str(n) for n in nums], arc_rows_html)}
<p class="meta">● = 视角　△ = 该人物出现变化</p>
<h2>线索与伏笔面板</h2>
{table(['线索', '引入', '最后出现', '次数', '状态'], thread_rows_html)}
<h2>偏离检测</h2><ul class="issues">{issues_html}</ul>
<h2>分卷与章节</h2>
{chapters_html}
</body></html>"""


def write_reports(book: BookPlan, theme: Theme, *, motifs: Optional[MotifLibrary] = None,
                  deviation: Optional[DeviationReport] = None,
                  outdir: Optional[Path] = None) -> Tuple[Path, Path]:
    base = Path(outdir) if outdir else Path(__file__).resolve().parent.parent / "output"
    base.mkdir(parents=True, exist_ok=True)
    if deviation is None:
        deviation = analyze_book(book, theme, motifs=motifs)
    md_path = base / REPORT_MD
    html_path = base / REPORT_HTML
    md_path.write_text(build_markdown(book, theme, motifs, deviation), encoding="utf-8")
    html_path.write_text(build_html(book, theme, motifs, deviation), encoding="utf-8")
    return md_path, html_path
