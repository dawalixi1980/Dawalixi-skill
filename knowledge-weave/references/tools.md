# Toolkit · 工具用法

## Math · math-render（公式 / 图）

```bash
node <math-render>/scripts/render_formula.js "<latex>" -o <项目>/02-详细知识/img/<名>.png
python <math-render>/scripts/render_plot.py spec.json -o <项目>/02-详细知识/img/<名>.png
```

- 公式 / 函数图 → 该知识点 `img/`，正文用相对路径嵌入。

## Wiki · `[[双向链接]]`

- 用 Obsidian 原生 `[[双向链接]]`。
- **问题 ⇄ 知识点**、**知识点 ⇄ 知识点**（相互印证），都要能互相找到。
- 不做目录层级，关系由链接决定。

## Learn · 校验锚点

- 用 Learn 的骨架（**主观主干 ＋ 教材目录**）给网络**查漏**。
- 标出：缺口 / 断链 / 待证。

## 乐享 · 佐证（可选）

- 检索：`search_kb_search` / `search_kb_embedding_search`
- 读正文：`entry_describe_ai_parse_content`
- 出处格式：**《文档名》** ＋ 链接 ＋（检索日期）
