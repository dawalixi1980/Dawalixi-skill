#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""init-wiki.py — Initialize a question-driven learning Wiki scaffold.

Creates the directory structure and root pages required by learn-wiki-skill.

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
    dirs = ["raw", "wiki"]
    for d in dirs:
        os.makedirs(os.path.join(path, d), exist_ok=True)


def write(path, name, content):
    fp = os.path.join(path, name)
    if os.path.exists(fp):
        print(f"[skip] {name} already exists")
        return
    with open(fp, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[ok]   {name}")


def build_all(project, domain):
    ensure_dirs(project)

    write(project, "index.md", f"""# {domain} — 学习 Wiki

> 基于 learn-wiki-skill（问题驱动学习架构 + 增量持久化）建立。

## 顶层核心问题

**<{domain}要回答的根本性大问题>**

## 领域公式（待完善）

**{domain} ≝ ⟨要素1, 要素2, 要素3, …⟩** — 详见 [wiki/00-领域公式.md](wiki/00-领域公式.md)

## 开始学习

1. 先读 [wiki/00-领域公式.md](wiki/00-领域公式.md) 建立全局协同观
2. 再按 [wiki/01-问题索引.md](wiki/01-问题索引.md) 逐题学习（先自答后对照）
3. 资料登记见 [raw/源文件清单.md](raw/源文件清单.md)

## 分类导航

（随摄入补充）

## 元信息
- 创建日期：{TODAY}
""")

    write(project, "log.md", f"""# 操作日志

## [{TODAY}] 初始化 | 创建学习 Wiki
- 建立 {domain} 学习 Wiki 骨架（learn-wiki-skill）
""")

    write(project, "WIKI-SCHEMA.md", f"""# WIKI-SCHEMA — {domain}

由 learn-wiki-skill 管理。结构：
- `raw/` 资料登记（只读）
- `wiki/00-领域公式.md` 根（顶层核心问题 + 领域公式 + Mermaid 图）
- `wiki/01-问题索引.md` 问题清单（学习入口）
- `wiki/<分类>/<节点>.md` 三元组页

链接规则：标准相对路径，双向链接，导航栏必备。模板详见 learn-wiki-skill 的 references/wiki-layout.md。
""")

    write(project, "raw/源文件清单.md", f"""# 源文件清单 — {domain}

> 只读登记簿。本地模式存源文件副本；IMA 模式仅登记。

| 文件名 | 类型 | 位置 | 分类 |
|--------|------|------|------|
|（待登记）| | | |
""")

    write(project, "wiki/00-领域公式.md", f"""---
title: 领域公式：{domain}
type: root
created: {TODAY}
updated: {TODAY}
core: {domain} ≝ ⟨要素…⟩
tags: [领域公式, 顶层核心问题]
---

# {domain} — 领域公式

> **导航**: [← 返回总纲](../index.md) | [问题索引](./01-问题索引.md)

## 顶层核心问题

**<该领域要回答的根本性大问题>**

## 领域公式

**{domain} ≝ ⟨要素1, 要素2, 要素3, …⟩**

- 要素1：…
- 要素2：…
- 要素3：…

## 分层协同架构图

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

## 协同路径说明

（待填写：要素A → 要素B → … 的协同解释）

## 相关页面
- [← 返回总纲](../index.md)
- [问题索引](./01-问题索引.md)
""")

    write(project, "wiki/01-问题索引.md", f"""# 问题索引 — {domain}

> **导航**: [← 返回总纲](../index.md) | [领域公式](./00-领域公式.md)

从根到叶排列。复习时只看问题不看答案。

| # | 问题 | 答案位置 | 状态 |
|---|------|----------|------|
| 1 | <顶层核心问题> | [领域公式](./00-领域公式.md) | [ ] |
| 2 | <问题> | [分类/节点页](./分类/节点.md#q1) | [ ] |

**图例**：`[ ]` 待掌握 · `[x]` 已掌握（标日期）

## 掌握状态记录
- {TODAY}：建立初版清单
""")

    print(f"\nWiki scaffold created at: {project}")
    print("Next: fill top-level core question, domain formula + Mermaid diagram in wiki/00-领域公式.md")


def main():
    ap = argparse.ArgumentParser(description="Initialize a question-driven learning Wiki")
    ap.add_argument("--path", required=True, help="project directory")
    ap.add_argument("--domain", required=True, help="domain name, e.g. 道路工程")
    args = ap.parse_args()
    build_all(os.path.abspath(args.path), args.domain)


if __name__ == "__main__":
    main()
