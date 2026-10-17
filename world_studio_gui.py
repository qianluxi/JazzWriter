"""World Studio GUI — an independent window for the worldview forge.

Semantics:
  发散  -> raise several structurally different prototypes from the seed
  选择并生长 -> pick one and grow it into a layered world, then render world.md
  嫁接  -> import an existing worldview file and transform it with an operator

Run:  python world_studio_gui.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from world.graft import OPS
from world.studio import WorldStudio

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except Exception as exc:  # pragma: no cover - GUI optional
    raise SystemExit(f"需要 Tkinter 才能运行图形界面：{exc}")


class WorldStudioApp:
    def __init__(self, root: "tk.Tk") -> None:
        self.root = root
        self.studio: Optional[WorldStudio] = None
        root.title("World Studio · 世界观工坊")
        root.geometry("1040x680")
        self._build()

    def _build(self) -> None:
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="灵感种子").pack(side="left")
        self.seed_var = tk.StringVar(
            value="每个人死后都会留下一段从未说出口的记忆，但只有建筑能听见"
        )
        ttk.Entry(top, textvariable=self.seed_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Label(top, text="模型").pack(side="left")
        self.provider_var = tk.StringVar(value="mock")
        ttk.Combobox(
            top, textvariable=self.provider_var, width=10,
            values=["mock", "opencode", "openai"], state="readonly",
        ).pack(side="left", padx=6)
        ttk.Button(top, text="发散", command=self.on_spark).pack(side="left")

        mid = ttk.Frame(self.root, padding=(8, 0))
        mid.pack(fill="both", expand=True)

        left = ttk.Frame(mid)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="世界原型（底层逻辑不同）").pack(anchor="w")
        self.ideas = tk.Listbox(left, width=38, height=24)
        self.ideas.pack(fill="y", expand=True)
        ttk.Button(left, text="选择并生长", command=self.on_grow).pack(fill="x", pady=4)

        graft_box = ttk.LabelFrame(left, text="设定嫁接", padding=6)
        graft_box.pack(fill="x", pady=6)
        self.op_var = tk.StringVar(value="深度变形")
        ttk.Combobox(
            graft_box, textvariable=self.op_var, values=list(OPS.keys()),
            state="readonly", width=16,
        ).pack(fill="x")
        ttk.Button(graft_box, text="导入设定文件并变形", command=self.on_graft).pack(fill="x", pady=4)

        right = ttk.Frame(mid)
        right.pack(side="left", fill="both", expand=True, padx=8)
        ttk.Label(right, text="世界设定（world.md）").pack(anchor="w")
        self.view = tk.Text(right, wrap="word")
        self.view.pack(fill="both", expand=True)
        btns = ttk.Frame(right)
        btns.pack(fill="x", pady=4)
        ttk.Button(btns, text="生成 / 刷新 Markdown", command=self.on_export).pack(side="left")
        ttk.Button(btns, text="另存为…", command=self.on_save_as).pack(side="left", padx=6)

        self.status = tk.StringVar(value="输入一句话，点『发散』开始。")
        ttk.Label(self.root, textvariable=self.status, relief="sunken", anchor="w").pack(
            fill="x", side="bottom"
        )

    # -- actions ------------------------------------------------------------
    def _new_studio(self) -> WorldStudio:
        seed = self.seed_var.get().strip()
        if not seed:
            raise ValueError("请先输入一句灵感种子")
        return WorldStudio.create(seed, provider=self.provider_var.get())

    def on_spark(self) -> None:
        try:
            self.studio = self._new_studio()
            self.studio.raise_ideas(count=4)
        except Exception as exc:
            messagebox.showerror("发散失败", str(exc))
            return
        self.ideas.delete(0, "end")
        for idea in self.studio.doc.ideas:
            self.ideas.insert("end", f"{idea.label}｜{idea.lens}｜差异度 {idea.distinctness}")
        self._render_ideas()
        self.status.set(f"已生成 {len(self.studio.doc.ideas)} 个原型，选一个继续生长。")

    def on_grow(self) -> None:
        if self.studio is None:
            messagebox.showinfo("提示", "请先『发散』。")
            return
        sel = self.ideas.curselection()
        if not sel:
            messagebox.showinfo("提示", "请先在左侧选择一个世界原型。")
            return
        try:
            self.studio.choose(str(sel[0] + 1))
            self.studio.grow()
            self.studio.export()
        except Exception as exc:
            messagebox.showerror("生长失败", str(exc))
            return
        self._show_markdown(self.studio.md_path)
        self.status.set(f"已生长并导出：{self.studio.md_path}")

    def on_graft(self) -> None:
        path = filedialog.askopenfilename(
            title="选择已有设定文档", filetypes=[("文本", "*.txt *.md"), ("所有文件", "*.*")]
        )
        if not path:
            return
        try:
            studio = self.studio or self._new_studio()
            studio.graft(Path(path).read_text(encoding="utf-8"),
                         self.op_var.get(), source_name=Path(path).name)
            studio.export()
            self.studio = studio
        except Exception as exc:
            messagebox.showerror("嫁接失败", str(exc))
            return
        self._show_markdown(studio.md_path)
        self.status.set(f"嫁接完成（{self.op_var.get()}）：{studio.md_path}")

    def on_export(self) -> None:
        if self.studio is None:
            messagebox.showinfo("提示", "请先『发散』。")
            return
        self.studio.export()
        self._show_markdown(self.studio.md_path)
        self.status.set(f"Markdown 已更新：{self.studio.md_path}")

    def on_save_as(self) -> None:
        text = self.view.get("1.0", "end").strip()
        if not text:
            return
        path = filedialog.asksaveasfilename(defaultextension=".md",
                                            filetypes=[("Markdown", "*.md")])
        if path:
            Path(path).write_text(text + "\n", encoding="utf-8")
            self.status.set(f"已另存为：{path}")

    # -- rendering ----------------------------------------------------------
    def _render_ideas(self) -> None:
        assert self.studio is not None
        lines = []
        for i, idea in enumerate(self.studio.doc.ideas, start=1):
            lines += [
                f"【{i}】{idea.label}｜{idea.lens}｜差异度 {idea.distinctness}",
                f"    一句话：{idea.logline}",
                f"    核心规则：{idea.core_rule}",
                "",
            ]
        self._set_view("\n".join(lines))

    def _show_markdown(self, path: Path) -> None:
        self._set_view(Path(path).read_text(encoding="utf-8"))

    def _set_view(self, text: str) -> None:
        self.view.configure(state="normal")
        self.view.delete("1.0", "end")
        self.view.insert("1.0", text)
        self.view.configure(state="disabled")


def main() -> int:
    root = tk.Tk()
    WorldStudioApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
