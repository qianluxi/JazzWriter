"""Generate the JazzWriter beginner's guide as a Word (.docx) document.

Run::

    python tools/make_manual.py

Output: ``docs/JazzWriter_新手引导.docx``
"""

from __future__ import annotations

import os
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "JazzWriter_新手引导.docx"
CJK = "微软雅黑"


def _cjk(font, name: str = CJK) -> None:
    font.name = name
    rpr = font._element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:eastAsia"), name)


def _setup(doc: Document) -> None:
    for style_name in ("Normal", "Title", "Heading 1", "Heading 2", "Heading 3",
                       "List Bullet", "List Number"):
        try:
            _cjk(doc.styles[style_name].font)
        except KeyError:
            pass
    doc.styles["Normal"].font.size = Pt(10.5)
    for name, size, color in (("Heading 1", 16, "1F4E79"), ("Heading 2", 13, "2E75B6"),
                              ("Heading 3", 11.5, "404040")):
        try:
            st = doc.styles[name].font
            st.size = Pt(size)
            st.color.rgb = RGBColor.from_string(color)
        except KeyError:
            pass


def h1(doc, text):
    doc.add_heading(text, level=1)


def h2(doc, text):
    doc.add_heading(text, level=2)


def h3(doc, text):
    doc.add_heading(text, level=3)


def p(doc, text, bold=False):
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.bold = bold
    return para


def bullets(doc, items):
    for it in items:
        doc.add_paragraph(it, style="List Bullet")


def numbers(doc, items):
    for it in items:
        doc.add_paragraph(it, style="List Number")


def table(doc, headers, rows):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    for i, htext in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = htext
        for run in cell.paragraphs[0].runs:
            run.bold = True
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = str(val)
    doc.add_paragraph()
    return t


