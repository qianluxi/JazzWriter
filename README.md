# JazzWriter（小说爵士引擎）`v2.4`

> **长篇小说结构即兴引擎 / Human-AI Improvisational Writing System。**
> 主要产物不是小说正文，而是**故事方案、全书梗概、分卷结构与逐章摘要**。

## 工作流（结构优先）

1. **输入故事前提**
2. **生成并比较多个创意方案**（在"因果机制/真相/关系/结局/主题解释"上实质不同）
3. **选择或融合**方案
4. **生成完整故事梗概与分卷规划**（synopsis / 开端 / 触发事件 / 关键转折 / 高潮 / 结局处理）
5. **展开、编辑、锁定**章节摘要卡片（可字段级锁定）
6. **校验全书**（结构硬校验 + 叙事审阅，问题优先于分数）
7. **按需局部重新即兴**（先出候选，作者采纳后才写回；锁定内容不被覆盖）
8. **最后才进入可选的正文试写**

> ⚠️ **mock 与真实模型**：默认 `mock` 是**离线演示**，只用于验证流程（章节卡片明显模板化）。
> 结构创意与正文质量主要依赖真实模型：`--provider opencode`（复用你已连接的模型）或
> `--provider openai`。离线生成的结构会明确标记为 `offline_template`，不会伪装成模型创作。

设计目标不变：**可控的创造性**——在主题、世界规则、人物认知与既有事实的约束下，
探索"这个故事还能怎样成立"。

## 映射关系

| 爵士 | 本系统 |
| --- | --- |
| Head / Theme 主题旋律 | `Theme` 核心命题、情绪、象征 |
| Chord changes 和声 | `Harmony` 世界硬约束、禁忌、情绪进行 |
| Soloist 独奏者 | `Character` 欲望/恐惧/世界观/即兴规则 |
| Motif 动机 | `Motif` 反复出现但意义演变 |
| Comping / 转调 | `ImprovisationScore` 受控偏移（随机、意外、节奏、独奏) |
| Take 录音 | 一次生成的多版本章节 |
| Listen-back 回听 | `Evaluator` + `feedback/Conductor` 评价并重调乐谱 |

> **即兴 ≠ 随机。** 本系统实现的是**约束下的高创造性偏移（Controlled Divergence）**：
> 在既定的主题与和声里，决定一次演奏"能走多远、往哪个方向走"。

## 安装

```powershell
pip install -r requirements.txt
```

无需任何 API Key 即可运行（内置离线 `mock` provider，用于打通流程）。

## 图形界面（推荐给非开发者）

```powershell
python gui.py
```

或直接双击根目录的 **`JazzWriter.bat`**。界面左侧填场景、选模式/人物/风格、调即兴参数，
点「▶ 演奏一章」；右侧标签页分别显示 **正文 / 即兴决策(Cue) / 评价 / 建议 / 状态 / 历史**。
另有「多版本 · 探索路径」「下一章场景建议」。仅用标准库 Tkinter，无需额外安装。

**结构工作台**：左侧「① 结构即兴」——「生成创意方案」→「融合所选两个方案」/ 选「采纳方案#」→
「采纳并展开全书结构」；右侧有「创意候选 / 全书结构 / 结构树 / 章节卡片」标签。
在「结构树」选中一章后，「章节卡片」可直接编辑字段并点「保存章节卡片编辑」；
「重新即兴选中章（可选范围）」会弹出勾选框决定重生成哪些后续章节（锁定章不重生成）。
「② 局部演练」里的「按结构渲染正文」才会生成正文。
所有生成都在**主线程先快照参数、后台线程执行、期间按钮禁用**，避免并发冲突。

## 使用（结构优先）

