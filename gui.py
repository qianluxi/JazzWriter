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

import json
import threading
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import messagebox, ttk

from core.chapter_plan import (apply_text, format_decisions, format_knowledge,
                               format_relationships, parse_decisions, parse_knowledge,
                               parse_relationships, to_text)
from core.improviser import STYLES
from engine.outline_expander import TEMPLATE_LABELS
from engine.project_manager import ProjectManager
from engine.semantic_similarity import MODES as EVAL_MODES
from llm import get_provider
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


class SingleFlight:
    """Pure single-task guard: only one background task at a time.

    Extracted from the GUI so it is testable without a display. The App uses it
    to reject overlapping tasks and to re-enable buttons on completion/failure.
    """

    def __init__(self) -> None:
        self._busy = False

    @property
    def busy(self) -> bool:
        return self._busy

    def begin(self) -> bool:
        if self._busy:
            return False
        self._busy = True
        return True

    def end(self) -> None:
        self._busy = False


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
        self._flight = SingleFlight()
        self._buttons: list[ttk.Button] = []
        self.data_dir: Path | None = None
        self._project_map: dict[str, Path] = {}
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
        ttk.Label(bar, text="项目:").pack(side="left")
        self.project_var = tk.StringVar(value="（默认 data/）")
        self.project_combo = ttk.Combobox(bar, textvariable=self.project_var,
                                         width=18, state="readonly")
        self.project_combo.pack(side="left", padx=(4, 4))
        ttk.Button(bar, text="打开", command=self.on_open_project).pack(side="left")
        ttk.Button(bar, text="编辑/重建", command=self.on_rebuild_project).pack(side="left", padx=(4, 0))
        ttk.Button(bar, text="新建项目", command=self.on_new_project).pack(side="left", padx=(4, 0))
        ttk.Button(bar, text="删除项目", command=self.on_delete_project).pack(side="left", padx=(4, 12))
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
        self.fuse_a_var = tk.IntVar(value=1)
        self.fuse_b_var = tk.IntVar(value=2)
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
            ("融合方案A#", ttk.Spinbox(grid, from_=1, to=10, textvariable=self.fuse_a_var, width=8)),
            ("融合方案B#", ttk.Spinbox(grid, from_=1, to=10, textvariable=self.fuse_b_var, width=8)),
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
        self._btn(p, "融合所选两个方案", self.on_fuse)
        self._btn(p, "采纳并展开全书结构", self.on_build)
        self._btn(p, "校验结构", self.on_validate)
        self._btn(p, "保存章节卡片编辑", self.on_save_card)
        self._btn(p, "保存 JSON 到选中章（嵌套字段）", self.on_save_card_json)
        self._btn(p, "编辑人物/关系变化（表单）", self.on_edit_participation)
        self._btn(p, "重新即兴选中章（可选范围）", self.on_reimprovise)
        self._btn(p, "锁定 / 解锁选中章", self.on_toggle_lock)
        self._btn(p, "导出结构 Markdown", self.on_export)
        self._btn(p, "叙事偏离检测", self.on_deviation)
        self._btn(p, "导出故事板（交互式 HTML）", self.on_report)

        ttk.Label(p, text="② 局部演练（可选）", foreground="#06c").pack(anchor="w", pady=(6, 0))
        self._btn(p, "按结构渲染正文", self.on_render)
        self._btn(p, "Jam Session（导演/独奏/观察/编辑）", self.on_jam)
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

        for name in ["创意候选", "全书结构", "章节卡片", "卡片JSON", "人物", "Jam", "正文", "即兴决策", "评价", "建议", "状态", "历史"]:
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
            "fuse_a": self.fuse_a_var.get(),
            "fuse_b": self.fuse_b_var.get(),
            "seed": int(self.seed_var.get()) if self.seed_var.get().strip() else None,
            "overrides": ({k: v.get() for k, v in self.sliders.items()} if self.custom_var.get() else {}),
            "save": self.save_var.get(),
        }

    # -- session ------------------------------------------------------------
    def _reload_session(self) -> None:
        try:
            self.session = Session.load(data_dir=self.data_dir,
                                        provider=self.provider_var.get(),
                                        eval_mode=self.eval_var.get())
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("加载失败", f"无法加载设定:\n{exc}")
            return
        self._refresh_projects()
        names = [c.name for c in self.session.characters.values()]
        self.pov_combo.configure(values=names)
        if names and self.pov_var.get() not in names:
            self.pov_var.set(names[0])
        self.loaded_var.set(
            f"项目：{self._current_project_label()} · 人物 {len(names)} · provider={self.session.provider_name}")
        self._set_tab("状态", self._status_text())
        self._set_tab("人物", self._characters_text())
        self._populate_tree()

    # -- project management --------------------------------------------------
    def _current_project_label(self) -> str:
        if self.data_dir is None:
            return "默认 data/"
        for name, p in self._project_map.items():
            if Path(p).resolve() == Path(self.data_dir).resolve():
                return name
        return Path(self.data_dir).name

    def _refresh_projects(self) -> None:
        try:
            items = ProjectManager().list_projects()
        except Exception:  # noqa: BLE001
            items = []
        self._project_map = {it["name"]: it["path"] for it in items}
        self.project_combo.configure(values=["（默认 data/）"] + list(self._project_map))
        if self.data_dir is None:
            self.project_var.set("（默认 data/）")
        else:
            for name, p in self._project_map.items():
                if Path(p).resolve() == Path(self.data_dir).resolve():
                    self.project_var.set(name)
                    break

    def on_open_project(self) -> None:
        name = self.project_var.get()
        if name in ("", "（默认 data/）"):
            self.data_dir = None
        elif name in self._project_map:
            self.data_dir = self._project_map[name]
        else:
            messagebox.showwarning("无法打开", f"未找到项目：{name}")
            return
        self._reload_session()
        if self.session is None:
            return
        title = self.session.theme.title or self._current_project_label()
        self.status_var.set(f"已打开：{title}")
        messagebox.showinfo("已打开项目",
                            f"《{title}》\n目录：{self.data_dir or 'data/'}\n"
                            f"人物：{len(self.session.characters)}")

    def on_rebuild_project(self) -> None:
        if self.data_dir is None:
            messagebox.showinfo("请选择项目",
                                "先在顶部「项目」下拉选择要重建的项目（默认 data/ 不在此重建）。")
            return
        path = Path(self.data_dir)
        manager = ProjectManager()
        current_brief = manager.read_brief(path)
        title = (self.session.theme.title if self.session else "") or path.name

        win = tk.Toplevel(self.root)
        win.title(f"编辑 / 重建项目 · {path.name}")
        win.transient(self.root)
        win.grab_set()
        win.geometry("760x620")
        ttk.Label(win, text="项目名称").pack(anchor="w", padx=10, pady=(10, 2))
        name_var = tk.StringVar(value=title)
        ttk.Entry(win, textvariable=name_var, width=44).pack(anchor="w", padx=10)
        ttk.Label(win, text="世界观 / 大致剧情（修改后重建会据此重新生成整套设定）").pack(
            anchor="w", padx=10, pady=(10, 2))
        brief = tk.Text(win, height=18, wrap="word")
        brief.pack(fill="both", expand=True, padx=10)
        brief.insert("1.0", current_brief or "在此写下世界观与大致剧情……")
        ttk.Label(win, foreground="#a33", wraplength=720, justify="left",
                  text="注意：重建会用上面的简介重新生成 story / characters / relationships / motifs / "
                       "story_state；旧文件（含已保存的结构 book_plan）会移入 _backup_* 目录，之后需要重新“生成创意→采纳并展开”。"
                  ).pack(anchor="w", padx=10, pady=(8, 0))

        def do_rebuild():
            new_name = name_var.get().strip() or path.name
            text = brief.get("1.0", "end").strip()
            if not text:
                messagebox.showwarning("缺少简介", "请填写世界观/剧情简介。", parent=win)
                return
            if not messagebox.askyesno("确认重建", "确定要重建该项目吗？旧文件会归档到 _backup_*。", parent=win):
                return
            win.destroy()

            def work():
                return ProjectManager(llm=self._project_llm()).regenerate(path, text, new_name)

            self._async(work, self._on_project_rebuilt, label="正在重建项目…")

        btns = ttk.Frame(win)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="重建", command=do_rebuild).pack(side="right", padx=6)
        ttk.Button(btns, text="取消", command=win.destroy).pack(side="right")

    def on_delete_project(self) -> None:
        if self.data_dir is None:
            messagebox.showinfo("请选择项目", "先在顶部「项目」下拉选择要删除的项目（默认 data/ 不可删除）。")
            return
        path = Path(self.data_dir)
        title = (self.session.theme.title if self.session else "") or path.name
        if not messagebox.askyesno(
                "确认删除",
                f"确定删除项目《{title}》吗？\n\n将删除本地目录：\n{path}\n"
                "并同步删除在线预览（如已发布）；此操作不可撤销。"):
            return

        def work():
            return ProjectManager(llm=self._project_llm()).delete(path)

        self._async(work, self._on_project_deleted, label="正在删除项目…")

    def _on_project_deleted(self, info) -> None:
        if self.data_dir and Path(self.data_dir) == Path(info["path"]):
            self.data_dir = None
        self._reload_session()
        self.status_var.set(f"已删除项目：{Path(info['path']).name}")
        if info.get("preview_removed"):
            note = "在线预览已删除" + ("并已推送。" if info.get("pushed") else f"（未推送：{info.get('message')}）")
        else:
            note = "在线预览中未找到该项目文件。"
        messagebox.showinfo("已删除", f"项目已删除：{info['path']}\n{note}")

    def _on_project_rebuilt(self, path) -> None:
        self.data_dir = Path(path)
        self._reload_session()
        self.status_var.set(f"项目已重建：{Path(path).name}")
        messagebox.showinfo("已重建", f"项目已用新简介重建：\n{path}\n\n请重新「生成创意方案 → 采纳并展开全书结构」。")

    def _project_llm(self):
        try:
            provider = get_provider(self.provider_var.get())
        except Exception:  # noqa: BLE001
            return None
        return provider if getattr(provider, "name", "mock") not in ("mock", "") else None

    def on_new_project(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("新建项目")
        win.transient(self.root)
        win.grab_set()
        win.geometry("720x580")
        ttk.Label(win, text="项目名称").pack(anchor="w", padx=10, pady=(10, 2))
        name_var = tk.StringVar(value="新主题")
        ttk.Entry(win, textvariable=name_var, width=44).pack(anchor="w", padx=10)
        ttk.Label(win, text="世界观 / 大致剧情（程序据此生成人物、关系与意象）").pack(
            anchor="w", padx=10, pady=(10, 2))
        brief = tk.Text(win, height=18, wrap="word")
        brief.pack(fill="both", expand=True, padx=10)
        brief.insert("1.0", "例如：2020年代的中俄边境小镇，一条冬天封冻的界河。"
                            "一起旧事故、两种互相矛盾的记录，以及几个不肯说出往事的人……")

        def create():
            name = name_var.get().strip()
            text = brief.get("1.0", "end").strip()
            if not name or not text:
                messagebox.showwarning("缺少信息", "请填写项目名称与简介。", parent=win)
                return
            win.destroy()

            def work():
                return ProjectManager(llm=self._project_llm()).create(name, text)

            self._async(work, self._on_project_created, label="正在生成新项目…")

        btns = ttk.Frame(win)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="创建", command=create).pack(side="right", padx=6)
        ttk.Button(btns, text="取消", command=win.destroy).pack(side="right")

    def _on_project_created(self, path) -> None:
        self.data_dir = Path(path)
        self._reload_session()
        self.status_var.set(f"新项目已创建并打开：{path}")
        messagebox.showinfo("已创建", f"项目已生成于：\n{path}\n\n可以直接开始「生成创意方案」。")

    # -- async runner (snapshot-first, single-flight, disable buttons) ------
    def _async(self, work, done, *, label="处理中…") -> bool:
        if not self._flight.begin():
            self.status_var.set("已有任务在执行，请等待完成…")
            return False
        self._set_buttons(False)
        self.status_var.set(label)

        def runner():
            try:
                result = work()
            except Exception as exc:  # noqa: BLE001
                result = exc
            self.root.after(0, lambda: self._finish(result, done))

        threading.Thread(target=runner, daemon=True).start()
        return True

    def _finish(self, result, done) -> None:
        self._flight.end()
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
        self._set_tab("创意候选", self._ideas_text(ideas))
        self.nb.select(0)

    def _ideas_text(self, ideas) -> str:
        base = ideas[0] if ideas else None
        lines = ["五维对照（≠ 表示与方案1不同）", ""]
        for i, idea in enumerate(ideas, 1):
            lines.append(f"【方案 {i}】{idea.label}　差异度 {idea.distinctness:.0%}")
            for label, value, ref in (
                ("因果机制", idea.causal_mechanism, base.causal_mechanism if base else ""),
                ("信息结构/真相", idea.truth_nature, base.truth_nature if base else ""),
                ("人物关系", idea.character_relation, base.character_relation if base else ""),
                ("结局", idea.ending_direction, base.ending_direction if base else ""),
                ("主题解释", idea.theme_reading, base.theme_reading if base else ""),
            ):
                mark = "≠ " if (base and i > 1 and value != ref) else "  "
                lines.append(f"    {mark}{label}：{value}")
            if i > 1 and idea.differentiators:
                lines.append(f"      与方案1的差异：{'、'.join(idea.differentiators)}")
            lines.append("")
        lines.append("在“采纳方案#”里选择编号，然后点「采纳并展开全书结构」。")
        return "\n".join(lines)

    def on_fuse(self) -> None:
        if self.session is None:
            return
        snap = self._snapshot()
        if not snap["scene"]:
            messagebox.showwarning("缺少前提", "请在场景框写下故事前提。")
            return
        if not self.ideas:
            messagebox.showinfo("先生成创意", "请先点「生成创意方案」。")
            return
        a, b = max(1, snap["fuse_a"]) - 1, max(1, snap["fuse_b"]) - 1

        def work():
            fused = self.session.fuse_ideas(self.ideas, a, b, seed=snap["seed"])
            rows = self.session.fuse_compare(self.ideas[a], self.ideas[b], fused)
            return list(self.ideas) + [fused], rows

        self._async(work, self._render_fuse, label="融合方案…")

    def _render_fuse(self, result) -> None:
        ideas, rows = result
        self.ideas = ideas
        fuse_lines = ["融合对照（“取自”表示该维度来自哪个方案）", ""]
        for r in rows:
            fuse_lines.append(f"  {r['dimension']}：A={r['a']}　|　B={r['b']}　|　融合={r['fused']}（取自 {r['from']}）")
        fuse_lines += ["", f"融合方案已加入候选（编号 {len(ideas)}）。", ""]
        self._set_tab("创意候选", "\n".join(fuse_lines) + self._ideas_text(ideas))
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
        if self.session.ideas_stale(self.ideas, premise):
            if not messagebox.askyesno("方案可能已过期",
                                       "故事前提已改过，当前创意方案是旧前提生成的。\n仍要使用这些旧方案吗？"):
                return
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
        self._set_tab("人物", self._characters_text())
        self.nb.select(self.tree_tab_index)

    def on_validate(self) -> None:
        if self.session is None:
            return
        self._async(lambda: self.session.validate_book(), self._render_validate, label="校验结构…")

    def _render_validate(self, report) -> None:
        self._set_tab("评价", self._structure_report_text(report))
        self.nb.select(list(self.tabs).index("评价"))

    def on_reimprovise(self) -> None:
        if self.session is None or self.session.book is None:
            messagebox.showinfo("尚无结构", "请先展开全书结构。")
            return
        number = self._selected_chapter()
        if number is None:
            messagebox.showinfo("选择章节", "请在结构树里选中一章。")
            return
        snap = self._snapshot()
        self._pending_number = number
        self._pending_seed = snap["seed"]
        self._async(lambda: self.session.reimprovise_candidates(number, seed=snap["seed"]),
                    self._render_candidates, label=f"生成第 {number} 章候选…")

    def _render_candidates(self, candidates) -> None:
        if not candidates:
            messagebox.showinfo("无候选", "未生成候选。")
            return
        idx = self._ask_candidate(candidates, self._pending_number)
        if idx is None:
            return
        book, affected = self.session.apply_candidate(candidates[idx])
        self._populate_tree(book)
        self._set_card(self._cards_text(book))
        self.nb.select(self.tree_tab_index)
        scope = self._ask_scope(book.affected_downstream(self._pending_number))
        if not scope:
            messagebox.showinfo("已采纳", f"已采纳候选并写回第 {self._pending_number} 章。\n受影响：{affected}")
            return
        target = sorted(set(scope) - {self._pending_number})

        def work():
            return self.session.regenerate_chapters(target, seed=self._pending_seed)

        self._async(work, self._render_reimprov, label="重生成后续章节…")

    def _render_reimprov(self, result) -> None:
        book, done = result
        self._populate_tree(book)
        self._set_card(self._cards_text(book))
        self.nb.select(self.tree_tab_index)
        messagebox.showinfo("完成", f"已重生成：{done}\n锁定章节与锁定字段保持不变。")

    def on_save_card(self) -> None:
        if self.session is None or self.session.book is None:
            messagebox.showinfo("尚无结构", "请先展开全书结构。")
            return
        number = self._selected_chapter()
        if number is None:
            messagebox.showinfo("选择章节", "请在结构树里选中一章。")
            return
        chapter = self.session.book.chapter(number)
        apply_text(chapter, self.tabs["章节卡片"].get("1.0", "end"))
        self.session.save_book()
        self._populate_tree(self.session.book)
        self.status_var.set(f"已保存第 {number} 章卡片")

    def _ask_scope(self, affected):
        """Modal checklist of downstream chapters to regenerate."""
        if not affected:
            return []
        locked = set(self.session.book.locked_numbers()) if self.session.book else set()
        win = tk.Toplevel(self.root)
        win.title("选择重生成范围")
        win.transient(self.root)
        win.grab_set()
        ttk.Label(win, text="勾选要重新生成的章节（未勾选者保持现有卡片；锁定章不会重生成）",
                  wraplength=320, justify="left").pack(anchor="w", padx=12, pady=8)
        frame = ttk.Frame(win)
        frame.pack(fill="both", expand=True, padx=12)
        vars_map = {}
        for n in affected:
            var = tk.BooleanVar(value=n not in locked)
            cb = ttk.Checkbutton(frame, text=f"第 {n} 章", variable=var)
            cb.pack(anchor="w")
            if n in locked:
                cb.configure(state="disabled")
                var.set(False)
            vars_map[n] = var
        result = {"value": None}

        def ok():
            result["value"] = [n for n, v in vars_map.items() if v.get()]
            win.destroy()

        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=12, pady=8)
        ttk.Button(btns, text="确定", command=ok).pack(side="right", padx=4)
        ttk.Button(btns, text="取消", command=win.destroy).pack(side="right")
        self.root.wait_window(win)
        return result["value"]

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
        self._set_card(self._cards_text(self.session.book))

    def on_export(self) -> None:
        if self.session is None:
            return
        self._async(self.session.export_outline, self._render_export, label="导出结构…")

    def _render_export(self, path) -> None:
        messagebox.showinfo("已导出", f"结构已导出到：\n{path}")
        self.status_var.set(f"已导出 {path}")

    def on_deviation(self) -> None:
        if self.session is None:
            return
        self._async(self.session.deviation_report, self._render_deviation, label="偏离检测…")

    def _render_deviation(self, report) -> None:
        lines = ["偏离检测 · Deviation", ""]
        lines += [f"· {i}" for i in report.issues]
        if report.theme_similarity:
            lines += ["", "主题关联（章节→主题）:"]
            lines += [f"  第 {d['number']} 章　{d['score']:.0%}" for d in report.theme_similarity]
        if report.motif_usage:
            lines += ["", "意象使用次数: " + "，".join(f"{k}×{v}" for k, v in report.motif_usage.items())]
        if report.duplicates:
            lines += ["", "疑似重复:"]
            lines += [f"  第 {d['a_number']} ↔ 第 {d['b_number']} 章　{d['score']:.0%}" for d in report.duplicates[:6]]
        self._set_tab("评价", "\n".join(lines))
        self.nb.select(list(self.tabs).index("评价"))

    def on_report(self) -> None:
        if self.session is None:
            return
        self._async(self.session.write_report, self._render_report, label="导出故事板…")

    def _render_report(self, result) -> None:
        md, html = result
        messagebox.showinfo("已导出", f"故事板：\n{md}\n{html}")
        self.status_var.set(f"已导出 {md.name} / {html.name}")
        try:
            import os
            os.startfile(str(html))  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass

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
        total = 0
        for i, take, eva in results:
            total += take.word_count
            body.append(f"──────── 第 {i} 章 · {take.style} · {take.word_count} 字 ────────\n{take.text}\n")
            evals.append(f"【第 {i} 章】\n{self._eval_text(eva)}")
        body.append(f"──────── 全书：{len(results)} 章 · 共 {total} 字"
                    f"（平均 {total // max(1, len(results))} 字/章）────────")
        self._set_tab("正文", "\n".join(body))
        self._set_tab("评价", "\n\n".join(evals))
        self.nb.select(list(self.tabs).index("正文"))
        info = self.session.last_publish if self.session else None
        if info:
            where = info.get("url") or info.get("path")
            self.status_var.set(f"已渲染并生成在线预览：{where}")
            detail = "已推送到远端" if info.get("pushed") else f"未推送（{info.get('message') or '仅本地'}）"
            messagebox.showinfo("在线正文预览",
                                f"已生成：{info.get('path')}\n{where}\n{detail}")

    def on_jam(self) -> None:
        if self.session is None:
            return
        snap = self._snapshot()
        if not snap["scene"]:
            messagebox.showwarning("缺少场景", "请先填写场景。")
            return
        book = self.session.book
        chapter_number = snap["chapter"] if (book and book.chapter(snap["chapter"])) else None

        def work():
            return self.session.jam(snap["scene"], pov=snap["pov"], chapter_number=chapter_number)

        self._async(work, self._render_jam, label="Jam Session…")

    def _render_jam(self, result) -> None:
        lines = ["【导演 Director】",
                 f"  目标：{result.brief.goal}",
                 f"  方向：{result.brief.direction}",
                 f"  约束：{'；'.join(result.brief.constraints) or '（无）'}",
                 "", "【独奏 Soloist】"]
        lines += [f"  - {m}" for m in result.solo]
        lines += ["", "【观察 Observer】"]
        lines += [f"  - {d}" for d in result.observer]
        lines += ["", "【编辑 Editor · 提案】", result.proposal]
        if result.removed:
            lines += ["", "被排除（疑似提前揭露）："] + [f"  - {r}" for r in result.removed]
        if result.notes:
            lines += [""] + [f"  ({n})" for n in result.notes]
        self._set_tab("Jam", "\n".join(lines))
        self.nb.select(list(self.tabs).index("Jam"))

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
                save_take(take, eva, index=1, outdir=self.session.chapters_dir)
                self.session.record_motifs(take)
                self.session.persist_motifs()
            return take, eva, advice, skeletons

        self._async(work, self._render_play, label="演奏中…")

    def _render_play(self, result) -> None:
        take, eva, advice, skeletons = result
        header = (f"──────── 第 {take.chapter} 章 · {take.mode} · {take.style} · "
                  f"POV {take.pov} · {take.word_count} 字 ────────\n")
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
                save_take(take, eva, index=i, outdir=self.session.chapters_dir)
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
            self._set_card(to_text(ch))
            self._set_json_card(json.dumps(ch.to_dict(), ensure_ascii=False, indent=2))

    # -- formatters ---------------------------------------------------------
    def _set_card(self, text: str) -> None:
        widget = self.tabs["章节卡片"]
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)

    def _set_json_card(self, text: str) -> None:
        widget = self.tabs["卡片JSON"]
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)

    def on_edit_participation(self) -> None:
        if self.session is None or self.session.book is None:
            messagebox.showinfo("尚无结构", "请先展开全书结构。")
            return
        number = self._selected_chapter()
        if number is None:
            messagebox.showinfo("选择章节", "请在结构树里选中一章。")
            return
        ch = self.session.book.chapter(number)
        win = tk.Toplevel(self.root)
        win.title(f"第 {number} 章 · 人物 / 关系变化")
        win.transient(self.root)
        win.grab_set()
        win.geometry("740x580")

        def section(label, hint, initial):
            ttk.Label(win, text=f"{label}　（{hint}）", justify="left",
                      wraplength=710).pack(anchor="w", padx=10, pady=(8, 2))
            box = tk.Text(win, height=4, wrap="word")
            box.pack(fill="x", padx=10)
            box.insert("1.0", initial)
            return box

        dtext = section("人物决策", "每行：character_id | 决策 | 动机",
                        format_decisions(ch.character_decisions))
        ktext = section("认知变化", "每行：character_id | 变化 | 来源 | fact_id(可空)",
                        format_knowledge(ch.knowledge_changes))
        rtext = section("关系变化", "每行：a,b | 变化 | 原因",
                        format_relationships(ch.relationship_changes))

        def save():
            self.session.update_chapter(number, {
                "character_decisions": [d.to_dict() for d in parse_decisions(dtext.get("1.0", "end"))],
                "knowledge_changes": [k.to_dict() for k in parse_knowledge(ktext.get("1.0", "end"))],
                "relationship_changes": [r.to_dict() for r in parse_relationships(rtext.get("1.0", "end"))],
            })
            self._populate_tree(self.session.book)
            self._set_card(to_text(self.session.book.chapter(number)))
            self.status_var.set(f"已保存第 {number} 章人物/关系变化")
            win.destroy()

        btns = ttk.Frame(win)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="保存", command=save).pack(side="right", padx=6)
        ttk.Button(btns, text="取消", command=win.destroy).pack(side="right")

    def on_save_card_json(self) -> None:
        if self.session is None or self.session.book is None:
            messagebox.showinfo("尚无结构", "请先展开全书结构。")
            return
        number = self._selected_chapter()
        if number is None:
            messagebox.showinfo("选择章节", "请在结构树里选中一章。")
            return
        try:
            data = json.loads(self.tabs["卡片JSON"].get("1.0", "end"))
        except json.JSONDecodeError as exc:
            messagebox.showerror("JSON 错误", str(exc))
            return
        try:
            self.session.update_chapter(number, data)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("更新失败", str(exc))
            return
        self._populate_tree(self.session.book)
        self._set_card(to_text(self.session.book.chapter(number)))
        self.status_var.set(f"已保存第 {number} 章 JSON")

    def _cards_text(self, book) -> str:
        return "\n\n".join(to_text(ch) for ch in book.chapters())

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
            "relationship_evolution": "关系演变",
        }
        lines = ["【结构校验（硬问题，优先看这里）】"]
        lines += ([f"  · {i}" for i in report.validation] or ["  · 未发现硬问题"])
        review = getattr(report, "review", []) or []
        if review:
            lines.append("")
            lines.append("【叙事审阅（含依据）】")
            for f in review:
                ch = f"第{f['chapter']}章 " if f.get("chapter") else ""
                tag = "⚠ 事实冲突 " if f.get("kind") == "fact_conflict" else ""
                ev = f"　依据：{f['evidence']}" if f.get("evidence") else ""
                lines.append(f"  · {tag}{ch}{f['issue']}{ev}")
        lines.append("")
        lines.append(f"【参考分数（分数仅供参考）】综合 {report.overall:.0%}")
        for k, v in report.dimensions.items():
            bar = "█" * int(round(v * 10))
            lines.append(f"  {labels.get(k, k):<6} {v:5.0%} {bar}")
        for note in report.notes:
            lines.append(f"  ({note})")
        return "\n".join(lines)

    def _ask_candidate(self, candidates, number):
        win = tk.Toplevel(self.root)
        win.title(f"第 {number} 章 · 即兴候选")
        win.transient(self.root)
        win.grab_set()
        win.geometry("760x460")
        ttk.Label(win, text="选择一个候选采纳（不会覆盖未选中的内容；锁定字段保持不变）").pack(anchor="w", padx=10, pady=6)
        body = ttk.Frame(win)
        body.pack(fill="both", expand=True, padx=10)
        listbox = tk.Listbox(body, width=30)
        listbox.pack(side="left", fill="y")
        preview = tk.Text(body, wrap="word")
        preview.pack(side="left", fill="both", expand=True, padx=(8, 0))
        for i, c in enumerate(candidates, 1):
            tag = "模型" if c.source == "llm" else "离线模板"
            listbox.insert("end", f"[{i}] {tag} · {', '.join(c.changed_fields) or '无'}")

        def show(_e=None):
            sel = listbox.curselection()
            if not sel:
                return
            c = candidates[sel[0]]
            preview.configure(state="normal")
            preview.delete("1.0", "end")
            preview.insert("1.0", f"{c.label}\n\n改动字段：{', '.join(c.changed_fields)}\n{c.note}\n\n"
                                  f"冲突：{c.chapter.conflict}\n结果：{c.chapter.outcome}\n"
                                  f"信息变化：{c.chapter.info_change}\n摘要：{c.chapter.summary}")
            preview.configure(state="disabled")

        listbox.bind("<<ListboxSelect>>", show)
        listbox.selection_set(0)
        show()
        result = {"idx": None}

        def ok():
            sel = listbox.curselection()
            result["idx"] = sel[0] if sel else None
            win.destroy()

        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=10, pady=8)
        ttk.Button(btns, text="采纳", command=ok).pack(side="right", padx=4)
        ttk.Button(btns, text="取消", command=win.destroy).pack(side="right")
        self.root.wait_window(win)
        return result["idx"]

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

    def _characters_text(self) -> str:
        s = self.session
        if s is None:
            return "(未加载)"
        lines = []
        for row in s.character_usage():
            c = s.resolve_character(row["id"])
            lines.append(f"[{row['tier']}] {row['name']} ({row['id']})　POV={'✓' if row['pov'] else '—'}")
            for label, value in (("欲望", c.desire), ("恐惧", c.fear), ("当前目标", c.current_goal)):
                if value:
                    lines.append(f"    {label}：{value}")
            if c.blind_spots:
                lines.append("    盲点：" + "、".join(c.blind_spots))
            if c.secrets:
                lines.append("    秘密：" + "、".join(c.secrets))
            lines.append(f"    参与章：{'、'.join(map(str, row['chapters'])) or '—'}")
            lines.append("")
        rb = s.relationships_brief()
        if rb:
            lines.append("【人物关系网络】")
            lines.append(rb)
        idle = s.idle_characters()
        if idle:
            lines.append("")
            lines.append(f"⚠ 未参与任何章节的人物：{idle}")
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

    def _history_text(self) -> str:
        records = load_runs(outdir=self.session.runs_dir if self.session else None)
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
