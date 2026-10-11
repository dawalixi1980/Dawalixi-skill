# 工具与链接规范

## 一、math-render（公式 / 图）

```bash
node <math-render>/scripts/render_formula.js "<latex>" -o <项目>/知识点/img/<名>.png
python <math-render>/scripts/render_plot.py spec.json -o <项目>/知识点/img/<名>.png
```

- 公式 / 函数图 → 放进该知识点 `img/`，正文用 `./img/<名>.png` 相对路径嵌入。
- 图中文字用 LaTeX / 简单文本，避免生僻字符。

## 二、乐享（取证佐证）

| 目的 | 工具 |
|---|---|
| 关键词检索 | `search_kb_search` |
| 语义检索 | `search_kb_embedding_search`（`filters.keyword`） |
| 读正文 | `entry_describe_ai_parse_content` |
| 定库 | `space_list_spaces` / `team_list_teams` |

- 出处格式：**《文档名》** ＋ 链接 ＋（检索日期）。
- 401 → 不重试，转 `lexiang-setup`。
- 无结果 → 明说"未检索到"。

## 三、`[[双向链接]]` 规范（本 skill 采用）

- 用 Obsidian 原生 `[[双向链接]]`（不是相对路径）。
- **谁被谁引用，都要能互相找到**：
  - 问题 ⇄ 知识点
  - 知识点 ⇄ 知识点（"相互印证"）
- 缺省即"未连"——**不连的知识点 = 孤立节点，不完整**。