```powershell
# 1) 从一个前提发散出若干「实质不同」的故事方案
python main.py outline "一场技术事故改变了一个家庭" --branches 3 --seed 1

# 2) 采纳某个方案，展开全书结构（分卷 + 逐章摘要卡片）
python main.py outline "一场技术事故改变了一个家庭" --build --pick 2 --chapters 12 --template mystery

# 3) 结构校验（六维 + 具体问题）／ 锁定 / 重新即兴 / 导出
python main.py outline --validate
python main.py outline --lock 3
python main.py outline --reimprovise 5                 # 生成第5章候选（不覆盖原卡片）
python main.py outline --reimprovise 5 --adopt 1       # 采纳第1个候选并写回
python main.py outline --reimprovise 5 --adopt 1 --regen all   # 采纳并重生成后续章节
python main.py outline --export            # → output/book_outline.md

# 融合两个故事方案（取 A 的因果/关系、B 的真相/结局，形成新的机制）
python main.py outline "一场技术事故改变了一个家庭" --fuse 1 2

# 编辑某章卡片：准备一个「字段：值」文本文件再导入
python main.py outline --edit 3 --file card.txt

# 字段级锁定：重生成时保留该字段
python main.py outline --lock-field 3 conflict

# 顺序合奏：导演 → 独奏 → 观察 → 编辑（--render 用提案渲染正文）
python main.py jam "深夜。检修井底，阀门自己转动了。" --pov 林 --render

# 偏离检测 + 导出故事板（动机演变时间线 / 人物弧线 / 伏笔面板；--open 打开 HTML）
python main.py report --open

# 4) 按结构渲染正文（可选局部演练）
python main.py book --from-plan --pov 林 --no-save
```

结构模板：`linear_causality | mystery | multi_pov | ensemble | nonlinear_puzzle | custom`。
结构参数：`--idea-divergence --causal-variation --character-agency --motif-transformation
--revelation-delay --branch-count --continuity-strength`。

### 其它命令

```powershell
# 查看主题 / 人物 / 和声 / 动机
python main.py status

# 即兴演奏一章（离线）
python main.py play "冬夜，学校食堂，一台报废的蒸汽机仍在运行" --pov 林 --mode classic_jazz --style 冷静观察

# 自由爵士模式 + 固定随机种子（同一"乐谱"可复现，换模式则会受控地偏移）
python main.py play "废弃工厂。林推开门。" --pov 林 --mode free_jazz --seed 42 --chapter 5 --total 12

# 自定义乐谱参数（覆盖 story.yaml）
python main.py play "..." --creativity 0.8 --surprise-level 0.6 --style-distance 0.7

# 同一场景生成多个版本（同一和声，不同 Solo 色彩）
python main.py takes "同上" --mode bebop --styles 冷静观察 象征增强 心理深入

# 模式B：同一主题多次独立即兴（各 Take 走不同叙事路径）
python main.py takes "同上" --mode bebop --seed 7 --explore --styles 象征增强 心理深入

# 逐章试写（每行一章，自动衔接上文）；场景不足会报错，不再循环复用
python main.py book "第1章场景" "第2章场景" "第3章场景" --pov 林 --mode bebop --seed 100
python main.py book --from-plan                # 用 outline 生成的结构渲染正文
python main.py book --file outline.txt --chapters 3 --style-cycle 冷峻 抒情 象征增强

# 生成后给出下一章场景骨架（交互式选择，不自动续写）
python main.py play "..." --suggest
python main.py plan --count 3

# 打印实际调用模型的完整 prompt（与真实调用一致）
python main.py play "..." --show-prompt

# 回听评价一个已保存的章节（可切换评价方式）
python main.py evaluate output/chapters/ch001_take01_冷静观察.md --eval-mode lexical

# 查看动机的意义演变轨迹
python main.py motifs

# 查看演奏历史与趋势统计
python main.py history
python main.py history --chapter 5 --metric novelty --limit 20

# 查看并显式应用下一轮参数建议（默认不自动改默认乐谱）
python main.py advice
python main.py advice --apply

# 查看即兴参数与三种模式预设
python main.py jazz

# 查看可用即兴模式与 Solo 色彩
python main.py styles

# 无参数运行：离线演示
python main.py
```

运行回归测试（确定性 / 记录完整性 / 连续性 / 反馈边界）：

```powershell
python -m unittest discover -s tests
```

通过管道传入场景：

```powershell
"雨夜。档案馆停电。" | python main.py play --pov 苏
```

## 接入真实 LLM

任何 OpenAI 兼容端点（OpenAI / DeepSeek / Qwen / vLLM / Ollama）：

```powershell
pip install openai
$env:OPENAI_API_KEY = "sk-..."
$env:NJE_BASE_URL   = "https://api.deepseek.com/v1"
$env:NJE_MODEL      = "deepseek-chat"
python main.py play "..." --provider openai
```

或用环境变量 `NJE_PROVIDER=openai` 设为默认。

