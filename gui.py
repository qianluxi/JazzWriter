"""JazzWriter GUI (V2.0) — a story-structure workbench.

Primary artifact is the *structure* (story hypotheses → whole-book plan →
chapter cards), with prose rendering as an optional local rehearsal.

Concurrency: Tkinter is not thread-safe, so every background task first
snapshots all widget values **on the main thread**, runs off-thread, and
re-enables buttons via ``root.after``. Buttons are disabled while a task runs
and overlapping tasks are rejected.

Run::

    python gui.py            (or double-click JazzWriter.bat)
"""

from __future__ import annotations

import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

from core.improviser import STYLES
from engine.outline_expander import TEMPLATE_LABELS
from engine.semantic_similarity import MODES as EVAL_MODES
from improvisation.improvisation_score import MODE_PRESETS
from session import Session
from store import load_runs, save_take

TEXT_PARAMS = [
    ("creativity", "创造程度"),
    ("randomness", "随机扰动"),
    ("motif_reuse", "主题重复"),
    ("character_freedom", "人物自主性"),
    ("surprise_level", "剧情转折"),
    ("style_distance", "语言变化"),
]
STRUCTURE_PARAMS = [
    ("idea_divergence", "创意发散"),
    ("causal_variation", "因果变化"),
    ("character_agency", "人物自主"),
    ("motif_transformation", "意象变义"),
    ("revelation_delay", "延迟揭露"),
    ("continuity_strength", "连续性约束"),
]
DEFAULT_STYLES = ["冷静观察", "象征增强", "心理深入"]


