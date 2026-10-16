"""Report — export the storyboard as Markdown and an **interactive** HTML page.

Views: motif timeline, character-arc map, thread (foreshadowing) panel, the
deviation findings, and a filterable chapter browser (POV filter, text search,
click a chapter to inspect its card). No external assets/JS libraries.
"""

from __future__ import annotations

import html
import json
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


def _motif_timeline(book: BookPlan, theme: Theme, motifs: Optional[MotifLibrary]
                    ) -> Tuple[List[str], Dict[str, List[int]]]:
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
        panel.append({"thread": thread, "intro": chs[0] if chs else None,
                      "last": chs[-1] if chs else None, "count": len(chs),
                      "status": "closed" if len(chs) >= 2 else "open"})
    return panel


def _chapter_dict(ch) -> Dict:
    return {
        "number": ch.number, "title": ch.title, "function": ch.function,
        "pov": ch.pov, "pov_id": ch.pov_character_id,
        "summary": ch.summary, "conflict": ch.conflict, "outcome": ch.outcome,
        "info_change": ch.info_change, "character_change": ch.character_change,
        "threads": ch.threads, "motifs": ch.motifs,
        "status": "locked" if ch.locked else ch.status,
        "decisions": [d.decision for d in ch.character_decisions],
        "knowledge": [k.change for k in ch.knowledge_changes],
        "relationships": [f"{'↔'.join(r.pair)}：{r.change}" for r in ch.relationship_changes],
    }


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
            mark = ("●" if n in m["pov"] else "") + ("△" if n in m["change"] else "")
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

    motif_rows_html = [[esc(name)] + ["●" if m in motif_rows[name] else "" for m in nums] for name in names]
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

    data = [_chapter_dict(c) for c in book.chapters()]
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    return f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(book.title or '未命名')} · 故事板</title>
<style>
 body{{font-family:"Microsoft YaHei UI","Segoe UI",sans-serif;margin:24px;color:#222;max-width:1180px}}
 h1{{margin:0 0 4px}} h2{{margin-top:28px;border-bottom:2px solid #eee;padding-bottom:4px}}
 table{{border-collapse:collapse;margin:8px 0;font-size:13px}}
 th,td{{border:1px solid #ddd;padding:4px 8px;text-align:center}}
 th{{background:#f5f7fa}} td:first-child,th:first-child{{text-align:left;white-space:nowrap}}
 .meta{{color:#555}} .issues li{{color:#a33}}
 .controls{{margin:8px 0}} .controls input,.controls select{{padding:4px 6px;margin-right:8px}}
 #rows tr{{cursor:pointer}} #rows tr:hover{{background:#eef6ff}}
 #rows td{{text-align:left}}
 #detail{{margin-top:10px;padding:12px;border:1px solid #cce;background:#f8fbff;border-radius:6px;min-height:60px}}
 .pill{{display:inline-block;background:#eef;border-radius:10px;padding:1px 8px;margin:2px;font-size:12px}}
 .locked{{color:#b60}}
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
<h2>章节浏览器（可按视角筛选 / 搜索 / 点击查看）</h2>
<div class="controls">
  <label>视角：<select id="pov"><option value="">全部</option></select></label>
  <input id="q" placeholder="搜索关键词…" size="24">
</div>
<table><thead><tr><th>章</th><th>功能</th><th>视角</th><th>摘要</th><th>状态</th></tr></thead>
<tbody id="rows"></tbody></table>
<div id="detail">点击上方任意一行查看该章卡片。</div>
<script>
const DATA = {data_json};
const povSel = document.getElementById('pov');
[...new Set(DATA.map(c => c.pov).filter(Boolean))].forEach(p => {{
  const o = document.createElement('option'); o.value = p; o.textContent = p; povSel.appendChild(o);
}});
const rows = document.getElementById('rows');
const detail = document.getElementById('detail');
function render() {{
  const pov = povSel.value, q = document.getElementById('q').value.trim();
  rows.innerHTML = '';
  DATA.filter(c => (!pov || c.pov === pov) &&
                   (!q || JSON.stringify(c).includes(q)))
      .forEach(c => {{
        const tr = document.createElement('tr');
        const lock = c.status === 'locked' ? ' <span class="locked">🔒</span>' : '';
        tr.innerHTML = `<td>${{c.number}}</td><td>${{c.function}}</td><td>${{c.pov}}</td>` +
                       `<td>${{c.summary}}</td><td>${{c.status}}${{lock}}</td>`;
        tr.onclick = () => show(c);
        rows.appendChild(tr);
      }});
}}
function show(c) {{
  const list = (arr) => arr.map(x => `<span class="pill">${{x}}</span>`).join('') || '—';
  detail.innerHTML =
    `<b>第 ${{c.number}} 章 · ${{c.title}}</b>　[${{c.function}}]　POV ${{c.pov}}<br>` +
    `<p>${{c.summary}}</p>` +
    `<div>冲突：${{c.conflict}}</div><div>结果：${{c.outcome}}</div>` +
    `<div>信息变化：${{c.info_change}}</div><div>人物变化：${{c.character_change}}</div>` +
    `<div>线索引：${{list(c.threads)}}</div><div>意象：${{list(c.motifs)}}</div>` +
    `<div>决策：${{list(c.decisions)}}</div><div>认知：${{list(c.knowledge)}}</div>` +
    `<div>关系：${{list(c.relationships)}}</div>`;
}}
povSel.onchange = render; document.getElementById('q').oninput = render;
render();
</script>
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
