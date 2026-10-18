"""World Studio GUI — an independent window for the worldview forge.

Semantics:
  发散        -> raise structurally different prototypes from the seed (auto-saved)
  选择并生长   -> pick one, grow it into a layered world, export world.md
  打开        -> continue an existing local world (worlds/<slug>)
  条目状态/锁定 -> confirm, mark open/contradiction or lock an entry, saved at once
  嫁接        -> import an existing worldview file and transform it with an operator

Run:  python world_studio_gui.py
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from world.models import STATES
from world.graft import OPS
from world.idea_forge import DIMENSION_LABELS
from world.studio import WORLDS_DIR, WorldStudio

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except Exception as exc:  # pragma: no cover - GUI optional
    raise SystemExit(f"需要 Tkinter 才能运行图形界面：{exc}")

_STATE_LABELS = {
    "confirmed": "已确认", "candidate": "候选", "open": "未决", "contradiction": "矛盾",
}


class WorldStudioApp:
    def __init__(self, root: "tk.Tk") -> None:
        self.root = root
        self.studio: Optional[WorldStudio] = None
        root.title("World Studio · 世界观工坊")
        root.geometry("1120x720")
        self._build()

    # -- layout -------------------------------------------------------------
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
        ttk.Combobox(top, textvariable=self.provider_var, width=10,
                     values=["mock", "opencode", "openai"], state="readonly").pack(side="left", padx=6)
        ttk.Button(top, text="发散", command=self.on_spark).pack(side="left")

        bar = ttk.Frame(self.root, padding=(8, 0))
        bar.pack(fill="x")
        ttk.Label(bar, text="已有世界观").pack(side="left")
        self.open_var = tk.StringVar()
        self.open_box = ttk.Combobox(bar, textvariable=self.open_var, width=30, state="readonly")
        self.open_box.pack(side="left", padx=6)
        ttk.Button(bar, text="打开", command=self.on_open).pack(side="left")
        ttk.Button(bar, text="刷新列表", command=self.refresh_worlds).pack(side="left", padx=6)
        ttk.Button(bar, text="另存副本", command=self.on_save_copy).pack(side="left")
        self.where = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.where).pack(side="left", padx=10)

        mid = ttk.Frame(self.root, padding=(8, 6))
        mid.pack(fill="both", expand=True)

        left = ttk.Frame(mid)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="世界原型（底层逻辑不同，选中可看五维）").pack(anchor="w")
        self.ideas = tk.Listbox(left, width=40, height=11)
        self.ideas.pack(fill="x")
        self.ideas.bind("<<ListboxSelect>>", self.on_select_idea)
        ttk.Button(left, text="选择并生长", command=self.on_grow).pack(fill="x", pady=4)

        ttk.Label(left, text="设定条目（选中后改状态/锁定）").pack(anchor="w", pady=(6, 0))
        self.entities = tk.Listbox(left, width=40, height=10)
        self.entities.pack(fill="x")
        self.entities.bind("<<ListboxSelect>>", self.on_select_entity)
        st = ttk.Frame(left)
        st.pack(fill="x", pady=4)
        for state in STATES:
            ttk.Button(st, text=_STATE_LABELS[state], width=6,
                       command=lambda s=state: self.on_state(s)).pack(side="left")
        ttk.Button(left, text="锁定 / 解锁", command=self.on_lock).pack(fill="x")

        edit_box = ttk.LabelFrame(left, text="编辑选中条目（保留 id/来源/依赖）", padding=6)
        edit_box.pack(fill="x", pady=6)
        self.ed_name = tk.StringVar()
        self.ed_statement = tk.StringVar()
        self.ed_basis = tk.StringVar()
        for label, var in (("名称", self.ed_name), ("内容", self.ed_statement), ("依据", self.ed_basis)):
            row = ttk.Frame(edit_box)
            row.pack(fill="x")
            ttk.Label(row, text=label, width=5).pack(side="left")
            ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
        ttk.Button(edit_box, text="保存编辑", command=self.on_edit).pack(fill="x", pady=(4, 0))

        graft_box = ttk.LabelFrame(left, text="设定嫁接", padding=6)
        graft_box.pack(fill="x", pady=6)
        self.op_var = tk.StringVar(value="深度变形")
        ttk.Combobox(graft_box, textvariable=self.op_var, values=list(OPS.keys()),
                     state="readonly", width=16).pack(fill="x")
        ttk.Button(graft_box, text="导入设定文件并变形", command=self.on_graft).pack(fill="x", pady=4)

        right = ttk.Frame(mid)
        right.pack(side="left", fill="both", expand=True, padx=8)
        ttk.Label(right, text="世界设定（world.md）").pack(anchor="w")
        self.view = tk.Text(right, wrap="word")
        self.view.pack(fill="both", expand=True)
        btns = ttk.Frame(right)
        btns.pack(fill="x", pady=4)
        ttk.Button(btns, text="生成 / 刷新 Markdown", command=self.on_export).pack(side="left")
        ttk.Button(btns, text="一致性检查", command=self.on_check).pack(side="left", padx=6)

        self.status = tk.StringVar(value="输入一句话，点『发散』开始。")
        ttk.Label(self.root, textvariable=self.status, relief="sunken", anchor="w").pack(
            fill="x", side="bottom")
        self.refresh_worlds()

    # -- helpers ------------------------------------------------------------
    def _new_studio(self) -> WorldStudio:
        seed = self.seed_var.get().strip()
        if not seed:
            raise ValueError("请先输入一句灵感种子")
        return WorldStudio.create(seed, provider=self.provider_var.get())

    def refresh_worlds(self) -> None:
        slugs: List[str] = []
        if WORLDS_DIR.exists():
            slugs = sorted(p.name for p in WORLDS_DIR.iterdir() if (p / "world.json").exists())
        self.open_box["values"] = slugs
        if slugs and not self.open_var.get():
            self.open_var.set(slugs[0])

    def _refresh_entities(self) -> None:
        self.entities.delete(0, "end")
        if not self.studio:
            return
        for entity in self.studio.doc.entities:
            lock = " 🔒" if entity.locked else ""
            self.entities.insert("end", f"[{_STATE_LABELS.get(entity.state, entity.state)}] "
                                        f"{entity.kind}/{entity.id} {entity.name}{lock}")

    def _show_markdown(self, path: Path) -> None:
        self._set_view(Path(path).read_text(encoding="utf-8"))

    def _set_view(self, text: str) -> None:
        self.view.configure(state="normal")
        self.view.delete("1.0", "end")
        self.view.insert("1.0", text)
        self.view.configure(state="disabled")

    def _selected_entity(self) -> Optional[str]:
        sel = self.entities.curselection()
        if not sel or not self.studio:
            return None
        return self.studio.doc.entities[sel[0]].id

    # -- actions ------------------------------------------------------------
    def on_spark(self) -> None:
        try:
            self.studio = self._new_studio()
            self.studio.raise_ideas(count=4)
            self.studio.save()
        except Exception as exc:
            messagebox.showerror("发散失败", str(exc))
            return
        self._render_ideas()
        warnings = self.studio.duplicate_warnings()
        self.status.set(f"已生成并保存 {len(self.studio.doc.ideas)} 个原型"
                        + (f"；⚠ {len(warnings)} 个机制重复" if warnings else ""))
        self.where.set(f"当前：{self.studio.slug}")
        self._refresh_entities()
        self.refresh_worlds()

    def on_open(self) -> None:
        slug = self.open_var.get()
        if not slug:
            messagebox.showinfo("提示", "没有可打开的世界观。")
            return
        try:
            self.studio = WorldStudio.load(slug, provider=self.provider_var.get())
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc))
            return
        self.seed_var.set(self.studio.doc.seed)
        self._render_ideas()
        self._refresh_entities()
        chosen = self.studio.doc.chosen_idea
        if self.studio.md_path.exists():
            self._show_markdown(self.studio.md_path)
        else:
            self._set_view("（该世界观尚未生长；选择上方原型后点「选择并生长」。）")
        self.where.set(f"当前：{self.studio.slug}")
        self.status.set(f"已打开：{self.studio.slug}"
                        + (f"（已选原型：{chosen.label}）" if chosen else "（尚未选择原型）"))

    def on_grow(self) -> None:
        if self.studio is None:
            messagebox.showinfo("提示", "请先『发散』或『打开』。")
            return
        sel = self.ideas.curselection()
        if not sel:
            messagebox.showinfo("提示", "请先在左侧选择一个世界原型。")
            return
        try:
            idea = self.studio.doc.ideas[sel[0]]
            self.studio.choose(idea.id)
            self.studio.grow()
            self.studio.export()
        except Exception as exc:
            messagebox.showerror("生长失败", str(exc))
            return
        self._show_markdown(self.studio.md_path)
        self._refresh_entities()
        self.status.set(f"已生长并导出：{self.studio.md_path}")

    def on_state(self, state: str) -> None:
        entity_id = self._selected_entity()
        if not self.studio or not entity_id:
            messagebox.showinfo("提示", "请先在条目列表选择一个条目。")
            return
        self.studio.set_state(entity_id, state)
        self.studio.export()
        self._refresh_entities()
        self._show_markdown(self.studio.md_path)
        self.status.set(f"{entity_id} → {_STATE_LABELS[state]}")

    def on_lock(self) -> None:
        entity_id = self._selected_entity()
        if not self.studio or not entity_id:
            messagebox.showinfo("提示", "请先在条目列表选择一个条目。")
            return
        entity = self.studio.doc.by_id(entity_id)
        self.studio.lock(entity_id, not (entity.locked if entity else False))
        self.studio.export()
        self._refresh_entities()
        self._show_markdown(self.studio.md_path)
        self.status.set(f"{entity_id} 锁定状态已切换")

    def on_select_idea(self, _event=None) -> None:
        sel = self.ideas.curselection()
        if not sel or not self.studio:
            return
        idea = self.studio.doc.ideas[sel[0]]
        lines = [f"{idea.label}（{idea.lens}）　差异度 {idea.distinctness}",
                 f"一句话：{idea.logline}",
                 f"核心规则：{idea.core_rule}",
                 "", "五维（世界机制的五个维度）："]
        for key, label in DIMENSION_LABELS.items():
            value = idea.dimensions.get(key, "")
            if value:
                lines.append(f"· {label}：{value}")
        lines += ["", "（点「选择并生长」按这个原型展开世界）"]
        self._set_view("\n".join(lines))

    def on_select_entity(self, _event=None) -> None:
        entity_id = self._selected_entity()
        if not self.studio or not entity_id:
            return
        entity = self.studio.doc.by_id(entity_id)
        self.ed_name.set(entity.name)
        self.ed_statement.set(entity.statement)
        self.ed_basis.set(entity.basis)

    def on_edit(self) -> None:
        entity_id = self._selected_entity()
        if not self.studio or not entity_id:
            messagebox.showinfo("提示", "请先在条目列表选择一个条目。")
            return
        entity = self.studio.doc.by_id(entity_id)
        needs_confirm = entity.locked or entity.state == "confirmed"
        if needs_confirm and not messagebox.askyesno(
                "确认修改", f"「{entity.name}」已锁定或已确认，确定要修改吗？"):
            return
        try:
            result = self.studio.edit(
                entity_id, name=self.ed_name.get(), statement=self.ed_statement.get(),
                basis=self.ed_basis.get(), confirm=True)
            self.studio.export()
        except Exception as exc:
            messagebox.showerror("编辑失败", str(exc))
            return
        self._refresh_entities()
        self._show_markdown(self.studio.md_path)
        if result.get("reverify"):
            messagebox.showinfo(
                "核心规则已修改",
                "以下候选条目需要复核：\n\n" + "\n".join(result["reverify"]))
        self.status.set(f"已保存 {entity_id} 的编辑"
                        + (f"；{len(result.get('affected', []))} 条受影响设定需复核"
                           if result.get("affected") else ""))

    def on_graft(self) -> None:
        op = self.op_var.get()
        path = filedialog.askopenfilename(
            title="选择已有设定文档", filetypes=[("文本", "*.txt *.md"), ("所有文件", "*.*")])
        if not path:
            return
        second_text = None
        if op == "世界交叉":
            second_path = filedialog.askopenfilename(
                title="世界交叉：选择第二份设定文档",
                filetypes=[("文本", "*.txt *.md"), ("所有文件", "*.*")])
            if not second_path:
                messagebox.showinfo("提示", "「世界交叉」需要第二份材料，已取消。")
                return
            second_text = Path(second_path).read_text(encoding="utf-8")
        try:
            studio = WorldStudio.graft_new(
                self.seed_var.get().strip() or Path(path).stem,
                Path(path).read_text(encoding="utf-8"),
                op, source_name=Path(path).name, second_text=second_text,
                provider=self.provider_var.get())
            studio.export()
            self.studio = studio
        except Exception as exc:
            messagebox.showerror("嫁接失败", str(exc))
            return
        self.seed_var.set(studio.doc.seed)
        self._render_ideas()
        self._show_markdown(studio.md_path)
        self._refresh_entities()
        self.refresh_worlds()
        self.where.set(f"当前：{studio.slug}")
        self.status.set(f"已派生新世界（{op}，源世界未改动）：{studio.md_path}")

    def _render_ideas(self) -> None:
        self.ideas.delete(0, "end")
        if not self.studio:
            return
        for idea in self.studio.doc.ideas:
            dup = " ⚠重复" if idea.near_duplicate else ""
            self.ideas.insert("end", f"{idea.label}｜{idea.lens}｜差异度 {idea.distinctness}{dup}")
        chosen = self.studio.doc.chosen_idea
        if chosen:
            self.ideas.selection_clear(0, "end")
            for i, idea in enumerate(self.studio.doc.ideas):
                if idea.id == chosen.id:
                    self.ideas.selection_set(i)
                    self.ideas.see(i)
                    break

    def on_check(self) -> None:
        if self.studio is None:
            messagebox.showinfo("提示", "请先『发散』或『打开』。")
            return
        issues = self.studio.check()
        if not issues:
            self.status.set("未发现需要提示的冲突。")
            return
        lines = [f"{'⚠' if i['level'] == 'warn' else '·'} {i['message']}"
                 f"（依据：{i.get('basis')}；把握：{i.get('confidence')}）" for i in issues]
        self._set_view("\n".join(lines))
        self.status.set(f"一致性提示 {len(issues)} 条（只提示，不修改）")

    def on_export(self) -> None:
        if self.studio is None:
            messagebox.showinfo("提示", "请先『发散』或『打开』。")
            return
        self.studio.export()
        self._show_markdown(self.studio.md_path)
        self.status.set(f"Markdown 已更新：{self.studio.md_path}")

    def on_save_copy(self) -> None:
        if self.studio is None:
            messagebox.showinfo("提示", "请先『发散』或『打开』。")
            return
        path = filedialog.asksaveasfilename(defaultextension=".md",
                                            filetypes=[("Markdown", "*.md")])
        if path:
            self.studio.export()
            Path(path).write_text(self.studio.md_path.read_text(encoding="utf-8"),
                                  encoding="utf-8")
            self.status.set(f"已另存副本：{path}")


def main() -> int:
    root = tk.Tk()
    WorldStudioApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