def _setup_fonts(root: tk.Tk) -> None:
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        try:
            tkfont.nametofont(name).configure(size=10)
        except Exception:
            pass
    try:
        tkfont.nametofont("TkDefaultFont").configure(family="Microsoft YaHei UI")
        tkfont.nametofont("TkTextFont").configure(family="Microsoft YaHei UI")
    except Exception:
        pass


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.session: Session | None = None
        self.ideas = []
        self._busy = False
        self._buttons: list[ttk.Button] = []
        root.title("JazzWriter · 小说结构即兴引擎")
        root.geometry("1280x820")
        _setup_fonts(root)
        self._build_toolbar()
        self._build_body()
        self._build_statusbar()
        self._reload_session()

    # -- layout -------------------------------------------------------------
    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self.root, padding=(10, 8, 10, 4))
        bar.pack(fill="x")
        ttk.Label(bar, text="模型:").pack(side="left")
        self.provider_var = tk.StringVar(value="mock")
        ttk.Combobox(bar, textvariable=self.provider_var,
                     values=["mock", "opencode", "openai"], width=10,
                     state="readonly").pack(side="left", padx=(4, 12))
        ttk.Label(bar, text="评价:").pack(side="left")
        self.eval_var = tk.StringVar(value="lexical")
        ttk.Combobox(bar, textvariable=self.eval_var, values=list(EVAL_MODES),
                     width=10, state="readonly").pack(side="left", padx=(4, 12))
        ttk.Button(bar, text="重载设定", command=self._reload_session).pack(side="left")
        self.loaded_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.loaded_var, foreground="#0a7").pack(side="right")

    def _build_body(self) -> None:
        paned = ttk.Panedwindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=6)
        left_outer = ttk.Frame(paned)
        right = ttk.Frame(paned, padding=4)
        paned.add(left_outer, weight=0)
        paned.add(right, weight=1)
        self._build_controls(self._scrollable(left_outer))
        self._build_output(right)

    def _scrollable(self, parent):
        canvas = tk.Canvas(parent, borderwidth=0, highlightthickness=0, width=360)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, padding=4)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
        return inner

    def _build_controls(self, p) -> None:
        ttk.Label(p, text="场景 / 章节摘要 Scene").pack(anchor="w")
        self.scene_text = tk.Text(p, width=42, height=5, wrap="word")
        self.scene_text.pack(fill="x", pady=(2, 2))
        self.scene_text.insert("1.0", "一场技术事故改变了一个家庭。")
        ttk.Label(p, text="提示：正文演练时每行一章；「按结构渲染」使用已生成的章节摘要。",
                  foreground="#888", wraplength=330, justify="left").pack(anchor="w", pady=(0, 6))

        grid = ttk.Frame(p)
        grid.pack(fill="x")
        self.mode_var = tk.StringVar(value="classic_jazz")
        self.pov_var = tk.StringVar(value="")
        self.style_var = tk.StringVar(value="现实主义")
        self.chapter_var = tk.IntVar(value=1)
        self.total_var = tk.IntVar(value=12)
        self.seed_var = tk.StringVar(value="")
        self.template_var = tk.StringVar(value="linear_causality")
        self.chapters_var = tk.IntVar(value=12)
        self.pick_var = tk.IntVar(value=1)
        rows = [
            ("即兴模式", ttk.Combobox(grid, textvariable=self.mode_var, state="readonly",
                                    values=list(MODE_PRESETS.keys()), width=16)),
            ("视角 POV", ttk.Combobox(grid, textvariable=self.pov_var, state="readonly", width=16)),
            ("Solo 色彩", ttk.Combobox(grid, textvariable=self.style_var, state="readonly",
                                     values=list(STYLES.keys()), width=16)),
            ("结构模板", ttk.Combobox(grid, textvariable=self.template_var, state="readonly",
                                    values=list(TEMPLATE_LABELS.keys()), width=16)),
            ("章节", ttk.Spinbox(grid, from_=1, to=999, textvariable=self.chapter_var, width=8)),
            ("全书章数", ttk.Spinbox(grid, from_=1, to=200, textvariable=self.chapters_var, width=8)),
            ("采纳方案#", ttk.Spinbox(grid, from_=1, to=10, textvariable=self.pick_var, width=8)),
            ("随机种子", ttk.Entry(grid, textvariable=self.seed_var, width=18)),
        ]
        for i, (label, widget) in enumerate(rows):
            ttk.Label(grid, text=label).grid(row=i, column=0, sticky="w", pady=2)
            widget.grid(row=i, column=1, sticky="ew", pady=2)
        grid.columnconfigure(1, weight=1)
        self.pov_combo = grid.grid_slaves(row=1, column=1)[0]
        grid.grid_slaves(row=0, column=1)[0].bind("<<ComboboxSelected>>", self._on_mode_change)

        self.custom_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(p, text="使用自定义参数", variable=self.custom_var).pack(anchor="w", pady=(6, 2))
        self.sliders: dict[str, tk.DoubleVar] = {}
        sframe = ttk.LabelFrame(p, text="结构参数")
        sframe.pack(fill="x", pady=2)
        self._add_sliders(sframe, STRUCTURE_PARAMS)
        tframe = ttk.LabelFrame(p, text="文本参数")
        tframe.pack(fill="x", pady=2)
        self._add_sliders(tframe, TEXT_PARAMS)

        self.save_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(p, text="保存到 output 并记录动机", variable=self.save_var).pack(anchor="w", pady=(6, 2))

        ttk.Label(p, text="① 结构即兴（主要产物）", foreground="#06c").pack(anchor="w", pady=(6, 0))
        self._btn(p, "生成创意方案", self.on_ideas)
        self._btn(p, "采纳并展开全书结构", self.on_build)
        self._btn(p, "校验结构", self.on_validate)
        self._btn(p, "重新即兴选中章", self.on_reimprovise)
        self._btn(p, "锁定 / 解锁选中章", self.on_toggle_lock)
        self._btn(p, "导出结构 Markdown", self.on_export)

        ttk.Label(p, text="② 局部演练（可选）", foreground="#06c").pack(anchor="w", pady=(6, 0))
        self._btn(p, "按结构渲染正文", self.on_render)
        self._btn(p, "▶ 演奏一章（试写）", self.on_play)
        self._btn(p, "≣ 多版本 · 探索路径", self.on_takes)
        self._btn(p, "下一章场景建议", self.on_plan)

    def _add_sliders(self, parent, specs) -> None:
        for key, label in specs:
            var = tk.DoubleVar(value=MODE_PRESETS["bebop"].get(key, 0.5))
            self.sliders[key] = var
            row = ttk.Frame(parent)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=label, width=9).pack(side="left")
            val = ttk.Label(row, text=f"{var.get():.2f}", width=4)
            ttk.Scale(row, from_=0.0, to=1.0, variable=var, orient="horizontal",
                      command=lambda _v, k=key: self._refresh_val(k)).pack(side="left", fill="x", expand=True, padx=2)
            val.pack(side="left")
            setattr(self, f"_val_{key}", val)

    def _btn(self, parent, text, command):
        b = ttk.Button(parent, text=text, command=command)
        b.pack(fill="x", pady=2)
        self._buttons.append(b)
        return b

    def _build_output(self, parent) -> None:
        self.nb = ttk.Notebook(parent)
        self.nb.pack(fill="both", expand=True)
        self.tabs: dict[str, tk.Text] = {}

        for name in ["创意候选", "全书结构", "章节卡片", "正文", "即兴决策", "评价", "建议", "状态", "历史"]:
            frame = ttk.Frame(self.nb)
            txt = tk.Text(frame, wrap="word", state="disabled", padx=8, pady=6)
            sb = ttk.Scrollbar(frame, command=txt.yview)
            txt.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            txt.pack(side="left", fill="both", expand=True)
            self.nb.add(frame, text=name)
            self.tabs[name] = txt

        # structure tree tab
        sframe = ttk.Frame(self.nb)
        self.tree = ttk.Treeview(sframe, columns=("function", "pov", "status"), show="tree headings")
        self.tree.heading("#0", text="卷 / 章")
        self.tree.heading("function", text="功能")
        self.tree.heading("pov", text="POV")
        self.tree.heading("status", text="状态")
        self.tree.column("#0", width=220)
        self.tree.column("function", width=90)
        self.tree.column("pov", width=70)
        self.tree.column("status", width=80)
        tsb = ttk.Scrollbar(sframe, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tsb.set)
        tsb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.nb.add(sframe, text="结构树")
        self.tree_tab_index = self.nb.index("end") - 1

    def _build_statusbar(self) -> None:
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(self.root, textvariable=self.status_var, relief="sunken",
                  anchor="w", padding=(8, 3)).pack(fill="x", side="bottom")

    # -- helpers ------------------------------------------------------------
    def _set_tab(self, name: str, text: str) -> None:
        widget = self.tabs[name]
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _refresh_val(self, key: str) -> None:
        getattr(self, f"_val_{key}").configure(text=f"{self.sliders[key].get():.2f}")

    def _on_mode_change(self, _event=None) -> None:
        preset = MODE_PRESETS.get(self.mode_var.get(), {})
        for key, var in self.sliders.items():
            if key in preset:
                var.set(preset[key])
                self._refresh_val(key)

    def _snapshot(self) -> dict:
        """Read ALL widget values on the main thread (Tkinter safety)."""
        return {
            "scene": self.scene_text.get("1.0", "end").strip(),
            "pov": self.pov_var.get() or None,
            "style": self.style_var.get(),
            "mode": self.mode_var.get(),
            "chapter": self.chapter_var.get(),
            "total": self.chapters_var.get(),
            "template": self.template_var.get(),
            "pick": self.pick_var.get(),
            "seed": int(self.seed_var.get()) if self.seed_var.get().strip() else None,
            "overrides": ({k: v.get() for k, v in self.sliders.items()} if self.custom_var.get() else {}),
            "save": self.save_var.get(),
        }

    # -- session ------------------------------------------------------------
    def _reload_session(self) -> None:
        try:
            self.session = Session.load(provider=self.provider_var.get(), eval_mode=self.eval_var.get())
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("加载失败", f"无法加载设定:\n{exc}")
            return
        names = list(self.session.characters.keys())
        self.pov_combo.configure(values=names)
        if names and self.pov_var.get() not in names:
            self.pov_var.set(names[0])
        self.loaded_var.set(f"人物 {len(names)} · provider={self.session.provider_name}")
        self._set_tab("状态", self._status_text())
        self._populate_tree()

    # -- async runner (snapshot-first, single-flight, disable buttons) ------
    def _async(self, work, done, *, label="处理中…") -> None:
        if self._busy:
            messagebox.showinfo("请稍候", "已有任务在执行，请等待完成。")
            return
        self._busy = True
        self._set_buttons(False)
        self.status_var.set(label)

        def runner():
            try:
                result = work()
            except Exception as exc:  # noqa: BLE001
                result = exc
            self.root.after(0, lambda: self._finish(result, done))

        threading.Thread(target=runner, daemon=True).start()

    def _finish(self, result, done) -> None:
        self._busy = False
        self._set_buttons(True)
        if isinstance(result, Exception):
            self.status_var.set("出错")
            messagebox.showerror("出错", str(result))
            return
        self.status_var.set("就绪")
        done(result)

    def _set_buttons(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for b in self._buttons:
            b.configure(state=state)

    # -- structure actions --------------------------------------------------
    def on_ideas(self) -> None:
        if self.session is None:
            return
        snap = self._snapshot()
        if not snap["scene"]:
            messagebox.showwarning("缺少前提", "请在场景框写下故事前提。")
            return
        premise = snap["scene"]

        def work():
            return self.session.story_ideas(premise, seed=snap["seed"], use_llm=True)

        self._async(work, self._render_ideas, label="发散故事方案…")

    def _render_ideas(self, ideas) -> None:
        self.ideas = ideas
        lines = []
        for i, idea in enumerate(ideas, 1):
            lines.append(f"【方案 {i}】{idea.label}　差异度 {idea.distinctness:.0%}")
            lines.append(f"  因果机制：{idea.causal_mechanism}")
            lines.append(f"  真相性质：{idea.truth_nature}")
            lines.append(f"  关系走向：{idea.character_relation}")
            lines.append(f"  结局方向：{idea.ending_direction}")
            if idea.rationale:
                lines.append(f"  理由：{idea.rationale}")
            lines.append("")
        lines.append("在“采纳方案#”里选择编号，然后点「采纳并展开全书结构」。")
        self._set_tab("创意候选", "\n".join(lines))
        self.nb.select(0)

    def on_build(self) -> None:
        if self.session is None:
            return
        snap = self._snapshot()
        if not snap["scene"]:
            messagebox.showwarning("缺少前提", "请在场景框写下故事前提。")
            return
        if not self.ideas:
            messagebox.showinfo("先生成创意", "请先点「生成创意方案」。")
            return
        premise = snap["scene"]
        pick = max(1, snap["pick"]) - 1

        def work():
            book = self.session.build_book(premise, self.ideas, pick=pick,
                                           chapters=snap["total"], template=snap["template"],
                                           seed=snap["seed"])
            report = self.session.validate_book(book)
            return book, report

        self._async(work, self._render_book_result, label="展开全书结构…")

    def _render_book_result(self, result) -> None:
        book, report = result
        self._populate_tree(book)
        self._set_tab("全书结构", self._structure_text(book))
        self._set_tab("评价", self._structure_report_text(report))
        self.nb.select(self.tree_tab_index)

    def on_validate(self) -> None:
        if self.session is None:
            return
        self._async(lambda: self.session.validate_book(), self._render_validate, label="校验结构…")

    def _render_validate(self, report) -> None:
        self._set_tab("评价", self._structure_report_text(report))
        self.nb.select(list(self.tabs).index("评价"))

    def on_reimprovise(self) -> None:
        number = self._selected_chapter()
        if number is None:
            messagebox.showinfo("选择章节", "请在结构树里选中一章。")
            return
        snap = self._snapshot()

        def work():
            return self.session.reimprovise_chapter(number, seed=snap["seed"])

        self._async(work, self._render_reimprov, label=f"重新即兴第 {number} 章…")

    def _render_reimprov(self, result) -> None:
        book, affected = result
        self._populate_tree(book)
        self._set_tab("章节卡片", f"已重新即兴；锁定章节保持不变。\n可能受影响的后续章节：{affected}\n\n" + self._cards_text(book))
        self.nb.select(self.tree_tab_index)
        messagebox.showinfo("完成", f"已重新即兴。可能受影响的后续章节：{affected}")

    def on_toggle_lock(self) -> None:
        if self.session is None:
            return
        number = self._selected_chapter()
        if number is None or self.session.book is None:
            messagebox.showinfo("选择章节", "请先展开结构，并在结构树里选中一章。")
            return
        chapter = self.session.book.chapter(number)
        if chapter and chapter.locked:
            self.session.unlock_chapter(number)
        else:
            self.session.lock_chapter(number)
        self._populate_tree(self.session.book)
        self._set_tab("章节卡片", self._cards_text(self.session.book))

    def on_export(self) -> None:
        if self.session is None:
            return
        self._async(self.session.export_outline, self._render_export, label="导出结构…")

    def _render_export(self, path) -> None:
        messagebox.showinfo("已导出", f"结构已导出到：\n{path}")
        self.status_var.set(f"已导出 {path}")

    # -- prose actions ------------------------------------------------------
    def on_render(self) -> None:
        if self.session is None:
            return
        if self.session.book is None:
            messagebox.showinfo("尚无结构", "请先「采纳并展开全书结构」。")
            return
        snap = self._snapshot()

        def work():
            return self.session.render_book_from_plan(
                pov=snap["pov"], style=snap["style"], jazz_mode=snap["mode"],
                seed=snap["seed"], overrides=snap["overrides"], save=snap["save"])

        self._async(work, self._render_book_prose, label="按结构渲染正文…")

    def _render_book_prose(self, results) -> None:
        body, evals = [], []
        for i, take, eva in results:
            body.append(f"──────── 第 {i} 章 · {take.style} ────────\n{take.text}\n")
            evals.append(f"【第 {i} 章】\n{self._eval_text(eva)}")
        self._set_tab("正文", "\n".join(body))
        self._set_tab("评价", "\n\n".join(evals))
        self.nb.select(list(self.tabs).index("正文"))

    def on_play(self) -> None:
        if self.session is None:
            return
        snap = self._snapshot()
        if not snap["scene"]:
            messagebox.showwarning("缺少场景", "请先填写场景。")
            return

        def work():
            take, eva = self.session.play(
                snap["scene"], pov=snap["pov"], style=snap["style"],
                chapter=snap["chapter"], total_chapters=snap["total"],
                jazz_mode=snap["mode"], seed=snap["seed"], overrides=snap["overrides"],
                previous_texts=self.session.recent_texts(5))
            advice = self.session.advise(take, eva, pov=snap["pov"])
            skeletons = self.session.plan(take, eva, count=3)
            if snap["save"]:
                save_take(take, eva, index=1)
                self.session.record_motifs(take)
                self.session.persist_motifs()
            return take, eva, advice, skeletons

        self._async(work, self._render_play, label="演奏中…")

    def _render_play(self, result) -> None:
        take, eva, advice, skeletons = result
        header = f"──────── 第 {take.chapter} 章 · {take.mode} · {take.style} · POV {take.pov} ────────\n"
        self._set_tab("正文", header + take.text)
        self._set_tab("即兴决策", self._cue_text(take))
        self._set_tab("评价", self._eval_text(eva))
        self._set_tab("建议", self._advice_text(advice) + "\n\n" + self._plan_text(skeletons))
        self.nb.select(list(self.tabs).index("正文"))

    def on_takes(self) -> None:
        if self.session is None:
            return
        snap = self._snapshot()
        if not snap["scene"]:
            messagebox.showwarning("缺少场景", "请先填写场景。")
            return

        def work():
            return self.session.variations(
                snap["scene"], pov=snap["pov"], styles=DEFAULT_STYLES,
                chapter=snap["chapter"], total_chapters=snap["total"],
                jazz_mode=snap["mode"], seed=snap["seed"], overrides=snap["overrides"],
                explore=True)

        self._async(work, self._render_takes, label="多版本探索…")

    def _render_takes(self, results) -> None:
        body, cues, evals = [], [], []
        for i, (take, eva) in enumerate(results, 1):
            body.append(f"──── Take {i} · {take.style} ────\n{take.text}\n")
            cues.append(self._cue_text(take))
            evals.append(f"【Take {i}】\n{self._eval_text(eva)}")
            if self.save_var.get():
                save_take(take, eva, index=i)
                self.session.record_motifs(take)
        if self.save_var.get():
            self.session.persist_motifs()
        self._set_tab("正文", "\n".join(body))
        self._set_tab("即兴决策", "\n\n".join(cues))
        self._set_tab("评价", "\n\n".join(evals))
        self.nb.select(list(self.tabs).index("正文"))

    def on_plan(self) -> None:
        if self.session is None:
            return
        self._async(lambda: self.session.plan(count=3), self._render_plan, label="规划场景…")

    def _render_plan(self, skeletons) -> None:
        self._set_tab("建议", self._plan_text(skeletons))
        self.nb.select(list(self.tabs).index("建议"))

    # -- tree / cards -------------------------------------------------------
    def _populate_tree(self, book=None) -> None:
        book = book or (self.session.book if self.session else None)
        self.tree.delete(*self.tree.get_children())
        self._tree_chapters = {}
        if not book:
            return
        for vol in book.volumes:
            vnode = self.tree.insert("", "end", text=f"第 {vol.number} 卷 · {vol.title}", open=True)
            for ch in vol.chapters:
                status = "🔒锁定" if ch.locked else ch.status
                node = self.tree.insert(vnode, "end",
                                        text=f"第 {ch.number} 章 · {ch.title}",
                                        values=(ch.function, ch.pov, status))
                self._tree_chapters[node] = ch.number

    def _selected_chapter(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return getattr(self, "_tree_chapters", {}).get(sel[0])

    def _on_tree_select(self, _event=None) -> None:
        number = self._selected_chapter()
        if number is None or not self.session or self.session.book is None:
            return
        ch = self.session.book.chapter(number)
        if ch:
            self._set_tab("章节卡片", self._card_text(ch))

    # -- formatters ---------------------------------------------------------
    @staticmethod
    def _card_text(ch) -> str:
        lines = [f"第 {ch.number} 章 · {ch.title}　[{ch.status}]", ""]
        for label, value in (("功能", ch.function), ("POV", ch.pov), ("起因", ch.premise),
                             ("关键行动", ch.key_action), ("冲突", ch.conflict),
                             ("结果", ch.outcome), ("代价", ch.stakes),
                             ("信息变化", ch.info_change), ("人物变化", ch.character_change),
                             ("线索", "、".join(ch.threads)), ("意象", "、".join(ch.motifs)),
                             ("承接上一章", ch.hook_from), ("驱向下一章", ch.hook_to),
                             ("摘要", ch.summary)):
            if value:
                lines.append(f"  {label}：{value}")
        return "\n".join(lines)

    def _cards_text(self, book) -> str:
        return "\n\n".join(self._card_text(ch) for ch in book.chapters())

    @staticmethod
    def _structure_text(book) -> str:
        lines = [f"《{book.title}》　模板：{book.structure_template}"]
        if book.logline:
            lines.append(f"核心创意：{book.logline}")
        if book.question:
            lines.append(f"核心命题：{book.question}")
        if book.main_conflict:
            lines.append(f"主要冲突：{book.main_conflict}")
        if book.key_turns:
            lines.append("关键转折：")
            lines += [f"  - {t}" for t in book.key_turns]
        if book.ending:
            lines.append(f"结局：{book.ending}")
        lines.append("")
        for vol in book.volumes:
            lines.append(f"== 第 {vol.number} 卷 · {vol.title} ==")
            for label, value in (("目标", vol.goal), ("开端", vol.opening_state),
                                 ("高潮", vol.climax), ("结果", vol.outcome),
                                 ("承接", vol.sets_up_next)):
                if value:
                    lines.append(f"  {label}：{value}")
            lines.append("  " + "、".join(f"第{c.number}章({c.function})" for c in vol.chapters))
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _structure_report_text(report) -> str:
        labels = {
            "idea_uniqueness": "创意独特性", "completeness": "故事完整性",
            "causal_continuity": "因果连续性", "character_change": "人物变化",
            "chapter_contribution": "章节贡献", "foreshadowing": "伏笔与回收",
        }
        lines = [f"综合 {report.overall:.0%}"]
        for k, v in report.dimensions.items():
            bar = "█" * int(round(v * 10))
            lines.append(f"  {labels.get(k, k):<6} {v:5.0%} {bar}")
        if report.issues:
            lines.append("")
            lines.append("具体问题：")
            lines += [f"  · {i}" for i in report.issues]
        for note in report.notes:
            lines.append(f"  ({note})")
        return "\n".join(lines)

    @staticmethod
    def _cue_text(take) -> str:
        cue = take.cue or {}
        if not cue:
            return "(无 Cue)"
        js = cue.get("jazz_seed", {})
        rhythm = cue.get("rhythm", {})
        solo = cue.get("solo", {})
        lines = [f"模式: {cue.get('mode')}　种子: {cue.get('seed_int')}",
                 f"色彩: {js.get('emotion','-')} / {js.get('perspective','-')} / {js.get('symbol','-')}",
                 f"节奏: {rhythm.get('name','-')}　独奏: {solo.get('character','-')}·{solo.get('instrument','-')}"]
        ops = (cue.get("operators", {}) or {}).get("operators", [])
        for op in ops:
            lines.append(f"操作: [{op.get('name')}] {op.get('directive')}")
        for s in cue.get("surprises", []):
            lines.append(f"意外: [{s.get('category')}] {s.get('detail')}")
        return "\n".join(lines)

    @staticmethod
    def _eval_text(eva) -> str:
        labels = {"theme": "主题", "character": "人物", "emotion": "情绪",
                  "motif": "动机", "novelty": "新鲜度", "harmony": "和声"}
        lines = [f"总分 {eva.overall:.0%}　评级 {eva.grade}"]
        for k, v in eva.metrics.items():
            lines.append(f"  {labels.get(k, k):<4} {v:5.0%} " + "█" * int(round(v * 10)))
        for k, v in (eva.signals or {}).items():
            lines.append(f"  {k:<18} {v:.0%}")
        for n in eva.notes + eva.listening:
            lines.append(f"  · {n}")
        return "\n".join(lines)

    @staticmethod
    def _advice_text(advice) -> str:
        d = advice.to_dict()
        lines = ["下一轮调整建议:"]
        lines += [f"  · {n}" for n in d["notes"]]
        if d.get("deltas"):
            lines.append("  参数变化: " + ", ".join(f"{k}{v:+.2f}" for k, v in d["deltas"].items()))
        return "\n".join(lines)

    @staticmethod
    def _plan_text(skeletons) -> str:
        if not skeletons:
            return "(无建议)"
        lines = ["下一章场景骨架:"]
        for i, sk in enumerate(skeletons, 1):
            lines.append(f"{chr(64+i)}. {sk.goal}")
            lines.append(f"   POV {sk.pov} · {sk.surface_action}")
            lines.append(f"   即兴方向: {sk.improv_direction}")
            lines.append(f"   信息边界: {sk.info_boundary}")
            lines.append(f"   退出点: {sk.exit_point}")
        return "\n".join(lines)

    def _status_text(self) -> str:
        s = self.session
        if s is None:
            return "(未加载)"
        lines = ["【主题】", s.theme.as_prompt(), "", "【叙事和声】", s.harmony.as_prompt(), "", "【乐手】"]
        for c in s.characters.values():
            lines.append(f"  - {c.name}（{c.role}）欲望: {c.desire}")
        lines += ["", "【动机】"]
        for m in s.motifs.all():
            lines.append(f"  - {m.name}: {m.count} 次")
        lines += ["", "【故事状态】", s.story_state.summary()]
        return "\n".join(lines)

    @staticmethod
    def _history_text() -> str:
        records = load_runs()
        if not records:
            return "(暂无运行记录)"
        lines = ["章节  时间      种子  模式        风格      总分  评级"]
        for r in sorted(records, key=lambda x: x.get("created_at", "")):
            eva = r.get("evaluation", {})
            lines.append(
                f"{r.get('chapter','?'):>3}  {(r.get('created_at','') or '')[11:19]}  "
                f"{r.get('seed',''):>5}  {r.get('mode',''):<10} {r.get('style',''):<8} "
                f"{eva.get('overall',0):.0%}  {eva.get('grade','')}")
        return "\n".join(lines)


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
