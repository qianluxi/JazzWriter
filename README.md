# JazzWriter（小说爵士引擎）`v2.11`

> **长篇小说结构即兴引擎 / Human-AI Improvisational Writing System。**
> 主要产物不是小说正文，而是**故事方案、全书梗概、分卷结构、逐章摘要卡片，以及人物与关系网络**。
>
> 作者提供主题与世界 → AI 提供即兴变化 → 作者挑选与打磨 → 系统维持长期一致性。
> 更接近爵士合奏与即兴戏剧，而不是"AI 自动写小说"。

---

## 目录
- [工作流（结构优先）](#工作流结构优先)
- [安装与启动](#安装与启动)
- [快速上手（CLI）](#快速上手cli)
- [图形界面](#图形界面)
- [命令速查](#命令速查)
- [核心概念：乐谱 · 结构 · 人物关系](#核心概念乐谱--结构--人物关系)
- [受控偏移（即兴层）](#受控偏移即兴层)
- [结构即兴引擎](#结构即兴引擎)
- [记忆 · 偏离检测 · 可视化](#记忆--偏离检测--可视化)
- [Jam Session 合奏](#jam-session-合奏)
- [接入真实模型](#接入真实模型)
- [数据文件（乐谱）](#数据文件乐谱)
- [架构](#架构)
- [设计原则](#设计原则)
- [测试](#测试)
- [版本历史](#版本历史)

---

## 工作流（结构优先）

1. **输入故事前提**
2. **生成并比较多个创意方案**（在「因果机制 / 信息结构·真相 / 人物关系 / 结局 / 主题解释」上实质不同）
3. **选择或融合**方案
4. **生成完整故事梗概与分卷规划**（synopsis / 开端 / 触发事件 / 关键转折 / 高潮 / 结局处理）
5. **展开、编辑、锁定**章节摘要卡片（支持字段级锁定）
6. **校验全书**（结构硬校验 + 叙事审阅，**问题优先于分数**）
7. **按需局部重新即兴**（先出候选，作者采纳后才写回；锁定内容不被覆盖）
8. **最后才进入可选的正文试写**

> ⚠️ **mock 与真实模型**：默认 `mock` 是**离线演示**，只用于验证流程（章节卡片明显模板化）。
> 结构与正文质量主要依赖真实模型：`--provider opencode`（复用你已连接的模型）或 `--provider openai`。
> 离线生成的结构会被明确标记为 `offline_template`，不会伪装成模型创作。

---

## 安装与启动

```powershell
pip install -r requirements.txt
python main.py --help          # 命令行
python gui.py                  # 图形界面（或双击 JazzWriter.bat）
```

无需任何 API Key 即可跑通流程（内置离线 `mock`）。仅 GUI 使用标准库 Tkinter，无需额外安装。

---

## 快速上手（CLI）

```powershell
# 1) 从一个前提发散出若干「实质不同」的故事方案（五维对照）
python main.py outline "一场技术事故改变了一个家庭" --branches 3 --seed 1

# 2) 采纳某个方案，展开全书结构（分卷 + 逐章摘要卡片）
python main.py outline "一场技术事故改变了一个家庭" --build --pick 2 --chapters 12 --template mystery

# 3) 融合两个方案（并显示每个维度取自 A 还是 B）
python main.py outline "一场技术事故改变了一个家庭" --fuse 1 2

# 4) 校验 / 锁定 / 重新即兴（候选 → 采纳）/ 导出
python main.py outline --validate
python main.py outline --lock 3
python main.py outline --lock-field 3 conflict
python main.py outline --reimprovise 5                 # 生成候选（不覆盖）
python main.py outline --reimprovise 5 --adopt 1 --regen all   # 采纳并重生成后续
python main.py outline --export            # → output/book_outline.md

# 5) 编辑章节卡片（简表字段 / 完整 JSON）
python main.py outline --edit 3 --file card.txt
python main.py outline --edit-json 3 --file card.json

# 6) 按结构渲染正文（可选局部演练）
python main.py book --from-plan --pov 林 --no-save
```

结构模板：`linear_causality | mystery | multi_pov | ensemble | nonlinear_puzzle | custom`
结构参数：`--idea-divergence --causal-variation --character-agency --motif-transformation --revelation-delay --branch-count --continuity-strength`

---

## 图形界面

`python gui.py`（或双击 `JazzWriter.bat`）。顶部选「模型」（mock/opencode/openai）与「评价」（lexical/embedding/hybrid）。

- **左侧**：场景/章节摘要框；模式、视角、结构模板、章数、采纳/融合编号；结构参数与文本参数。
- **① 结构即兴**：生成创意 → 融合所选两个方案 / 采纳并展开 → 校验 / 保存卡片编辑 / 保存 JSON / **编辑人物·关系变化（表单）** / 重新即兴（可选范围） / 锁定 / 导出结构 / 偏离检测 / 导出故事板。
- **② 局部演练**：按结构渲染正文 / 试写一章 / 多版本探索 / 下一章场景建议 / Jam Session。
- **右侧标签**：创意候选 · 全书结构 · 结构树 · 章节卡片 · 卡片JSON · 人物 · Jam · 正文 · 即兴决策 · 评价 · 建议 · 状态 · 历史。

所有生成都在**主线程先快照参数、后台线程执行、期间按钮禁用**（`SingleFlight`），避免并发冲突。

---

## 命令速查

| 命令 | 作用 |
| --- | --- |
| `status` | 查看主题 / 人物 / 和声 / 动机 / 故事状态 |
| `chars` | 人物库、使用情况、关系网络与关系变化 |
| `outline "前提" --branches 3` | 发散故事方案（五维对照） |
| `outline … --build --pick N --chapters M --template T` | 采纳并展开全书结构 |
| `outline … --fuse A B` | 融合两个方案（对照取自 A/B） |
| `outline --validate` / `--lock N` / `--lock-field N FIELD` | 校验 / 锁定章 / 锁定字段 |
| `outline --reimprovise N [--adopt K] [--regen …]` | 候选 → 采纳 → 范围重生成 |
| `outline --edit N --file card.txt` / `--edit-json N --file card.json` | 编辑章节卡片 |
| `outline --export` | 导出结构 Markdown |
| `book --from-plan` / `book "场景1" "场景2" …` | 按结构渲染 / 逐章试写（不再循环复用场景） |
| `play …` / `takes … [--explore]` | 单章即兴 / 多版本（同和声或独立路径） |
| `jam "场景" [--rounds N] [--render]` | 四角色合奏（多轮辩论），可渲染正文 |
| `plan [--count N]` | 下一章场景骨架（有模型时由模型生成） |
| `report [--open]` | 偏离检测 + 导出**交互式**故事板并打开 |
| `memory [--rebuild] [--query "…"]` | 向量记忆：重建 / 语义检索章节 |
| `history [--chapter N] [--metric M] [--limit K]` | 运行历史与趋势 |
| `advice [--apply]` | 查看 / 应用下一轮参数建议 |
| `evaluate <file> [--eval-mode …]` | 评价已保存章节 |
| `motifs` / `jazz` / `styles` / `init` | 动机 / 乐谱参数 / 模式与色彩 / 写入示例乐谱 |

管道传入场景：`"雨夜。档案馆停电。" | python main.py play --pov 苏`

---

## 核心概念：乐谱 · 结构 · 人物关系

把设定想成乐队的"乐谱"，AI 是与你合奏的乐手。

| 爵士 | 本系统 |
| --- | --- |
| Head / Theme 主题旋律 | `Theme` 核心命题、情绪、象征 |
| Chord changes 和声 | `Harmony` 世界硬约束、禁忌、情绪进行 |
| Soloist 独奏者 | `Character` 欲望/恐惧/盲点/秘密/能力/限制/当前目标 |
| Motif 动机 | `Motif` 反复出现但意义演变 |
| Comping / 转调 | `ImprovisationScore` 受控偏移（随机、意外、节奏、独奏） |
| Take 录音 | 一次生成的多版本章节 |
| Listen-back 回听 | `Evaluator` + `feedback/Conductor` 评价并重调乐谱 |

**结构三层**：`BookPlan`（全书梗概/命题/冲突/转折/结局/分卷）→ `VolumePlan`（分卷目标/高潮/阶段结果）→ `ChapterPlan`（功能/POV/起因/行动/冲突/结果/信息变化/人物变化/线索/意象/前后钩子 + 人物参与）。

**人物与关系**（示例给了 5 人：3 核心 + 2 重要配角）：
- `Character` 有稳定 `id`、`tier`（core/supporting/functional）、`pov`（能否作视角），以及叙事驱动字段 `blind_spots / secrets / capabilities / constraints / current_goal`。
- `relationships.yaml` 定义关系网络：`mutual_interest / conflict / asymmetry / initial_state / pressure_point / possible_transition`。
- 每章记录：`pov_character_id / characters_involved / character_decisions / knowledge_changes / relationship_changes`（类型化，可追溯 motivation/source/cause）。

---

## 受控偏移（即兴层）

> **即兴 ≠ 随机。** 实现的是**约束下的高创造性偏移（Controlled Divergence）**。

| 模块 | 作用 |
| --- | --- |
| `improvisation_score.py` | 指挥台：读参数、发 `Cue`、决定偏移程度（核心） |
| `randomizer.py` | 随机种子 `JazzSeed`：情绪 / 视角 / 象征 / 切入角度 |
| `operator_engine.py` | 8 种叙事操作：注意力转移 / 感官替换 / 认知偏差 / 信息错位 / 意象变奏 / 情绪反差 / 行动偏航 / 因果重审 |
| `motif_engine.py` | 动机变奏：literal → symbolic → psychological → philosophical |
| `surprise_engine.py` | 受控意外（尊重故事状态）：隐藏关系 / 错误记忆 / 反向因果 / 未知观察者 / 时间错位 / 物件背叛 |
| `rhythm_engine.py` | 叙事节奏：adagio / swing / bebop / ballad / free |
| `solo_engine.py` | 人物 Solo：每个角色的"乐器"、关注点、盲点、记忆滤镜 |

乐谱参数（`story.yaml` 的 `jazz:` 段，可命令行覆盖）：

| 参数 | 作用 | classic_jazz | bebop | free_jazz |
| --- | --- | --- | --- | --- |
| creativity | 创造程度 | 0.25 | 0.60 | 0.85 |
| randomness | 随机扰动 | 0.15 | 0.45 | 0.70 |
| motif_reuse | 主题重复 | 0.90 | 0.75 | 0.50 |
| character_freedom | 人物自主性 | 0.35 | 0.60 | 0.85 |
| surprise_level | 剧情转折 | 0.15 | 0.50 | 0.70 |
| style_distance | 语言变化 | 0.15 | 0.45 | 0.80 |

结构参数：`idea_divergence / causal_variation / character_agency / motif_transformation / revelation_delay / branch_count / continuity_strength`。

---

## 结构即兴引擎

```
前提
 └─ StoryIdea × N      engine/book_planner.py      故事级发散（五维对照 / 融合）
     └─ BookPlan       engine/outline_expander.py  逐级展开为分卷 + ChapterPlan
         └─ 校验       engine/plot_validator.py · structure_evaluator.py（硬校验 + 叙事审阅）
             └─ 局部重新即兴  engine/reimproviser.py（候选 → 采纳；锁定保护）
```

- **发散与对照**：`StoryIdea` 含 `theme_reading`（主题解释）；`Session.compare_ideas` 五维并排；`Session.fuse_compare` 标注融合维度取自 A/B。
- **硬约束注入**：世界规则/禁忌/人物认知/已确定事实/秘密在**创意、梗概、逐卷展开**三个阶段共同生效（`BookPlan.constraints` 可追溯）；`generated_by` 标记 `llm` / `offline_template`。
- **分阶段 + 严格校验的 LLM 规划**：蓝图 → 逐卷章节卡片 → **章数必须完全一致、字段非空**，不满足即回退并明确标记，绝不静默接受。
- **全书梗概**：`synopsis / opening_state / inciting_incident / central_turn / climax / resolution`——不看卡片也能理解故事为何这样发展、结尾如何回应。
- **POV 分布**：`multi_pov` 平衡交错、`ensemble` 连续视角弧；关键转折章收束到 `primary_character_id`（不再依赖文件顺序）。
- **锁定**：整章锁定 + 字段级锁定；`expand_book` 拒绝在已有详细卡片时静默重写（需 `force`）。
- **重新即兴 = 候选 → 采纳**：先给候选（含改动字段），采纳后才写回；锁定内容不被覆盖。
- **两层校验**：结构硬校验（缺章/编号/断链/未回收线索/闲置人物/未知人物 id/关系连续性/认知连续性）+ 可选**叙事审阅**（事件合理性/人物选择/冲突升级/结局回应，给出依据与章号）。
- **结构评价七维**：创意独特性 / 故事完整性 / 因果连续性 / 人物变化 / 章节贡献 / 伏笔与回收 / **关系演变**。
- **创意过期保护**：方案记录前提指纹，前提改动后 `ideas_stale` 会提示过期。

---

## 记忆 · 偏离检测 · 可视化

- **轻量语义记忆**（`engine/memory.py`）：近重复检测、主题漂移、人物弧缺失、意象未使用、结构卡片提前揭露。（相似度为"报警"，不作评分。）
- **向量记忆**（`engine/vector_store.py`）：**可持久化**的语义向量库——有嵌入模型时用 embedding，否则回退 CJK 词向量，存到 `output/vector_store.json`；`Session.vector_memory()/vector_search()`，CLI `memory`。
- **故事板导出**（`engine/report.py`）：`output/story_report.md` 与**可交互** `output/story_report.html`（按视角筛选、关键词搜索、点击章节查看卡片）；含动机演变时间线、人物弧线图、线索伏笔面板。
- **运行记录**：每次 `play` 写 `output/runs/<run_id>.json`（cue/prompt/评价/建议）；`history` 做趋势统计；`--show-prompt` 打印的就是实际调用的同一份 prompt。

---

## Jam Session 合奏

`jam_session/` 顺序合奏，各角色任务不同、**不各自重写正文**：

- **Director** 定方向与限制 → **Soloist** 从人物欲望/恐惧/盲点出行动 → **Observer** 给非中心细节/边缘视角 → **Editor** 给候选打分排序、剔除矛盾与提前揭露、整合提案（**不自动升级为正式设定**）。
- **多轮辩论**（`rounds≥2`）：Observer **反驳**（太笼统/直说主题/复述旧冲突）→ Soloist **修订** → Editor **归因**（谁贡献了哪个想法）。
- CLI：`python main.py jam "场景" --pov 林 --rounds 2 --render`。

---

## 接入真实模型

**任意 OpenAI 兼容端点**（OpenAI / DeepSeek / Qwen / vLLM / Ollama）：

```powershell
pip install openai
$env:OPENAI_API_KEY = "sk-..."
$env:NJE_BASE_URL   = "https://api.deepseek.com/v1"
$env:NJE_MODEL      = "deepseek-chat"
python main.py play "..." --provider openai
```

**opencode（复用你已连接的模型）**：

```powershell
opencode serve --port 4096          # 另开终端
python main.py play "..." --provider opencode
```

可选环境变量：`NJE_OPENCODE_URL`（默认 `http://127.0.0.1:4096`）、`NJE_OPENCODE_MODEL`、`OPENCODE_SERVER_PASSWORD`。
不设任何 Key 时仍可用 `mock` 离线跑通。

---

## 数据文件（乐谱）

- `data/story.yaml` — 主题旋律 + 叙事和声 + 即兴参数
- `data/characters.yaml` — 人物库（id/层级/视角 + 叙事驱动字段）
- `data/relationships.yaml` — 人物关系网络
- `data/motifs.yaml` — 意象定义（运行时意义演变写入 `motif_state.yaml`）
- `data/story_state.yaml` — 故事圣经（事实 / 认知 / 线索 / 近期事件）

`python main.py init --force` 重新写入示例乐谱。`--data <dir>` 可切换到独立项目乐谱（如同时维护多部小说）。

---

## 架构

```
core/           theme / character / relationship / harmony / motif / story_state
                story_idea / volume_plan / chapter_plan / book_plan / improviser
improvisation/  improvisation_score(指挥台+Cue) · operator_engine · randomizer
                motif_engine · surprise_engine · rhythm_engine · solo_engine
engine/         book_planner · outline_expander · reimproviser · plot_validator
                structure_evaluator · narrative_reviewer · scene_planner
                composer · variation · evaluator · textutil · semantic_similarity
                memory · vector_store · report · planning_llm
feedback/       theme_check / character_check / novelty_check / conductor
jam_session/    director / soloist / observer / editor / orchestrator
llm/            base / mock / openai_provider / opencode_provider
session.py  store.py  cli.py  gui.py  main.py
tests/          回归测试（91 项）
projects/       独立小说的乐谱与稿子（示例见 projects/border2020/）
```

---

## 设计原则

1. **硬约束 vs 软约束**：世界规则、时间线、人物经历、人物认知不可违反；描述方式、场景顺序、语言风格可自由变奏。
2. **主题不可直说**：只通过细节与意象让主题"被听见"。
3. **人物驱动而非情节驱动**：同一事件经过不同人物的欲望与盲点，产生不同故事。
4. **动机变奏**：每个核心意象出现时给出新意义，杜绝同义复读。
5. **受控偏移**：即兴不是随机；所有偏离都由 `Cue` 约束，并可在回听后回调。
6. **作者优先**：系统只提供方案与提案，采纳与定稿始终由作者决定。

---

## 测试

```powershell
python -m unittest discover -s tests     # 91 项：确定性 / 记录 / 连续性 / 约束注入 / 结构校验 / 人物关系 / 反馈边界 / 向量记忆 / Jam
```

---

## 版本历史

| 版本 | 内容 |
| --- | --- |
| **v2.11** | 向量记忆（持久化/embedding 可选）· 交互式故事板 · Jam 多轮辩论 · 模型生成场景骨架 |
| v2.10 | 创意五维对照 · 融合对照 · 章节级人物上下文 · 结构化编辑控件 · 关系演变维度 |
| v2.9 | 人物认知连续性（来源必填/不来自未来/秘密提示）· 注入链路测试 |
| v2.8 | 类型化人物字段 · `primary_character_id` · `resolve_character` · 关系孤立诊断 · JSON 编辑器 |
| v2.7 | 每章关系变化 + 关系连续性校验 |
| v2.6 | 人物与关系网络 · `chars` 命令 · GUI「人物」页 |
| v2.5 | 质量门禁回归测试 · 章号/缺章校验 · GUI 单任务守卫 |
| v2.4 | 重新即兴候选/采纳 · 硬约束注入 · 分阶段严格章数校验 · 全书梗概 · 两层校验 · 创意过期保护 |
| v2.3 | 记忆与偏离检测（theme drift / 近重复 / 弧缺失）· 故事板导出 |
| v2.2 | POV 分布优化 · 字段级锁定 · Jam Session |
| v2.1 | 方案融合 · 章节卡片编辑 · 范围重生成 |
| v2.0 | 定位转向「结构即兴引擎」（BookPlan / 结构校验 / 结构工作台） |
| v0.4–v0.6 | 即兴层与受控偏移（操作库 · 故事状态感知的意外 · 多路径探索 · 回听重调） |
| v0.2–v0.3 | 可插拔 LLM · 回听评价 · 多 Take |

核心循环：**设定 → 即兴决策 → 生成多个可能性 → 回听与比较 → 作者选择 → 更新故事状态 → 下一轮即兴。**