### 用 opencode 自己的模型（opencode serve）

JazzWriter 可以**直接复用 opencode 已连接的大模型**（OpenCode Zen / Go，或你 `/connect` 过的任意 provider），
无需单独配置 API Key——它通过本地 opencode server 调用：

```powershell
# 1) 另开一个终端，启动 opencode 服务器（默认端口 4096）
opencode serve --port 4096

# 2) 在 JazzWriter 里选择 opencode 后端
python main.py play "..." --provider opencode
#   或 GUI 顶部「模型」下拉选 opencode
```

可选环境变量：

```powershell
$env:NJE_OPENCODE_URL = "http://127.0.0.1:4096"      # 默认值
$env:NJE_OPENCODE_MODEL = "anthropic/claude-sonnet-4" # 不设则用服务器默认模型
$env:OPENCODE_SERVER_PASSWORD = "..."                 # 若服务器开了 basic auth
```

openai 与 opencode 两个后端都可用；不设任何 Key 时仍可用 `mock` 离线跑通流程。

## 即兴层 · Controlled Divergence

世界设定 → 人物 → 剧情结构 → **【即兴层】** → 文本。即兴层在每次演奏前发一张
`Cue`（乐谱），决定本次"能走多远、往哪走"：

| 模块 | 作用 |
| --- | --- |
| `improvisation_score.py` | 指挥台：读参数、发 Cue、决定偏移程度（核心） |
| `randomizer.py` | 随机种子 `JazzSeed`：情绪 / 视角 / 象征 / 切入角度 |
| `motif_engine.py` | 动机变奏：literal → symbolic → psychological → philosophical |
| `surprise_engine.py` | 受控意外：隐藏关系 / 错误记忆 / 反向因果 / 未知观察者 / 时间错位 / 物件背叛 |
| `rhythm_engine.py` | 叙事节奏：adagio / swing / bebop / ballad / free |
| `solo_engine.py` | 人物 Solo：每个角色有自己的"乐器"、关注点、盲点、记忆滤镜 |

**乐谱参数**（`data/story.yaml` 的 `jazz:` 段，可用命令行覆盖）：

| 参数 | 作用 | classic_jazz | bebop | free_jazz |
| --- | --- | --- | --- | --- |
| creativity | 创造程度 | 0.25 | 0.60 | 0.85 |
| randomness | 随机扰动 | 0.15 | 0.45 | 0.70 |
| motif_reuse | 主题重复 | 0.90 | 0.75 | 0.50 |
| character_freedom | 人物自主性 | 0.35 | 0.60 | 0.85 |
| surprise_level | 剧情转折 | 0.15 | 0.50 | 0.70 |
| style_distance | 语言变化 | 0.15 | 0.45 | 0.80 |

### 叙事操作 · ImprovisationOperator（V0.5 核心）

即兴不是随机加情节，而是选择一种**叙事操作**：注意力转移 / 感官替换 / 认知偏差 /
信息错位 / 意象变奏 / 情绪反差 / 行动偏航 / 因果重审。每轮按参数随机挑选 1–3 个组合，
并附带硬约束（人物动机一致、不得篡改已确定事实、不得提前揭露）。见
`improvisation/operator_engine.py`。

### 故事状态与连续性 · StoryState（V0.6 基础）

`data/story_state.yaml` 区分五种“真”：**已确定事实 / 怀疑 / 秘密 / 未决线索 /
候选创意**。`SurpriseEngine` 会读取故事状态：过滤不适用的意外、为意外绑定具体的
事实/线索/意象、并保证**已确定事实不可被随机覆盖**。`Evaluator` 会检测“提前揭露”
（连续性问题）并单独报告，而不计入总分。

### 回听 → 重调（`feedback/`）

`Conductor` 读评价给出下一轮参数建议：创新太低则提高 `randomness`，偏离主题则降低
自由度。建议写入 `output/advice_history.jsonl`，默认**只待审核**；`advice --apply`
才把结果写入 `data/jazz_state.yaml`（运行时状态），不会静默改动作者在 `story.yaml`
里的默认乐谱。

### 可观测性与可复现（V0.4.1）

