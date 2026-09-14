#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""init-wiki.py — Initialize a D v4 learning-Wiki scaffold (learn-skill).

Layout: one knowledge point = one folder (index.md + img/). Images follow their
knowledge point. Input images live in raw/images/ with media/ text-cards.

Usage:
    python init-wiki.py --path <project-dir> --domain "<domain-name>"
"""

import argparse
import io
import os
import sys
from datetime import date

if sys.stdout and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TODAY = date.today().isoformat()


def ensure_dirs(path):
    for d in ["raw", "raw/images", "media", "wiki", "wiki/00-骨架/img", "wiki/应用"]:
        os.makedirs(os.path.join(path, *d.split("/")), exist_ok=True)


def write(path, rel, content):
    fp = os.path.join(path, *rel.split("/"))
    if os.path.exists(fp):
        print(f"[skip] {rel} already exists")
        return
    with open(fp, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[ok]   {rel}")


def build_all(project, domain):
    ensure_dirs(project)

    write(project, "index.md", f"""# {domain} — 学习 Wiki

> 由 learn-skill（学习架构 D v4：顶层整体 ＋ 贯穿地基）建立。

## 顶层核心问题

**<{domain} 要回答的根本大问题>**

## 骨架（顶层 ＋ 地基）

**{domain} ≝ ⟨要素1, 要素2, 要素3⟩** ＋ 地基元素 **<地基>**
→ 详见 [wiki/00-骨架/index.md](wiki/00-骨架/index.md)

## 开始学习

1. 先读 [wiki/00-骨架/index.md](wiki/00-骨架/index.md) 建立顶层整体观、锁定地基元素
2. 按 [wiki/01-问题索引.md](wiki/01-问题索引.md) 逐题学习（先自答后对照）
3. 自测缺口记入 [wiki/02-缺口账本.md](wiki/02-缺口账本.md)
4. 现实应用见 [wiki/应用/钉子表.md](wiki/应用/钉子表.md)
5. 资料登记见 [raw/源文件清单.md](raw/源文件清单.md)；图片图文卡见 [media/](media/)

## 分类导航

（随摄入补充）

## 元信息
- 创建日期：{TODAY}
""")

    write(project, "log.md", f"""# 操作日志

## [{TODAY}] 初始化 | 创建学习 Wiki
- 建立 {domain} 学习 Wiki 骨架（learn-skill / 架构 D v4）
""")

    write(project, "WIKI-SCHEMA.md", f"""# WIKI-SCHEMA — {domain}

由 learn-skill（学习架构 D v4）管理。结构：

- `raw/` 资料登记（只读；IMA 模式仅登记）；`raw/images/` 输入原图
- `media/<slug>.md` 图片图文卡（OCR/描述/洞察 → 可检索）
- `wiki/00-骨架/index.md` 顶层三件套 + 地基元素 + 连结关系图（图片在该页 img/）
- `wiki/01-问题索引.md` 从根到叶问题表（1/3/7/30 复习）
- `wiki/02-缺口账本.md` 第 2 遍自测的真缺口（open/resolved）
- `wiki/<分类>/<要素>/` 一个知识点＝一个文件夹（index.md + img/）
- `wiki/应用/钉子表.md` 现实问题穿针

链接规则：标准相对路径，双向链接，导航栏必备。
模板详见 learn-skill 的 references/wiki-layout.md、unit-template.md、media.md。
""")

    write(project, "raw/源文件清单.md", f"""# 源文件清单 — {domain}

> 只读登记簿。本地模式存源文件副本；IMA 模式仅登记，不下载。图片登记时"类型"写"图片"。

| 文件名 | 类型 | 位置 | 分类 |
|--------|------|------|------|
|（待登记）| | | |
""")

    write(project, "wiki/00-骨架/index.md", f"""---
title: 骨架：{domain}
type: skeleton
created: {TODAY}
updated: {TODAY}
core: {domain} ≝ ⟨要素1, 要素2, 要素3⟩
base_element: <地基元素>
base_kind: object | background | material
images: []
tags: [骨架, 顶层核心问题, 地基元素]
---

# {domain} — 骨架（顶层整体 ＋ 贯穿地基）

