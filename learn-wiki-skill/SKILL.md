---
name: learn-wiki-skill
description: 以问题为核心的学习 Wiki 构建技能。融合「学习架构A」（顶层核心问题→领域公式→三元组「问题→符号→知识点」→从根到叶）与「llm-wiki」（增量持久化知识库）。当用户想要"学习某领域""建立学习知识库""以提问方式学习""把知识组织成问题驱动架构""用问题清单自测""学习架构A教学"时触发。使用时应先提炼领域公式与 Mermaid 协同架构图，再将知识点作为三元组挂载到协同节点。
---

# Learn Wiki Skill — 问题驱动的学习 Wiki

学习不是"读百科"，而是**检索练习**：先被问题卡住，再去找答案，记忆才牢固。本技能让 Wiki 成为"习得"工具——每一页都从一个问题出发，知识全部挂载到唯一的协同架构上。

## 何时使用本 Skill

- 用户要"学习/学会"某领域、想把资料变成学习系统
- 用户要以"提问/问题清单/自测"方式学习
- 用户要求按「学习架构A」教学（顶层核心问题、领域公式、Mermaid 架构图）
- 用户有资料（本地文件或 IMA 知识库）想增量沉淀为学习 Wiki

> 若用户只是想"存资料、查资料"，应改用 `llm-wiki-skill`。本技能专为**习得**而非查阅。

## 核心模型（三层）

```
第 1 层 根：领域公式页  ── 顶层核心问题 + 领域公式 + Mermaid 协同架构图
第 2 层 干：三元组单元  ── 问题 → 符号 → 知识点（定位 + 协同演示）
第 3 层 叶：问题索引    ── 从根到叶的问题清单（学习入口 / 自测）
```

- **第 1 层**：每个领域只维护一个根公式 `领域 ≝ ⟨要素1, 要素2, …⟩`，禁止引入平行核心。
- **第 2 层**：每个知识点以三元组组织，必须包含「定位」（挂载在哪个节点/协同线）与「协同演示」（符号链）。
- **第 3 层**：问题索引按"从根到叶"排序，标记掌握状态，是学习与复习的入口。

**详细规范**（必须遵守）：
- 学习架构 A 完整定义与 7 条教学要求 → [references/learning-architecture.md](references/learning-architecture.md)
- Wiki 目录结构与页面格式模板 → [references/wiki-layout.md](references/wiki-layout.md)
- 摄入 / 查询 / 复习 / 健康检查流程 → [references/workflows.md](references/workflows.md)
- 如何设计高质量问题 → [references/question-design.md](references/question-design.md)
- 初始化脚手架脚本 → `scripts/init-wiki.py`

## 工作流概览

### A. 建立新的学习 Wiki（尚未有）

```bash
python <skill-dir>/scripts/init-wiki.py --path <项目目录> --domain "<领域名>"
```

脚本自动生成：`index.md`、`log.md`、`WIKI-SCHEMA.md`、`wiki/00-领域公式.md`、`wiki/01-问题索引.md` 骨架。

随后**第一步必须**：
1. 确定**顶层核心问题**
2. 提炼**领域公式**并输出 **Mermaid 分层协同架构图**（写入 `00-领域公式.md`）
3. 创建 `01-问题索引.md` 的初版问题清单

### B. 摄入资料（增量学习）

每摄入一份资料，执行完整闭环（详见 [workflows.md](references/workflows.md)）：
判断资料源 → 定位挂载点 → 提炼三元组 → 更新问题索引 → 必要时修订领域公式 → 记录日志 → 健康检查

### C. 查询与自测

从 `01-问题索引.md` 找问题 → **先自答**（检索练习）→ 对照节点页答案 → 答错的沿协同链回溯到根 → 有价值问答归档为三元组。

### D. 间隔复习

问题索引标注掌握日期，按 1/3/7/30 天复查；只问不看答案，答对标记 `[x]`，答错降级并补强。

## 教学要求（速记）

公式先行+图示并列 / 三元组教学 / 协同链回顾 / 单一理论核心 / 符号化优先 / 从根到叶 / 鼓励重画协同图。完整版见 [references/learning-architecture.md](references/learning-architecture.md) 的「对 LLM 教学的要求」。

## 资料源双模式

- **本地文件模式**：源文件存入 `raw/`，直接读取。
- **IMA 向量库模式**：用 ima-skill 的 `search_knowledge` 向量检索识别内容，仅登记 `raw/源文件清单.md`，不下载源文件。详见 [references/workflows.md](references/workflows.md)。

## 相关参考

- 本 skill 融合自：`llm-wiki-skill`（持久化与链接规则）、学习架构 A（问题驱动教学法）。
- 创建规范：参照 `skill-creator` 的渐进式加载原则（SKILL.md 精简、references 按需加载、scripts 确定性执行）。