每次 `play` 保存一份完整运行记录到 `output/runs/<run_id>.json`，包含
`cue / cue_directives / prompt / context / take / evaluation / conductor_advice`。
固定随机种子时即兴决策可复现（模型采样另有随机性）；`--show-prompt` 打印的就是
实际调用模型的同一份 prompt。`history` 命令基于这些记录做排序、筛选与趋势统计。

## 结构即兴引擎（V2.0）

以 `BookPlan` 为中心的创作流程（正文 `Take` 仍保留，用于局部演练）：

```
前提
 └─ StoryIdea × N   ── engine/book_planner.py   故事级即兴（发散实质不同的故事方案）
     └─ BookPlan    ── engine/outline_expander.py 逐级展开为分卷 + ChapterPlan 章节卡片
         └─ 校验    ── engine/plot_validator.py / structure_evaluator.py（六维 + 具体问题）
             └─ 局部重新即兴（受锁定保护）
```

- `core/story_idea.py · volume_plan.py · chapter_plan.py · book_plan.py` — 结构数据模型（含 `status/locked` 与下游影响追踪）。
- 结构参数（`data/story.yaml` 或命令行）：`idea_divergence / causal_variation / character_agency /
  motif_transformation / revelation_delay / branch_count / continuity_strength`。
- 有真实模型时（opencode / openai）由模型产出结构与章节卡片；否则用**确定性生成器**离线跑通（可测试、可复现）。
- 结构评价独立于文本评价；留白与开放结局不会被机械扣分。
- **POV 分布**：`multi_pov` 平衡交错并避免视角长跑；`ensemble` 分配连续视角弧；关键转折章（高潮/收束/汇合…）收束到主角视角。
- **字段级锁定**：`ChapterPlan.locked_fields`——重生成时保留被锁字段；整章锁定时永不改写。
- **Jam Session（V0.7）**：`jam_session/` 顺序合奏——Director（方向与限制）→ Soloist（人物驱动的行动）→
  Observer（非中心细节／边缘视角）→ Editor（**给候选打分排序**、剔除矛盾与提前揭露、整合提案）。
  角色任务不同，不各自重写正文；Editor 只给**提案**，不自动升级为正式设定。`python main.py jam "..."`。
- **记忆与偏离检测（V1.0）**：`engine/memory.py`——轻量语义记忆（默认词典向量，可选 embedding）：
  相似章节检索、**近重复检测**、**主题漂移**、人物弧缺失、意象未使用、结构卡片提前揭露。
- **故事板导出**：`engine/report.py` 生成 `output/story_report.md` 与自包含 `output/story_report.html`
  （动机演变时间线 / 人物弧线图 / 线索伏笔面板 / 偏离检测）。`python main.py report --open`。
- **全书梗概**：`BookPlan.synopsis / opening_state / inciting_incident / central_turn / climax / resolution`——
  不看卡片也能理解故事为何这样发展、结尾如何回应。
- **硬约束注入规划**：世界规则/禁忌/人物认知/已确定事实/秘密在**创意、梗概、逐章展开**三个阶段共同生效
  （`BookPlan.constraints` 可追溯）；`generated_by` 标记 `llm` / `offline_template`。
- **分阶段 + 严格校验的 LLM 规划**：蓝图 → 逐卷章节卡片 → 严格校验（章数必须完全一致、字段非空），
  不满足则回退并**明确标记为离线模板**，绝不静默接受。
- **重新即兴 = 候选 → 采纳**：`engine/reimproviser.py` 先给候选（含改动字段），作者采纳后才写回；
  锁定章与锁定字段永不被覆盖。`expand_book` 也会拒绝在已有详细卡片时静默重写（需 `force`）。
- **两层校验**：结构硬校验（缺章/编号/断链/未回收线索）+ 可选**叙事审阅**（事件合理性/人物选择/冲突升级/
  结局回应，给出依据与章号）；界面**问题清单优先于分数**。
- **创意过期保护**：方案记录前提指纹，前提改动后 `ideas_stale` 会提示方案过期。

## 数据文件（乐谱）

- `data/story.yaml` — 主题旋律 + 叙事和声 + 即兴参数
- `data/characters.yaml` — 独奏者
- `data/motifs.yaml` — 动机及其意义演变（生成后自动更新）

`python main.py init --force` 可重新写入示例乐谱。

## 架构

