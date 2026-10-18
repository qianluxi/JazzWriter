# JazzWriter（小说爵士引擎）`v2.26`

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
- [World Studio（世界观工坊）](#world-studio世界观工坊)
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
python world_studio_gui.py     # 世界观工坊界面（或双击 WorldStudio.bat）
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
python main.py outline --export            # → <数据目录>/book_outline.md

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

## 项目管理

多部小说互不干扰：每个项目是 `projects/<目录>/` 下的一套独立乐谱。

- **新建主题**：GUI 顶部「**新建项目**」——填写名称 + 世界观/大致剧情（简介框），程序据此生成
  `story.yaml / characters.yaml / relationships.yaml / motifs.yaml / story_state.yaml / brief.md`
  （有模型时由模型扩展人物与关系；离线给可编辑的起步集）。
- **继续主题**：顶部「项目」下拉选择，点「**打开**」；数据目录随之切换，后续规划/正文/历史都写在该项目下。
  （打开后会弹出确认，标题栏右侧显示「项目：…」，避免"看起来没反应"。）
- **修改世界观 / 重建**：选中项目后点「**编辑/重建**」——修改简介并重建，程序会重新生成整套设定；
  **旧文件（含已保存的结构 book_plan）会先移入 `_backup_*` 目录**，避免用旧结构渲染新世界。
- **删除项目**：选中项目后点「**删除项目**」——删除本地目录，并**同步移除在线预览**（`docs/preview/<项目>.html`）并推送，`preview/` 索引随之更新。
- **安全护栏**：`project delete` / `project regen` 只作用于 **`projects/` 的直系子目录**，且必须是含 `story.yaml` 的真实项目；校验前会 `resolve()` 解析符号链接（防越权跳转），传入根目录之外、根目录本身或缺 `story.yaml` 的路径都会被**拒绝**。CLI 同样受限，不依赖 GUI 选项。
- **发布安全**：预览自动提交**只含 `docs/preview` 目标文件**（用 `git commit --only`），并**拒绝非法的预览路径**（`..`、绝对路径、pathspec magic 等）；若当前分支**已有未推送提交**或没有 `origin` upstream，会自动中止发布，避免连带公开其它改动。
- **CLI**：
  ```powershell
  python main.py project list
  python main.py project show border2020                 # 查看项目主题/人物/简介
  python main.py project new "界河纪事" --brief "2020年代中俄边境……"
  python main.py project regen "界河纪事" --file new_brief.txt   # 修改简介并重建
  python main.py project delete "界河纪事" --yes           # 删除项目并同步移除在线预览
  python main.py --data projects/界河纪事 status          # 继续该项目
  ```

---

## World Studio（世界观工坊）

**独立入口**：`python world_studio.py`（命令行）与 `python world_studio_gui.py`（独立窗口，或双击 `WorldStudio.bat`）。数据独立保存在 `worlds/<slug>/`，**不写入小说项目**，直到你明确导出。

> 新手指引：`docs/WorldStudio_新手引导.docx`（或 `docs/WorldStudio_新手引导.md`）。

一条可观察、可保存的创意工作流：**只言片语 → 发散多个底层逻辑不同的世界原型 → 选择 → 逐层生长 → 一致性提示 → 导出 `world.md`**。

- **灵感种子（spark）**：一句话即可开始。系统用「认知 / 制度 / 存在论 / 经济 / 信仰 / 物理」六种**底层逻辑**重新解释同一片语，产出 3–5 个真正不同的原型。**差异度按世界机制（规则/权力/知识/困境/时间五个维度）计算**，并会标出"标签不同但机制重复"的原型，而不是只看文字相似度。
- **保存与恢复闭环**：发散即存；重新打开会**恢复种子与原型列表并高亮已选原型**；原型按 **ID** 选择（不依赖列表位置）。CLI 提供 `pick <slug> <原型>`；`grow` 不再静默选择第一个原型。
- **逐层生长（由规则推导，非套模板）**：先由核心规则推出**结构属性**（可观测性 / 稀缺性 / 执行方式 / 代价 / 可变性），每条属性带**证据**与**把握度**，**无法判断时为「未知」并生成待确认问题**（不猜）。再由属性推导演绎出 社会后果 · 知识与认知 · 制度与权力 · 历史动力 · 地理与空间 · 冲突与人物 · 意象与母题；每条都带**依据**，不同规则会生长出结构不同的世界。
- **多层依赖溯源**：条目依赖是**规则 → 后果 → 制度/历史 → 地理/冲突**的链，而非都挂在核心规则下的星形；可反查"若修改某条规则，会牵连哪些候选设定"（`impact`）。
- **设定嫁接（graft）**：导入已有世界观文档，抽取**抽象骨架**（规则 / 主题 / 权力 / 历史 / 美学）。每种操作是一份**结构化变形计划**（保留哪些前提 / 反转哪条假设 / 哪些属性位移 / 新增哪些规则 / 预期影响），并据此生成内容——`深度变形 / 主题移植 / 世界交叉 / 边缘扩展 / 反转前提` 会产出**不同的核心规则与后果链**，而非只改说明。**默认派生新世界，不改动源世界**；`世界交叉`**强制要求第二份材料**。新增规则一律标「候选」。
- **状态区分**：`confirmed（已确认）/ candidate（候选）/ open（未决）/ contradiction（有意保留的矛盾）`——模型不会把猜想当成已定事实；可逐条切换状态与锁定，Markdown 中**所有条目**都会标注状态与锁定。
- **一致性检查只提示、不自动修正**：合并同类重复、**跨类别**疑似冲突、**规则↔下游条目**专项检查（均带**依据**与**把握度**）、依赖影响与有意保留的矛盾；可选用真实模型做语义审阅（结果标注"需人工确认"）。**离线模式会明确声明"不做语义判断"**，因此"未发现冲突"不等于"与核心规则一致"。
- **数据安全**：世界观名（slug）限定为单层目录名，路径经 `resolve()` 后必须位于世界观根目录内（拒绝 `..`、分隔符与越界）。
- **模型输出校验**：模型 JSON 经严格校验（`kind` 白名单、必填字段、非空陈述）；缺失或非法条目被忽略，关键类别缺失时**回退到离线推导并在文档中提示**。
- **产出**：`worlds/<slug>/world.md`（结构化世界观文档）+ `world.json`（机器可读）。
- **模型**：可选 `--provider opencode|openai`；默认离线 `mock` 用确定性推导给出可读骨架（标注 `offline_template`）。

```powershell
python world_studio.py spark "每个人死后都会留下一段从未说出口的记忆，但只有建筑能听见"
python world_studio.py spark "…" --pick 制度世界           # 选择原型 → 生长 → 导出 world.md
python world_studio.py pick <slug> idea-2                  # 稍后回到该项目，选第二个原型
python world_studio.py grow <slug> [--pick 制度世界]        # 生长并导出（未选原型会报错，不静默）
python world_studio.py graft notes/world.txt --op 反转前提 --seed "一个没有夜晚的城市"   # 派生新世界
python world_studio.py graft a.txt --op 世界交叉 --seed "…" --second b.txt              # 交叉需第二份材料
python world_studio.py check <slug>                        # 一致性提示（含依据/把握度/离线声明）
python world_studio.py impact <slug> rule-1                # 修改该条目会牵连哪些设定
python world_studio.py state <slug> consequence-1 confirmed  # 设置条目状态
python world_studio.py show <slug> / list                  # 状态 / 列表
python world_studio_gui.py                                 # 独立图形界面（发散即存 / 打开恢复 / 改状态 / 锁定）
```

---

## 命令速查

| 命令 | 作用 |
| --- | --- |
| `project list` / `show <dir>` / `new "名称" --brief "…"` | 列出 / 查看 / 从简介生成项目 |
| `project regen <dir> [--file 简介]` | 用新简介重建项目（旧文件归档到 `_backup_*`） |
| `project delete <dir> --yes` | 删除项目（本地 + 同步移除在线预览） |
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
| `preview [--no-publish]` | 生成并（默认）推送在线正文预览 `preview/` |
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
- **重新即兴 = 候选 → 采纳**：先给候选（含改动字段），采纳后才写回；锁定内容不被覆盖。**重即兴保持该章的 POV 与参与人物不变**（只改行动/冲突/结果/信息变化），从根本上保证显示 POV、稳定 id 与参与列表一致。
- **两层校验**：结构硬校验（缺章/编号/断链/未回收线索/闲置人物/未知人物 id/关系连续性/认知连续性）+ 可选**叙事审阅**（事件合理性/人物选择/冲突升级/结局回应，给出依据与章号）。
- **事实冲突（语义）显式审阅**：把各章与 `story_state` 的**已确定事实**对照，判断是否存在语义矛盾（如"设备从未修复" vs "已修复成功"），结论带章号与引用的事实。**需要模型**；离线时明确标注"需接入模型、不判定"，绝不静默通过。
- **结构评价七维**：创意独特性 / 故事完整性 / 因果连续性 / 人物变化 / 章节贡献 / 伏笔与回收 / **关系演变**。
- **创意过期保护**：方案记录前提指纹，前提改动后 `ideas_stale` 会提示过期。

---

## 记忆 · 偏离检测 · 可视化

- **轻量语义记忆**（`engine/memory.py`）：近重复检测、主题漂移、人物弧缺失、意象未使用、结构卡片提前揭露。（相似度为"报警"，不作评分。）
- **向量记忆**（`engine/vector_store.py`）：**可持久化**的语义向量库——有嵌入模型时用 embedding，否则回退 CJK 词向量，存到**数据目录**（如 `data/vector_store.json`）；`Session.vector_memory()/vector_search()`，CLI `memory`。
- **故事板导出**（`engine/report.py`）：`story_report.md` 与**可交互** `story_report.html`（按视角筛选、关键词搜索、点击章节查看卡片）；含动机演变时间线、人物弧线图、线索伏笔面板。
- **运行记录**：每次 `play` 写 `output/runs/<run_id>.json`（cue/prompt/评价/建议）；`history` 做趋势统计；`--show-prompt` 打印的就是实际调用的同一份 prompt。
- **项目隔离（完整）**：`BookPlan / 结构导出 / 向量库 / 故事板 / 运行记录(runs) / 章节正文(chapters) / 参数建议(advice_history) / story_state / jazz_state` 全部保存在**当前数据目录**下；`--data <dir>` 切换项目时互不干扰。

### 在线正文预览（GitHub Pages）

每次「按结构渲染正文」都会生成一个**自包含的阅读页**，并**默认同步到远端**：

- 生成：`docs/preview/<项目>.html`，以及索引 `docs/preview/index.html`（多部作品并列）。
- **字数统计**：每章标注字数、页脚显示全书总字数；GUI「正文」页与 CLI `book` 概览表同样给出每章/全书字数。
- 自动同步：渲染后自动提交并推送（push 失败自动重试）。**提交范围被限定为 `docs/preview` 目标文件**，不会连带提交你已暂存的其它改动；**若当前分支有未推送提交或没有 `origin` upstream 则自动中止**（避免误公开）。用 `NJE_PREVIEW_AUTOPUSH=0` 关闭，或 `book --from-plan --no-publish`。
- 单独重发：`python main.py preview [--no-publish]`。
- 在线地址：`https://<user>.github.io/<repo>/preview/<项目>.html`
  （本仓库即 `https://qianluxi.github.io/JazzWriter/preview/`）。
- 开启方法（**仓库**设置，别点右上角头像里的账号设置——那是 "Verified domains"）：
  打开 `https://github.com/qianluxi/JazzWriter/settings/pages` → **Build and deployment** →
  Source 选 **Deploy from a branch** → Branch `main`、Folder **`/docs`** → Save。
  （预览位于 `docs/preview/`，故用 `/docs` 源；站点根 `docs/index.html` 为首页。）

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

`projects/<目录>/` 保存各自独立的小说项目（`python main.py project new` 或 GUI 新建）。

`python main.py init --force` 重新写入示例乐谱。`--data <dir>` 可切换到独立项目乐谱（如同时维护多部小说）——
**全书规划、结构导出、向量库、故事板、运行记录、章节正文与参数状态都保存在该目录下**，切换项目互不干扰。

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
world/          World Studio：idea_forge(发散+机制度量) · expander(按规则属性推导)
                graft(嫁接/结构化差异) · graph(依赖溯源) · checker(一致性提示)
                emit(导出 Markdown) · studio(编排) · models · util
world_studio.py  world_studio_gui.py   世界观工坊的独立入口（CLI / GUI）
tests/          回归测试（162 项）
projects/       独立小说的乐谱与稿子（示例见 projects/border2020/；产出随各项目目录保存）
worlds/         独立的世界观项目（World Studio 产物，本地保存，不入库）
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
python -m unittest discover -s tests     # 162 项：确定性 / 记录 / 连续性 / 约束注入 / 结构校验 / 人物关系 / 反馈边界 / 向量记忆 / Jam / 项目隔离 / 事实冲突审阅 / 世界观工坊
```

---

## 版本历史

| 版本 | 内容 |
| --- | --- |
| **v2.26** | World Studio 易用性：新增**独立启动器 `WorldStudio.bat`** 与**《World Studio 新手引导》**（`docs/WorldStudio_新手引导.docx` / `.md`）· 站点首页加入工坊引导入口 |
| **v2.25** | World Studio 可靠性修复（专家复审）：**保存后恢复闭环**（GUI 恢复种子/原型/选中并按 ID 选择；CLI 新增 `pick`，`grow` 不再静默默认第一条）· **嫁接默认派生新世界不覆盖源世界**，`世界交叉`**强制第二份材料** · 嫁接改为**结构化变形计划**并据此生成不同的核心规则与后果链 · 规则属性**含证据/把握度/未知**（处理否定与范围）· 一致性新增**规则↔下游**检查与**离线不做语义判断**声明 · 依赖图改为**多层链** · **slug 路径护栏** · **模型 JSON 严格校验与回退** · Markdown 输出**全条目**状态与锁定 |
| **v2.24** | World Studio 可靠性提升（专家评审 P1）：**原型差异度改为按世界机制五维度量**并标记"标签不同但机制重复"· **生长改为由规则属性**（可观测性/稀缺性/执行/代价/可变性）**推导**而非固定模板 · 新增**依赖图**（`impact` 反查受影响条目）· 一致性检查**跨类别 + 输出依据与把握度 + 可选模型语义审阅** · 嫁接输出**结构化差异**（继承/删除/修改/新增/下游影响）· GUI 支持**发散即存、打开已有、改状态与锁定** |
| **v2.23** | 新模块 **World Studio（世界观工坊）**：独立入口 `world_studio.py` / `world_studio_gui.py`，独立数据目录 `worlds/`。**灵感种子**（一句话发散多个底层逻辑不同的世界原型）+ **设定嫁接**（抽取骨架 → 深度变形/主题移植/世界交叉/边缘扩展/反转前提）；状态区分与只提示不修正的一致性检查；产出结构化 `world.md` |
| **v2.22** | 并入专家 P1 补丁的加固：项目校验收紧为 `projects/` **直系子目录** + 符号链接解析；预览路径合法性校验；**本地有未推送提交 / 无 origin upstream 时自动发布中止**（避免连带公开） |
| **v2.21** | 安全修复：`project delete/regen` 仅限 `projects/` 内真实项目（防越界删改）· 预览自动提交**只含 `docs/preview` 目标文件**，不牵连其它已暂存改动 |
| **v2.20** | 每章/全书**字数统计**（GUI/CLI/在线预览）· 预览推送失败自动重试 |
| **v2.19** | 删除项目：本地删除 + 同步移除在线预览并推送（GUI「删除项目」/ CLI `project delete`） |
| **v2.18** | 在线正文预览：渲染正文即生成 `docs/preview/` 并默认推送远端（GitHub Pages 可访问） |
| **v2.17** | 项目「编辑/重建」（改简介重生成整套设定，旧文件归档 `_backup_*`）· 打开项目有明确反馈/当前项目标签 · CLI `project show/regen` |
| **v2.16** | 项目管理：输入世界观/剧情简介即在 `projects/` 下生成新项目（GUI 新建/打开项目 + CLI `project`） |
| **v2.15** | 重即兴固定该章 POV 与参与人物（消除元数据不一致）· 项目 A/B 数据完全隔离的验收测试 · 端到端工作流测试 |
| **v2.14** | 新增「与已确定事实的语义冲突」显式 LLM 审阅项（带章号与引用事实；离线明确标注"需模型、不判定"） |
| **v2.13** | 修复：运行记录/正文/参数/状态也随数据目录隔离 · 重复人物 id 不再丢人且可被检查 · 重即兴同步刷新参与人物与 POV id、来源锚定到线索 · 离线清洗覆盖全部字段（含标题/钩子/线索，逐 POV 秘密）· 无可作视角人物时报错 · 取消 compose_book 场景循环复用 |
| **v2.12** | 修复：多项目产出隔离（规划/向量/故事板随数据目录）· 同名人物不再被覆盖（按 id 存储）· 重新即兴同步刷新人物决策/认知/关系 · 离线路径执行世界规则与故事状态 · 知识来源具体化并校验"只给章号" |
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