> **导航**: [← 返回总纲](../../index.md) | [问题索引](../01-问题索引.md) | [缺口账本](../02-缺口账本.md)

## 一、顶层核心问题
**<该领域要回答的根本大问题>**

## 二、顶层领域公式
**{domain} ≝ ⟨要素1, 要素2, 要素3⟩**，且 <协同箭头>

- 要素1（<符号>）：…（公式图放本页 img/，用 `![…](./img/…png)` 引用）
- 要素2（<符号>）：…
- 要素3（<符号>）：…

## 三、顶层协同图
```mermaid
flowchart LR
    subgraph 要素1
        e1[a]
    end
    subgraph 要素2
        e2[b]
    end
    e1 -->|数据流| e2
```

## 四、地基元素（贯穿基本元素）
- **地基**：<基本原子>（对象型 / 背景型 / 原料型）
- **判定**：删掉它，顶层每个要素都会 <…>；顶层每件事都作用在 / 相对 <…> 发生。
- **贯穿度自检**：

  | 顶层要素 | 作用于/相对主元素 | 关系 |
  |---|---|---|
  | 要素1 | ✅ | 对其实施 X 运算 |
  | 要素2 | ✅ | 相对它成立 |
  | 要素3 | ✅ | 由它组成 |

## 五、连结关系图（顶层 ⇄ 地基）
```mermaid
flowchart TB
    subgraph BOT["底层：贯穿基本元素"]
        E[<地基元素> ⭐]
    end
    subgraph TOP["顶层：整体"]
        T1[要素1]
        T2[要素2]
        T3[要素3]
    end
    E -->|"作用于/相对/由它组成"| T1
    E -->|"作用于/相对/由它组成"| T2
    E -->|"作用于/相对/由它组成"| T3
```
**双向标注**：底→顶 <地基是哪些要素的共同对象/前提>；顶→底 <每个要素都是对地基的什么运算/关系>。

## 相关页面
- [← 返回总纲](../../index.md)
- [问题索引](../01-问题索引.md)
- [<要素1>页](../<分类>/<要素1>/index.md)
""")

    write(project, "wiki/01-问题索引.md", f"""# 问题索引 — {domain}

> **导航**: [← 返回总纲](../index.md) | [骨架](./00-骨架/index.md)

从根到叶排列。复习时**只看问题不看答案**。

| # | 问题 | 答案位置 | 状态 | 复习记录 |
|---|------|----------|------|----------|
| 1 | <顶层核心问题> | [骨架](./00-骨架/index.md) | [ ] | |
| 2 | <地基元素是什么？> | [骨架](./00-骨架/index.md) | [ ] | |
| 3 | <机制型问题：要素如何作用在地基上？> | [要素页](./<分类>/<要素>/index.md#q1) | [ ] | |

**图例**：`[ ]` 待掌握 · `[x]` 已掌握
**复习节拍**：掌握后按 1 / 3 / 7 / 30 天复查。

## 掌握状态记录
- {TODAY}：建立初版清单
""")

    write(project, "wiki/02-缺口账本.md", f"""# 缺口账本 — {domain}

> 第 2 遍"下山自测"时，只看顶层公式却推不出的点。open → resolved。

| # | 缺口（推不出的地方） | 关联要素/地基 | 状态 | 补强动作 | 日期 |
|---|----------------------|---------------|------|----------|------|
| | | | | | |
""")

    write(project, "wiki/应用/钉子表.md", f"""# 钉子表 — {domain}

> 现实问题穿针。每个顶层要素 2–3 个"答案有意义"的问题。

| 现实问题 | 顶坐标（要素） | 底坐标（地基） | 为何答案有意义 |
|---|---|---|---|
| | | | |
""")

    print(f"\nWiki scaffold created at: {project}")
    print("Next: fill 顶层核心问题 + 领域公式 + 协同图 + 地基元素 in wiki/00-骨架/index.md")


def main():
    ap = argparse.ArgumentParser(description="Initialize a D v4 learning-Wiki scaffold")
    ap.add_argument("--path", required=True, help="project directory")
    ap.add_argument("--domain", required=True, help="domain name, e.g. 微积分")
    args = ap.parse_args()
    build_all(os.path.abspath(args.path), args.domain)


if __name__ == "__main__":
    main()