```
core/
  theme.py       主题旋律         core/improviser.py  即兴简报(核心)
  character.py   人物 Solo        core/motif.py       动机追踪
  harmony.py     叙事和声
  story_state.py  故事状态(事实/认知/线索) core/improviser.py 即兴简报
improvisation/                     # 即兴层：受控的偏移
  improvisation_score.py  指挥台 + Cue(核心)
  operator_engine.py      叙事操作库(8种, V0.5 核心)
  randomizer.py           JazzSeed 随机种子
  motif_engine.py         动机变奏
  surprise_engine.py      受控意外(尊重故事状态)
  rhythm_engine.py        叙事节奏
  solo_engine.py          人物 Solo
engine/
  composer.py    取一次 Take      evaluator.py   回听评价(含文学信号)
  variation.py   多版本变奏       scene_planner.py 下一章场景骨架
  textutil.py    轻量文本分析     semantic_similarity.py 可选语义评价
feedback/
  theme_check.py / character_check.py / novelty_check.py
  conductor.py   重调乐谱(自适应)
llm/
  base.py        接口            mock.py 离线    openai_provider.py 真实模型
session.py       乐队装配         store.py 读写(含 runs/state)  cli.py 命令行
tests/           确定性/记录/连续性/反馈 回归测试
output/
  chapters/      章节正文(.md)     runs/  完整运行记录(.json)
  advice_history.jsonl  参数建议与变更记录
data/
  story.yaml characters.yaml motifs.yaml story_state.yaml [jazz_state.yaml]
```

## 设计原则

1. **硬约束 vs 软约束**：世界规则、时间线、人物经历不可违反；描述方式、场景顺序、对话风格可自由变奏。
2. **主题不可直说**：只通过细节与意象让主题"被听见"。
3. **人物驱动而非情节驱动**：同一事件经过不同人物的即兴规则，产生不同故事。
4. **动机变奏**：每个核心意象出现时给出新意义，杜绝同义复读。
5. **受控偏移**：即兴不是随机；所有偏离都由 `Cue` 约束，并可在回听后回调。

## 定位

> **Human-AI Improvisational Writing System（人机即兴写作系统）**

作者提供主题与世界 → AI 提供即兴变化 → 作者挑选最佳演奏片段 → 系统维持长期主题一致性。
更接近爵士合奏与即兴戏剧，而非传统写作助手。

## 路线图

- V0.2 ✅ 可插拔 LLM（mock / OpenAI 兼容）
- V0.3 ✅ 回听评价 + 多 Take
- V0.4 ✅ 即兴层：乐谱参数 / 受控意外 / 动机变奏 / 回听重调
- V0.4.1 ✅ 可观测性：完整运行记录 `output/runs` / `history` 趋势 / `--show-prompt` 一致 / 可选语义评价 / 回归测试
- V0.5 ✅ 叙事即兴引擎：`ImprovisationOperator` 操作库 / 故事状态感知的意外 / 多路径探索(Mode B)
- V0.6 ◑ 长篇记忆与闭环：`StoryState` 故事圣经 / `scene_planner` 场景骨架 / `Conductor` 可撤销参数闭环 / 文学回听信号（向量记忆待做）
- **V2.0 ✅ 定位转向「结构即兴引擎」**：`BookPlan/VolumePlan/ChapterPlan` + 故事级发散 +
  结构校验（六维/问题式）+ 锁定与影响追踪 + 结构工作台 GUI（并发安全）+ 结构导出；正文生成降级为可选。
- **V2.1 ✅ 融合 / 卡片编辑 / 范围重生成**。
- **V2.2 ✅ POV 分布优化 + 字段级锁定 + Jam Session（V0.7）**。
- V0.7 ✅ Jam Session：Director + Soloist + Observer + Editor 顺序合奏（Editor 候选打分排序）。
- **V2.3 ✅ 记忆与偏离检测 + 故事板导出（动机时间线 / 人物弧线 / 伏笔面板）**。
- **V2.4 ✅ 重新即兴候选/采纳 + 硬约束注入规划 + 分阶段严格章数校验 + 全书梗概 + 两层校验 + 创意过期保护**。
- V1.0 ◑ 轻量语义记忆与偏离检测已实现（词典向量 + 可选 embedding）；剩余：真正的向量库与交互式可视化编辑器。

核心循环：**设定 → 即兴决策 → 生成多个可能性 → 回听与比较 → 作者选择 → 更新故事状态 → 下一轮即兴。**
