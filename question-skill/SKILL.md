---
name: question-skill
description: 提问式答疑技能（QuestionSkill）。当用户在看书/读资料遇到疑惑并提问（常附截图）时使用：先标明问题出自哪本书·哪一章，检索乐享知识库与教材佐证，再用物理/力学情境（优先力学＋计算机）把概念讲清楚（必要条件），最后归类归档。触发词：我有个问题、这里看不懂、这步怎么来的、为什么会这样、帮我理解一下、结合知识库、对照这个截图、书上是这么写的。
---

# question-skill — 从「疑问」到「有据可查的答案」

> 核心链路：**你提问 → 标出处 → 检索佐证 → 用物理/力学讲清 → 双归档（问答库 ＋ wiki）**。
> 前置场景：你正在**看书、获取概念**，需要**理解我输出的知识**。答案不散落在对话里，而是沉淀成可回查的 Wiki。

## 相关 skill 分工（不要重复造）

| Skill | 职责 |
|---|---|
| **question-skill（本件）** | 答疑编排层：接题 → 标出处 → 检索佐证 → 苏格拉底式讲清 → 归类 |
| `lexiang-search` / `lexiang-setup` | 乐享知识库检索与连接（未配置时走 setup） |
| `math-render` | 公式 / 函数图 → PNG（终端不渲染 LaTeX） |
| `learn-skill` | 系统建库底座：顶层架构、分层、要素页（**共用同一套 wiki 结构**） |
| `llm-wiki-skill` | 目录 / 链接规范 |

> 与 learn-skill 的关系：learn-skill 从上往下**建库**；本 skill 从下往上**答疑并回填**。共用 `library/ raw/ wiki/ log.md` 底座。

## 触发条件

用户**产生疑问并提问**，常见信号：`我有个问题` · `这里看不懂` · `这步怎么来的` · `为什么…` · `帮我理解` · `结合知识库` · `对照截图` · `书上是…`，通常**附一张截图**。

## 回答铁律（三条，最重要）

> [!important] ① 先标出处
> 解答**前**，先一句话说明这个问题**出自哪本书 · 第几章 · 哪个知识点**；再解答；最后**归类**。
> 出处不明 → 先问用户，不要瞎猜。

> [!important] ② 物理佐证（必要）
> 回答**任何概念**，必须先用一个**物理 / 力学情境**（具体、可算、带单位）把它「演」出来。
> **举例优先：① 力学 → ② 计算机**（见 [references/grounding.md](references/grounding.md)）。**不写纯理性板块。**
> 没有情境的概念解释 = **不合格**。

> [!important] ③ 双归档
> 解答后**双归档**：**问题＋答案** → `问答知识库/`；**提炼的纯概念 / 定义** → `wiki/`。不散落在对话里。

## 核心循环（六拍）

| 拍 | 动作 | 产出 |
|:--:|---|---|
| ① **接题** | 读**截图**（OCR＋公式LaTeX＋描述＋洞察）＋疑问原话＋归档截图 | `raw/`（原图＋文字层） |
| ② **标出处** | 一句话说明**哪本书 · 第几章 · 哪个知识点**；先查本地 wiki 是否已答 | 出处卡 |
| ③ **检索** | 调**乐享**（关键词＋语义）；必要时查本地教材 | 候选材料 |
| ④ **佐证** | **截图 ↔ 乐享 ↔ 教材**三方交叉；标出处；冲突标注；无果降级 | 证据链 |
| ⑤ **作答** | **3 板块：① 问题 → ② 概念（答小问） → ③ 物理情景（力学/计算机）**；穿插公式图 | 解答 |
| ⑥ **双归档** | 原始「问+答」→ `问答知识库/`；**提炼纯概念** → `wiki/<章>/<概念>/`；双向链接 | 沉淀 |

> 详细步骤见 [references/workflow.md](references/workflow.md)。

## 检索与佐证

乐享工具、出处标注、冲突处理、无结果降级、下载文件归档见 [references/citation.md](references/citation.md)。

## 归档规范（详见 [references/archiving.md](references/archiving.md)）

| 产物 | 位置 |
|---|---|
| 3 点（核心问题 / 整体架构 / 核心要素） | `index.md` **顶部** |
| 问答目录 ＋ 知识库目录 | `index.md` 下半 |
| 书籍 / 乐享下载 | `library/books/` ／ `library/lexiang/<来源库>/` |
| 截图（原图＋文字层） | `raw/` |
| **问答记录（原始层：问＋答＋情景）** | `问答知识库/YYYYMMDD-<slug>.md`（目录：`问答知识库/index.md`） |
| **概念页（提炼层：纯定义）** | `wiki/<章>/<概念>/index.md` |
| 生成的公式 / 函数图 | `wiki/<章>/<概念>/img/` |
| **符号表（★ 永久保留）** | `wiki/符号表.md` |
| 存疑清单（轻量） | `wiki/02-缺口账本.md` |
| 操作日志 | `log.md` |

## 回答模板

问答记录模板见 [references/answer-template.md](references/answer-template.md)（3 板块）；wiki 纯概念页模板见 [references/concept-template.md](references/concept-template.md)。

## 反模式 & 质量自查

| 反模式 | 自查项 |
|---|---|
| **不标出处、不先说哪本书哪一章** | [ ] 出处卡在最前 |
| 不检索直接答（幻觉） | [ ] 乐享已检索且有出处 |
| 不标出处 | [ ] 截图 / 乐享 / 教材出处齐全 |
| **只讲纯概念、没有物理/力学情境** | [ ] 已有具体可算的情境（优先力学/计算机） |
| 不双归档 | [ ] 问答记录 + 纯概念页 都写好，且双向链接 |
| 一次答多问 | [ ] 一问一单元 |
| 截图公式不复现 | [ ] 公式已渲染 PNG 校验 |
| 覆盖旧版不记 log | [ ] `log.md` 已追加 |

## 边界 / 安全

- 依赖 `lexiang` MCP；未配置走 `lexiang-setup`。
- 乐享返回 **401** → 不重试，转 `lexiang-setup` 续期。
- 截图默认**仅本地**归档，不外传。
- 知识库内容可能过时 → 标注**检索日期**。

## 参考文档

| 文档 | 说明 |
|---|---|
| [references/workflow.md](references/workflow.md) | 六拍循环详解 |
| [references/grounding.md](references/grounding.md) | 物理佐证规范（力学/计算机优先） |
| [references/answer-template.md](references/answer-template.md) | 问答记录模板（3 板块） |
| [references/concept-template.md](references/concept-template.md) | 纯概念页模板（wiki） |
| [references/citation.md](references/citation.md) | 乐享检索 + 出处 + 冲突 + 降级 + 下载归档 |
| [references/archiving.md](references/archiving.md) | 两层归档 + 3 点 + 书目导航 + 文件分类 |
| [references/screenshot.md](references/screenshot.md) | 截图归档（放 raw/，原图＋文字层） |
