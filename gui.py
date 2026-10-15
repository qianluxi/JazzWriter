"""JazzWriter GUI — a simple desktop front-end for the Novel Jazz Engine.

Run with::

    python gui.py

It is a thin shell over the existing ``Session`` API: pick a scene, press
"演奏", and compare takes / cue / evaluation / suggestions. Generation runs in
a background thread so the window never freezes (matters with a real LLM).
"""

from __future__ import annotations

import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

from core.improviser import STYLES
from engine.semantic_similarity import MODES as EVAL_MODES
from improvisation.improvisation_score import MODE_PRESETS
from session import Session
from store import load_runs, save_take

JAZZ_KEYS = [
    ("creativity", "创造程度"),
    ("randomness", "随机扰动"),
    ("motif_reuse", "主题重复"),
    ("character_freedom", "人物自主性"),
    ("surprise_level", "剧情转折"),
    ("style_distance", "语言变化"),
]
MODE_LABELS = {
    "classic_jazz": "classic_jazz（稳）",
    "bebop": "bebop（中）",
    "free_jazz": "free_jazz（飘）",
}
DEFAULT_STYLES = ["冷静观察", "象征增强", "心理深入"]


def _setup_fonts(root: tk.Tk) -> None:
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):
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
        root.title("JazzWriter · 小说爵士引擎")
        root.geometry("1200x760")
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
        ttk.Combobox(bar, textvariable=self.provider_var, values=["mock", "openai"],
                     width=8, state="readonly").pack(side="left", padx=(4, 12))
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
        left = ttk.Frame(paned, padding=4)
        right = ttk.Frame(paned, padding=4)
        paned.add(left, weight=0)
        paned.add(right, weight=1)
        self._build_controls(left)
        self._build_output(right)

    def _build_controls(self, parent) -> None:
        ttk.Label(parent, text="场景 Scene").pack(anchor="w")
        self.scene_text = tk.Text(parent, width=42, height=6, wrap="word")
        self.scene_text.pack(fill="x", pady=(2, 2))
        self.scene_text.insert("1.0", "冬夜。学校食堂，一台报废的蒸汽机仍在运行。")
        ttk.Label(parent, text="提示：「生成全书」按「全书章数」生成；场景每行一章，行数不足会循环复用（# 开头为注释）",
                  foreground="#888", wraplength=330, justify="left").pack(anchor="w", pady=(0, 6))

        grid = ttk.Frame(parent)
        grid.pack(fill="x")
        self.mode_var = tk.StringVar(value="classic_jazz")
        self.pov_var = tk.StringVar(value="")
        self.style_var = tk.StringVar(value="现实主义")
        self.chapter_var = tk.IntVar(value=1)
        self.total_var = tk.IntVar(value=12)
        self.seed_var = tk.StringVar(value="")

        rows = [
            ("即兴模式", ttk.Combobox(grid, textvariable=self.mode_var, state="readonly",
                                    values=list(MODE_PRESETS.keys()), width=16)),
            ("视角 POV", ttk.Combobox(grid, textvariable=self.pov_var, state="readonly", width=16)),
            ("Solo 色彩", ttk.Combobox(grid, textvariable=self.style_var, state="readonly",
                                     values=list(STYLES.keys()), width=16)),
            ("章节", ttk.Spinbox(grid, from_=1, to=999, textvariable=self.chapter_var, width=8)),
            ("全书章数", ttk.Spinbox(grid, from_=1, to=999, textvariable=self.total_var, width=8)),
            ("随机种子", ttk.Entry(grid, textvariable=self.seed_var, width=18)),
        ]
        for i, (label, widget) in enumerate(rows):
            ttk.Label(grid, text=label).grid(row=i, column=0, sticky="w", pady=2)
            widget.grid(row=i, column=1, sticky="ew", pady=2)
        grid.columnconfigure(1, weight=1)
        self.pov_combo = grid.grid_slaves(row=1, column=1)[0]
        self.mode_combo = grid.grid_slaves(row=0, column=1)[0]
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_change)

        # jazz params
        self.custom_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(parent, text="使用自定义即兴参数", variable=self.custom_var).pack(anchor="w", pady=(8, 2))
        self.sliders: dict[str, tk.DoubleVar] = {}
        pframe = ttk.Frame(parent)
        pframe.pack(fill="x")
        for i, (key, label) in enumerate(JAZZ_KEYS):
            var = tk.DoubleVar(value=MODE_PRESETS["classic_jazz"][key])
            self.sliders[key] = var
            row = ttk.Frame(pframe)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=label, width=10).pack(side="left")
            val = ttk.Label(row, text=f"{var.get():.2f}", width=4)
            scale = ttk.Scale(row, from_=0.0, to=1.0, variable=var, orient="horizontal",
                              command=lambda _v, k=key: self._on_slider(k))
            scale.pack(side="left", fill="x", expand=True, padx=2)
            val.pack(side="left")
            setattr(self, f"_val_{key}", val)

        ttk.Separator(parent).pack(fill="x", pady=8)
        self.save_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(parent, text="保存到 output/chapters 并记录动机", variable=self.save_var).pack(anchor="w")

        btns = ttk.Frame(parent)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="▶ 演奏一章", command=self.on_play).pack(fill="x", pady=2)
        ttk.Button(btns, text="⇒ 生成全书（每行一章）", command=self.on_book).pack(fill="x", pady=2)
        ttk.Button(btns, text="≣ 多版本 · 探索路径", command=self.on_takes).pack(fill="x", pady=2)
        ttk.Button(btns, text="→ 下一章场景建议", command=self.on_plan).pack(fill="x", pady=2)
        ttk.Button(btns, text="状态 / 历史", command=self.on_status).pack(fill="x", pady=2)

    def _build_output(self, parent) -> None:
        self.nb = ttk.Notebook(parent)
        self.nb.pack(fill="both", expand=True)
        self.tabs: dict[str, tk.Text] = {}
        for name in ["正文", "即兴决策", "评价", "建议", "状态", "历史"]:
            frame = ttk.Frame(self.nb)
            txt = tk.Text(frame, wrap="word", state="disabled", padx=8, pady=6)
            sb = ttk.Scrollbar(frame, command=txt.yview)
            txt.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            txt.pack(side="left", fill="both", expand=True)
            self.nb.add(frame, text=name)
            self.tabs[name] = txt

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

    def _append_tab(self, name: str, text: str) -> None:
        widget = self.tabs[name]
        widget.configure(state="normal")
        widget.insert("end", text)
        widget.configure(state="disabled")

    def _on_mode_change(self, _event=None) -> None:
        preset = MODE_PRESETS.get(self.mode_var.get(), {})
        for key, var in self.sliders.items():
            if key in preset:
                var.set(preset[key])
                self._refresh_val_label(key)

    def _on_slider(self, key: str) -> None:
        self._refresh_val_label(key)

    def _refresh_val_label(self, key: str) -> None:
        getattr(self, f"_val_{key}").configure(text=f"{self.sliders[key].get():.2f}")

    def _overrides(self) -> dict:
        if not self.custom_var.get():
            return {}
        return {key: var.get() for key, var in self.sliders.items()}

    def _seed(self):
        raw = self.seed_var.get().strip()
        return int(raw) if raw else None

    # -- session ------------------------------------------------------------
    def _reload_session(self) -> None:
        try:
            self.session = Session.load(provider=self.provider_var.get(),
                                        eval_mode=self.eval_var.get())
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("加载失败", f"无法加载设定:\n{exc}")
            return
        names = list(self.session.characters.keys())
        self.pov_combo.configure(values=names)
        if names and self.pov_var.get() not in names:
            self.pov_var.set(names[0])
        self.loaded_var.set(f"已加载 {len(names)} 人物 · provider={self.session.provider_name}")
        self._set_tab("状态", self._status_text())

    def _status_text(self) -> str:
        s = self.session
        if s is None:
            return "(未加载)"
        lines = ["【主题】", s.theme.as_prompt(), "", "【叙事和声】", s.harmony.as_prompt(), "",
                 "【乐手】"]
        for c in s.characters.values():
            lines.append(f"  - {c.name}（{c.role}）欲望: {c.desire} / 恐惧: {c.fear}")
        lines += ["", "【动机】"]
        for m in s.motifs.all():
            lines.append(f"  - {m.name}: {m.count} 次  [{ ' → '.join(m.meanings) or '-' }]")
        lines += ["", "【故事状态】", s.story_state.summary()]
        return "\n".join(lines)

    # -- async runner -------------------------------------------------------
    def _async(self, work, done) -> None:
        self.status_var.set("演奏中…")
        self.root.configure(cursor="watch")

        def runner():
            try:
                result = work()
            except Exception as exc:  # noqa: BLE001
                result = exc
            self.root.after(0, lambda: self._finish(result, done))

        threading.Thread(target=runner, daemon=True).start()

    def _finish(self, result, done) -> None:
        self.root.configure(cursor="")
        if isinstance(result, Exception):
            self.status_var.set("出错")
            messagebox.showerror("出错", str(result))
            return
        self.status_var.set("就绪")
        done(result)

    # -- actions ------------------------------------------------------------
    def on_play(self) -> None:
        if self.session is None:
            return
        scene = self.scene_text.get("1.0", "end").strip()
        if not scene:
            messagebox.showwarning("缺少场景", "请先填写场景。")
            return
        pov = self.pov_var.get() or None
        kwargs = dict(
            scene=scene, pov=pov, style=self.style_var.get(),
            chapter=self.chapter_var.get(), total_chapters=self.total_var.get(),
            jazz_mode=self.mode_var.get(), seed=self._seed(),
            overrides=self._overrides(),
            previous_texts=self.session.recent_texts(5),
        )

        def work():
            take, eva = self.session.play(**kwargs)
            advice = self.session.advise(take, eva, pov=pov)
            skeletons = self.session.plan(take, eva, count=3)
            if self.save_var.get():
                save_take(take, eva, index=1)
                self.session.record_motifs(take)
                self.session.persist_motifs()
            return take, eva, advice, skeletons

        self._async(work, self._render_play)

    def _render_play(self, result) -> None:
        take, eva, advice, skeletons = result
        header = f"──────── 第 {take.chapter} 章 · {take.mode} · {take.style} · POV {take.pov} ────────\n"
        self._set_tab("正文", header + take.text)
        self._set_tab("即兴决策", self._cue_text(take))
        self._set_tab("评价", self._eval_text(eva))
        self._set_tab("建议", self._advice_text(advice) + "\n\n" + self._plan_text(skeletons))
        self.nb.select(0)

    def on_book(self) -> None:
        if self.session is None:
            return
        lines = [ln.strip() for ln in self.scene_text.get("1.0", "end").splitlines()]
        scenes = [ln for ln in lines if ln and not ln.startswith("#")]
        if not scenes:
            messagebox.showwarning("缺少场景", "请在场景框里每行写一章的场景。")
            return
        pov = self.pov_var.get() or None

        def work():
            return self.session.compose_book(
                scenes, pov=pov, style=self.style_var.get(),
                jazz_mode=self.mode_var.get(), seed=self._seed(),
                overrides=self._overrides(),
                target_chapters=self.total_var.get(),   # 全书章数为准
                save=self.save_var.get(),
            )

        self._async(work, self._render_book)

    def _render_book(self, results) -> None:
        body, cues, evals = [], [], []
        for i, take, eva in results:
            body.append(f"──────── 第 {i} 章 · {take.style} ────────\n{take.text}\n")
            cues.append(f"【第 {i} 章】\n{self._cue_text(take)}")
            evals.append(f"【第 {i} 章】\n{self._eval_text(eva)}")
        self._set_tab("正文", "\n".join(body))
        self._set_tab("即兴决策", "\n\n".join(cues))
        self._set_tab("评价", "\n\n".join(evals))
        self.nb.select(0)
        self.status_var.set(f"已生成 {len(results)} 章")

    def on_takes(self) -> None:
        if self.session is None:
            return
        scene = self.scene_text.get("1.0", "end").strip()
        if not scene:
            messagebox.showwarning("缺少场景", "请先填写场景。")
            return
        pov = self.pov_var.get() or None

        def work():
            return self.session.variations(
                scene, pov=pov, styles=DEFAULT_STYLES,
                chapter=self.chapter_var.get(), total_chapters=self.total_var.get(),
                jazz_mode=self.mode_var.get(), seed=self._seed(),
                overrides=self._overrides(), explore=True,
            )

        self._async(work, self._render_takes)

    def _render_takes(self, results) -> None:
        body, cues, evals = [], [], []
        for i, (take, eva) in enumerate(results, 1):
            body.append(f"──── Take {i} · {take.style} ────\n{take.text}\n")
            cues.append(self._cue_text(take))
            evals.append(f"【Take {i} · {take.style}】\n{self._eval_text(eva)}")
            if self.save_var.get():
                save_take(take, eva, index=i)
                self.session.record_motifs(take)
        if self.save_var.get():
            self.session.persist_motifs()
        self._set_tab("正文", "\n".join(body))
        self._set_tab("即兴决策", "\n\n".join(cues))
        self._set_tab("评价", "\n\n".join(evals))
        self.nb.select(0)

    def on_plan(self) -> None:
        if self.session is None:
            return
        self._async(lambda: self.session.plan(count=3), self._render_plan)

    def _render_plan(self, skeletons) -> None:
        self._set_tab("建议", self._plan_text(skeletons))
        self.nb.select(3)

    def on_status(self) -> None:
        if self.session is None:
            self._reload_session()
        self._set_tab("状态", self._status_text())
        self._set_tab("历史", self._history_text())
        self.nb.select(4)

    # -- formatters ---------------------------------------------------------
    @staticmethod
    def _cue_text(take) -> str:
        cue = take.cue or {}
        if not cue:
            return "(无 Cue)"
        js = cue.get("jazz_seed", {})
        rhythm = cue.get("rhythm", {})
        solo = cue.get("solo", {})
        lines = [f"模式: {cue.get('mode')}　种子: {cue.get('seed_int')}",
                 f"色彩: 情绪 {js.get('emotion','-')} / 视角 {js.get('perspective','-')} / 象征 {js.get('symbol','-')}",
                 f"节奏: {rhythm.get('name','-')}（{rhythm.get('pace','-')}）",
                 f"独奏: {solo.get('character','-')} · {solo.get('instrument','-')}"]
        for m in cue.get("motifs", []):
            lines.append(f"动机: {m.get('name')} → 第{m.get('stage')}次（{m.get('mode')}）")
        ops = (cue.get("operators", {}) or {}).get("operators", [])
        if ops:
            lines.append("叙事操作:")
            for op in ops:
                lines.append(f"  · [{op.get('name')}] {op.get('directive')}")
        sur = cue.get("surprises", [])
        if sur:
            for s in sur:
                lines.append(f"受控意外: [{s.get('category')}] {s.get('detail')}")
        else:
            lines.append("受控意外: 无")
        return "\n".join(lines)

    @staticmethod
    def _eval_text(eva) -> str:
        labels = {"theme": "主题", "character": "人物", "emotion": "情绪",
                  "motif": "动机", "novelty": "新鲜度", "harmony": "和声"}
        lines = [f"总分 {eva.overall:.0%}　评级 {eva.grade}"]
        for k, v in eva.metrics.items():
            bar = "█" * int(round(v * 10))
            lines.append(f"  {labels.get(k, k):<4} {v:5.0%} {bar}")
        if eva.signals:
            sl = {"non_obviousness": "非显然性", "implicit_expression": "隐含表达",
                  "narrative_increment": "叙事增量", "continuity": "连续性",
                  "repetition_risk": "重复风险"}
            lines.append("文学回听:")
            for k, v in eva.signals.items():
                lines.append(f"  {sl.get(k, k):<6} {v:.0%}")
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

    @staticmethod
    def _history_text() -> str:
        records = load_runs()
        if not records:
            return "(暂无运行记录，先演奏一次)"
        lines = ["章节  时间      种子  模式        风格      总分  评级"]
        for r in sorted(records, key=lambda x: x.get("created_at", "")):
            eva = r.get("evaluation", {})
            lines.append(
                f"{r.get('chapter','?'):>3}  {(r.get('created_at','') or '')[11:19]}  "
                f"{r.get('seed',''):>5}  {r.get('mode',''):<10} {r.get('style',''):<8} "
                f"{eva.get('overall',0):.0%}  {eva.get('grade','')}"
            )
        overalls = [r.get("evaluation", {}).get("overall", 0) for r in records]
        lines.append("")
        lines.append(f"共 {len(records)} 次演奏，平均总分 {sum(overalls)/len(overalls):.0%}")
        return "\n".join(lines)


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
