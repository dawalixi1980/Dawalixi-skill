---
name: knowledge-weave
description: 渐构·织知（Knowledge Weave）。以「我的问题」为起点，用四拍织网：Push 推问 → Top 顶（基于我已理解）→ Link 连（[[双向链接]] 挂到 Wiki）→ Verify 验（以 Learn 为锚点校验）。产出四件：问题库 / 知识清单 / 详细知识 / 大纲骨架。当用户说「我想搞懂 X」「从现象 / 问题出发」「知识组网 / 织网」「渐构」「weave」，或希望以问题链展开知识时使用。调用 math-render 出公式图、乐享知识库做佐证。
---

# knowledge-weave · 渐构织知

> 一问引一问，一点连一点。　*questions spawn questions, points link to points.*

## The Loop · 四拍

| 拍 | 中文 | 做什么 | 产出 |
|:--:|:--:|---|---|
| **Push** | 推问 | 提一个问题（**你问或我问**，须立在你已理解之上） | 问题库一条 |
| **Top** | 顶 | 用已会的去顶；顶得动→过，**顶不动→这里是边界** | 边界 / 缺口 |
| **Link** | 连 | 新知识原点用 `[[双向链接]]` 挂到网；问题页记「长出 N 点」 | 详细知识 ＋ 链接 |
| **Verify** | 验 | 用 **Learn** 骨架查漏 ＋ 现实锚点（物）核验 | 大纲骨架更新 |

> 顶不动怎么处理、"物"锚点 → [references/ptlv.md](references/ptlv.md)

## The Weave · 链式推进

一个问题衍生下一个，再下一个（约 **3–4 问**），知识点随之展开：

```
Q1（现象） → Q2（由 Q1 衍生） → Q3 → …  → 知识原点铺开成网
```

## The Vault · 产出结构

| 文件 | 角色 |
|---|---|
| `00-问题库.md` | 我的问题（起点，链式） |
| `01-知识清单.md` | 全部知识原点（索引） |
| `02-详细知识/<名>.md` | 点进去的知识点详解（`[[双向链接]]`） |
| `03-大纲骨架.md` | 网络骨架（主观主干 ＋ 教材目录） |

> 结构细则 → [references/schema.md](references/schema.md)　｜　模板 → [references/templates.md](references/templates.md)

## Toolkit · 工具

- **Math**（`math-render`）：公式 / 图 → PNG
- **Wiki**：`[[双向链接]]` 知识网本体
- **Learn**：作为校验锚点

> 用法 → [references/tools.md](references/tools.md)

## Style · 风格

中英结合，克制而雅。SKILL.md 只留**骨架与指针**，细节下沉到 references。

## References

| 文件 | 何时读 |
|---|---|
| [references/ptlv.md](references/ptlv.md) | 每次织网 |
| [references/schema.md](references/schema.md) | 建库 / 归档 |
| [references/templates.md](references/templates.md) | 写文件时 |
| [references/tools.md](references/tools.md) | 调工具时 |
