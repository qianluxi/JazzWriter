# Novel Jazz Engine（小说爵士引擎）

> AI 不是打字机，而是乐队的即兴成员。作者不是在"让 AI 写小说"，而是和 AI 一起演奏一部长篇。

在固定结构（主题 / 和声 / 动机）下实时创造，生成多个 `Take`（一次演奏），
作者"回听"评价后再进入下一轮即兴。

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

## 使用

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

# 回听评价一个已保存的章节
python main.py evaluate output/chapters/ch001_take01_冷静观察.md

# 查看动机的意义演变轨迹
python main.py motifs

# 查看即兴参数与三种模式预设
python main.py jazz

# 查看可用即兴模式与 Solo 色彩
python main.py styles

# 无参数运行：离线演示
python main.py
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

**回听 → 重调**（`feedback/`）：`Conductor` 读评价结果给出下一轮参数建议——
创新太低则提高 `randomness`，偏离主题则降低自由度。作者始终选择保留哪段演奏。

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
improvisation/                     # 即兴层：受控的偏移
  improvisation_score.py  指挥台 + Cue(核心)
  randomizer.py           JazzSeed 随机种子
  motif_engine.py         动机变奏
  surprise_engine.py      受控意外(转调)
  rhythm_engine.py        叙事节奏
  solo_engine.py          人物 Solo
engine/
  composer.py    取一次 Take      engine/evaluator.py 回听评价
  variation.py   多版本变奏
feedback/
  theme_check.py / character_check.py / novelty_check.py
  conductor.py   重调乐谱(自适应)
llm/
  base.py        接口            mock.py 离线    openai_provider.py 真实模型
session.py       乐队装配         store.py 读写    cli.py 命令行
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
- V0.5 ⏳ Jam Session：导演 + 多人物 Solo + 旁白 + 编辑者（多智能体）
- V0.6 ⏳ 向量记忆：章节 embedding、偏离检测（`engine/textutil.py` 已留接口）
- V1.0 ⏳ 世界观编辑器 / 人物关系图 / 风格控制台
