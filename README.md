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
| Take 录音 | 一次生成的多版本章节 |
| Listen-back 回听 | `Evaluator` 一致性/新鲜度评价 |

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
python main.py play "冬夜，学校食堂，一台报废的蒸汽机仍在运行" --pov 林 --mode classic --style 冷静观察

# 同一场景生成多个版本（多 Take 变奏）
python main.py takes "同上" --styles 冷静观察 象征增强 心理深入

# 回听评价一个已保存的章节
python main.py evaluate output/chapters/ch001_take01_冷静观察.md

# 查看动机的意义演变轨迹
python main.py motifs

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

## 数据文件（乐谱）

- `data/story.yaml` — 主题旋律 + 叙事和声
- `data/characters.yaml` — 独奏者
- `data/motifs.yaml` — 动机及其意义演变（生成后自动更新）

`python main.py init --force` 可重新写入示例乐谱。

## 架构

```
core/
  theme.py       主题旋律         core/improviser.py  即兴简报(核心)
  character.py   人物 Solo        core/motif.py       动机追踪
  harmony.py     叙事和声
engine/
  composer.py    取一次 Take      engine/evaluator.py 回听评价
  variation.py   多版本变奏
llm/
  base.py        接口            mock.py 离线    openai_provider.py 真实模型
session.py       乐队装配         store.py 读写    cli.py 命令行
```

## 设计原则

1. **硬约束 vs 软约束**：世界规则、时间线、人物经历不可违反；描述方式、场景顺序、对话风格可自由变奏。
2. **主题不可直说**：只通过细节与意象让主题"被听见"。
3. **人物驱动而非情节驱动**：同一事件经过不同人物的即兴规则，产生不同故事。
4. **动机变奏**：每个核心意象出现时给出新意义，杜绝同义复读。

## 路线图

- V0.2 ✅ 可插拔 LLM（mock / OpenAI 兼容）
- V0.3 ✅ 回听评价 + 多 Take
- V0.4 ⏳ 向量记忆：章节 embedding、偏离检测（`engine/textutil.py` 已留接口）
- V1.0 ⏳ 世界观编辑器 / 人物关系图 / 风格控制台