def build() -> Document:
    doc = Document()
    _setup(doc)

    # -- cover --------------------------------------------------------------
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    trun = title.add_run("JazzWriter 新手引导")
    trun.bold = True
    trun.font.size = Pt(28)
    _cjk(trun.font)
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    srun = sub.add_run("长篇小说结构即兴引擎 · 从零开始的完整操作手册")
    srun.font.size = Pt(13)
    srun.font.color.rgb = RGBColor.from_string("666666")
    _cjk(srun.font)
    ver = doc.add_paragraph()
    ver.alignment = WD_ALIGN_PARAGRAPH.CENTER
    vrun = ver.add_run("适用版本 v2.5　·　Novel Jazz Engine")
    vrun.font.size = Pt(11)
    vrun.font.color.rgb = RGBColor.from_string("999999")
    _cjk(vrun.font)
    doc.add_paragraph()

    # -- TOC ----------------------------------------------------------------
    h1(doc, "目录")
    bullets(doc, [
        "一、这是什么（60 秒了解）",
        "二、安装与启动",
        "三、5 分钟快速上手",
        "四、界面速览",
        "五、核心概念：乐谱与结构",
        "六、结构工作流详解",
        "七、局部演练：正文 / 多版本 / Jam",
        "八、接入真实模型",
        "九、命令行速查",
        "十、常见问题（FAQ）",
        "十一、文件与目录说明",
        "十二、术语表",
    ])

    # -- 1 ----------------------------------------------------------------
    h1(doc, "一、这是什么（60 秒了解）")
    p(doc, "JazzWriter 不是“一键生成整本小说”的工具，而是一个帮你探索故事的“即兴引擎”。"
           "它的主要产物是：故事方案、全书梗概、分卷结构与逐章摘要卡片。正文生成是可选的“局部演练”。")
    p(doc, "工作循环可以记成一句话：", bold=True)
    p(doc, "给定一个前提 → 发散出多个实质不同的故事方向 → 采纳或融合 → 生成完整结构（分卷+逐章卡片）"
           "→ 校验 → 局部重新即兴 → 导出。最后由你来判断与选择。")
    p(doc, "它适合：长篇小说/网文/系列的作者、需要管理世界观与伏笔的写作者、想先想清楚“故事怎么成立”的人。")

    # -- 2 ----------------------------------------------------------------
    h1(doc, "二、安装与启动")
    p(doc, "1）安装依赖（在项目根目录执行）：")
    p(doc, "pip install -r requirements.txt")
    p(doc, "2）启动图形界面（推荐给新用户）：")
    p(doc, "python gui.py")
    p(doc, "或者直接双击根目录的 JazzWriter.bat。")
    p(doc, "3）也可以用命令行（CLI）：")
    p(doc, "python main.py --help")
    p(doc, "说明：默认使用离线 mock 模型，无需任何 API Key 即可跑通流程（但内容偏模板化）。"
           "接入真实模型见第八章。")

    # -- 3 ----------------------------------------------------------------
    h1(doc, "三、5 分钟快速上手")
    p(doc, "打开 GUI 后，按下面 6 步操作即可得到一套完整的故事结构。")

    h2(doc, "第 1 步：填写故事前提")
    p(doc, "在左侧“场景 / 章节摘要”框里写一句故事前提，例如：")
    p(doc, "一场技术事故改变了一个家庭。")
    p(doc, "并设置：即兴模式（classic_jazz / bebop / free_jazz）、全书章数、结构模板（如 mystery 悬疑）。")

    h2(doc, "第 2 步：生成创意方案")
    p(doc, "点「生成创意方案」→ 右侧「创意候选」标签页会出现多个方向。"
           "每个方向在“因果机制 / 真相性质 / 人物关系 / 结局方向”上实质不同。")

    h2(doc, "第 3 步：采纳或融合")
    p(doc, "在“采纳方案#”里选一个编号；也可以点「融合所选两个方案」把两个方向合并成一个新方向。"
           "然后点「采纳并展开全书结构」。")

    h2(doc, "第 4 步：查看与校验结构")
    p(doc, "右侧「全书结构 / 结构树 / 章节卡片」展示分卷与逐章摘要。"
           "点「校验结构」查看问题清单（硬问题 + 叙事审阅），问题优先于分数。")

    h2(doc, "第 5 步：编辑、锁定与局部重新即兴")
    p(doc, "在「结构树」选中某一章 →「章节卡片」可直接编辑 →点「保存章节卡片编辑」。"
           "认可的情节可「锁定」（整章锁定或字段级锁定）；"
           "想改某章时点「重新即兴选中章」：系统先给出候选，你采纳后才写回，未选中的章节与锁定内容不受影响。")

    h2(doc, "第 6 步：导出")
    p(doc, "点「导出结构 Markdown」得到结构文件；点「导出故事板（md/html）」得到可视化故事板"
           "（动机时间线 / 人物弧线 / 伏笔面板 / 偏离检测）。")

    # -- 4 ----------------------------------------------------------------
    h1(doc, "四、界面速览")
    table(doc, ["区域 / 按钮", "作用"], [
        ["左侧 场景框", "写故事前提；正文演练时每行一章"],
        ["即兴模式 / 视角 / Solo 色彩", "控制发散与文风"],
        ["结构模板", "线性因果 / 悬疑 / 多视角 / 群像 / 非线性拼图 / 自定义"],
        ["全书章数 / 采纳方案#", "期望章数与采纳的候选编号"],
        ["结构参数 / 文本参数", "控制创意发散、延迟揭露、连续性等"],
        ["① 结构即兴", "生成创意 / 融合 / 采纳展开 / 校验 / 卡片编辑 / 重新即兴 / 导出 / 偏离检测 / 故事板"],
        ["② 局部演练", "按结构渲染正文 / 试写一章 / 多版本探索 / 场景建议 / Jam Session"],
        ["创意候选", "多个故事方向"],
        ["全书结构", "梗概 + 分卷"],
        ["结构树 / 章节卡片", "逐章浏览与编辑"],
        ["Jam", "四角色合奏产出的场景提案"],
        ["评价", "结构校验 + 叙事审阅 + 参考分数（问题优先）"],
        ["历史", "每次运行的记录与趋势"],
    ])

    # -- 5 ----------------------------------------------------------------
    h1(doc, "五、核心概念：乐谱与结构")
    p(doc, "把设定想成爵士乐队的“乐谱”，AI 是与你合奏的乐手。", bold=True)
    h2(doc, "乐谱（data/ 目录）")
    table(doc, ["文件", "内容"], [
        ["story.yaml", "主题命题、世界硬约束/禁忌、情绪曲线、即兴参数"],
        ["characters.yaml", "人物（欲望/恐惧/记忆/世界观/矛盾/语感/即兴规则/人物弧）"],
        ["motifs.yaml", "核心意象定义"],
        ["story_state.yaml", "故事圣经：已确定事实 / 怀疑 / 秘密 / 未决线索 / 近期事件"],
    ])
    h2(doc, "结构三层")
    bullets(doc, [
        "BookPlan（全书）：梗概、命题、冲突、关键转折、结局、分卷",
        "VolumePlan（分卷）：本卷目标、开端、高潮、阶段结果",
        "ChapterPlan（章节卡片）：功能、POV、起因、行动、冲突、结果、信息变化、人物变化、线索、意象、前后钩子",
    ])
    h2(doc, "硬约束 vs 软约束")
    bullets(doc, [
        "硬约束（不可违反）：世界规则、禁忌、已确定事实、人物认知、未决线索的揭露时机",
        "软约束（可变化）：描述方式、场景顺序、对话风格、语言距离",
    ])

    # -- 6 ----------------------------------------------------------------
    h1(doc, "六、结构工作流详解")
    numbers(doc, [
        "输入前提，设定模式/模板/章数。",
        "生成创意方案（故事级发散）。",
        "比较方案（因果机制/真相/关系/结局/差异度），可融合，也可标记过期（前提改了会提示）。",
        "采纳并展开：生成全书梗概（开端/触发事件/关键转折/高潮/结局处理）与逐章卡片。",
        "校验：结构硬校验（缺章、编号、断链、未回收线索）+ 叙事审阅（含依据与章号）。",
        "编辑与锁定：卡片可编辑；可整章锁定或字段级锁定。",
        "局部重新即兴：先出候选并显示“改动字段”，采纳后才写回；未选中章节与锁定内容保持。",
        "导出：结构（Markdown）与故事板（Markdown/HTML）。",
    ])

    # -- 7 ----------------------------------------------------------------
    h1(doc, "七、局部演练：正文 / 多版本 / Jam")
    h2(doc, "按结构渲染正文")
    p(doc, "用已生成的章节摘要作为场景，顺序写成正文（可选）。按钮：「按结构渲染正文」。")
    h2(doc, "试写与多版本")
    bullets(doc, [
        "「演奏一章（试写）」：局部即兴一段正文，含“即兴决策 Cue”“评价”。",
        "「多版本 · 探索路径」：同一主题多次独立即兴，得到不同叙事路径。",
    ])
    h2(doc, "Jam Session")
    p(doc, "点「Jam Session（导演/独奏/观察/编辑）」：四个角色分工协作，"
           "Editor 会对候选打分排序、剔除与已知事实冲突者，整合成一个场景提案（不自动升级为正式设定）。")

    # -- 8 ----------------------------------------------------------------
    h1(doc, "八、接入真实模型")
    p(doc, "默认 mock 只用于离线演示。要获得真正的创意与文笔，请接入真实模型（二者兼容）。")
    h2(doc, "方式一：opencode（复用你已连接的模型）")
    numbers(doc, [
        "另开一个终端启动服务器：opencode serve --port 4096",
        "在 JazzWriter 顶部把“模型”下拉选 opencode，点“重载设定”。",
        "可选环境变量：NJE_OPENCODE_URL（默认 http://127.0.0.1:4096）、NJE_OPENCODE_MODEL（如 anthropic/claude-…）。",
    ])
    h2(doc, "方式二：OpenAI 兼容端点（OpenAI / DeepSeek / Qwen…）")
    p(doc, "在启动 GUI 之前设置环境变量：")
    p(doc, 'pip install openai')
    p(doc, '$env:OPENAI_API_KEY = "你的key"')
    p(doc, '$env:NJE_BASE_URL = "https://api.deepseek.com/v1"')
    p(doc, '$env:NJE_MODEL = "deepseek-chat"')
    p(doc, "然后顶部“模型”选 openai，点“重载设定”。")
    p(doc, "提示：结构生成在离线（mock）下使用确定性模板，会被明确标记为 offline_template；"
           "只有接入模型时才是模型创作。")

    # -- 9 ----------------------------------------------------------------
    h1(doc, "九、命令行速查")
    table(doc, ["命令", "作用"], [
        ["python main.py status", "查看主题/人物/和声/动机/故事状态"],
        ["python main.py outline \"前提\" --branches 3", "发散故事方案"],
        ["python main.py outline \"前提\" --build --pick 2 --chapters 12 --template mystery", "采纳并展开结构"],
        ["python main.py outline \"前提\" --fuse 1 2", "融合两个方案"],
        ["python main.py outline --validate", "结构校验"],
        ["python main.py outline --lock 3", "锁定第 3 章"],
        ["python main.py outline --lock-field 3 conflict", "锁定第 3 章 conflict 字段"],
        ["python main.py outline --reimprovise 5", "生成第 5 章候选（不覆盖）"],
        ["python main.py outline --reimprovise 5 --adopt 1 --regen all", "采纳候选并重生成后续"],
        ["python main.py outline --export", "导出结构 Markdown"],
        ["python main.py book --from-plan", "按结构渲染正文"],
        ["python main.py jam \"场景\" --pov 林 --render", "Jam 合奏并渲染"],
        ["python main.py report --open", "偏离检测 + 导出故事板并打开"],
        ["python main.py history", "运行历史与趋势"],
        ["python main.py advice --apply", "应用参数建议"],
        ["python main.py init", "写入示例乐谱"],
    ])

    # -- 10 ---------------------------------------------------------------
    h1(doc, "十、常见问题（FAQ）")
    qa = [
        ("生成的内容很模板化？",
         "那是在用离线 mock。请接入真实模型（opencode 或 openai），结构创意与文笔主要依赖模型。"),
        ("需要联网 / API Key 吗？",
         "离线 mock 不需要；真实模型需要。"),
        ("我的修改会被覆盖吗？",
         "不会。锁定的章节与字段不会被改写；“重新即兴”先给候选，采纳后才写回。"),
        ("如何得到小说正文？",
         "先有结构，再用「按结构渲染正文」或 python main.py book --from-plan。"),
        ("能复现同一次结果吗？",
         "固定“随机种子 seed”可复现即兴决策；正文由模型采样，可能略有差异。"),
        ("支持多少章？",
         "结构模式可到几十上百章；耗时与质量取决于模型。"),
        ("支持哪些模型？",
         "opencode（复用已连接模型）与任意 OpenAI 兼容端点。"),
        ("中文乱码？",
         "GUI 无此问题；命令行若乱码是终端编码，改用 Windows Terminal 或设置 UTF-8。"),
        ("结构生成失败/章数不对？",
         "分阶段生成会严格校验章数；不满足则自动回退并标记为离线模板，不会静默接受。"),
    ]
    for q, a in qa:
        p(doc, "问：" + q, bold=True)
        p(doc, "答：" + a)

    # -- 11 ---------------------------------------------------------------
    h1(doc, "十一、文件与目录说明")
    table(doc, ["路径", "说明"], [
        ["data/", "乐谱：主题、人物、意象、故事状态（可编辑）"],
        ["output/chapters/", "生成的章节正文（.md / .json）"],
        ["output/runs/", "每次运行的完整记录（cue/prompt/评价）"],
        ["output/book_plan.json", "当前全书结构（自动保存）"],
        ["output/book_outline.md", "结构导出"],
        ["output/story_report.md / .html", "故事板导出"],
        ["data/motif_state.yaml / jazz_state.yaml", "运行时状态（本地，不入库）"],
    ])

    # -- 12 ---------------------------------------------------------------
    h1(doc, "十二、术语表")
    table(doc, ["术语", "含义"], [
        ["Theme 主题", "全书核心命题，只被暗示、不直说"],
        ["Harmony 和声", "世界规则、禁忌、情绪曲线等约束"],
        ["Motif 动机", "反复出现且意义不断变化的意象"],
        ["Cue 乐谱", "某一轮即兴的决策（色彩/操作/意外/节奏）"],
        ["Take", "一次生成的文本版本"],
        ["BookPlan / VolumePlan / ChapterPlan", "全书 / 分卷 / 章节卡片三层结构"],
        ["ImprovisationOperator", "注意力转移、信息错位、因果重审等叙事操作"],
        ["Jam Session", "导演→独奏→观察→编辑 顺序合奏"],
        ["offline_template", "离线模板生成的内容（非模型创作）"],
    ])

    return doc


def main() -> int:
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT))
    print(f"written: {OUT}  ({len(doc.paragraphs)} paragraphs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
