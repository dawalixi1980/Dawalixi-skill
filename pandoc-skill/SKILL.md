---
name: pandoc-skill
description: |
  将 Markdown 文件转换为格式规范的 Word 文档 (.docx)，基于内置 pandoc-A3.docx 模板渲染。
  自动清洗标题中的编号前缀（如 1. / 1.1 / 一、等），仅保留 # 语法标识的纯文本标题。
agent_created: true
---
# pandoc转换 — Markdown to A3-styled Word

## 概述

本技能将 Markdown 文件通过 Pandoc 转换为基于内置 `pandoc-A3.docx` 模板的 Word 文档。模板已嵌入技能目录（`./pandoc-A3.docx`），定义了页面布局（A3纸张）和各级标题/正文/表格的样式，转换后文档可直接用于打印或提交。

## 技能结构

```
pandoc-skill/
├── SKILL.md           ← 本文件
└── pandoc-A3.docx     ← A3 Word 模板（已嵌入）
```

## 触发词

"转Word"、"转docx"、"pandoc"、"pandoc转换"、"Markdown转换"、"生成Word"

## 前置条件

- **Pandoc** 已安装（路径：`/c/Program Files/Pandoc/pandoc`）
- **pandoc-A3.docx** 模板已嵌入本技能目录，路径：`{SKILL_DIR}/pandoc-A3.docx`

## Markdown 格式强制约束

### 标题规则（核心）

```
✅ 正确 — 仅用 # 语法，无编号前缀：
# 项目总论与基础认知
## 项目概况
### 项目基本概况

❌ 错误 — 含编号前缀，禁止：
# 第一章 项目总论与基础认知
## 1.1 项目概况
### 1.1.1 项目基本概况
### 一、项目基本概况
```

**修复规则**：转换前自动扫描并清洗标题中的编号前缀。清洗后写入临时文件进行转换，原文件不做任何修改。

### 表格规则

```
标准 GFM 表格语法：

| 列1 | 列2 | 列3 |
|-----|-----|-----|
| 数据 | 数据 | 数据 |

*表 1 示例表格标题*
```

### 图片规则

```
![图片描述](路径/或URL)

*图 1 示例图片标题*
```

### 段落规则

- 正文直接书写，段落间空一行
- 不依赖编号列表（`1.`, `-`, `*`）作为主要叙事结构
- 信息以连贯段落自然叙述

## 工作流程

### 步骤一：自动清洗标题编号

扫描输入 Markdown 文件，自动去除标题中的编号前缀：

```
清洗前：
# 第一章 项目总论与基础认知
## 1.1 项目概况
### 1.1.1 项目基本概况
### 一、区域地理位置
## 2. 背景分析

清洗后：
# 项目总论与基础认知
## 项目概况
### 项目基本概况
### 区域地理位置
## 背景分析
```

**清洗规则（按顺序匹配）**：
1. 去除 `第X章` / `第X节` 前缀（含空格）
2. 去除 `X.X` / `X.X.X` 数字编号（含末尾 `、`）
3. 去除 `X.` 单级数字编号（含空格）
4. 去除 中文序号（一、二、三… 至 二十、）
5. 去除 `X）` / `(X)` 括号编号前缀

使用 Python 一键清洗，生成临时干净文件后转换，**不修改原文件**。

```bash
python3 -c "
import re, sys
content = sys.stdin.read()

def clean_heading(line):
    original = line
    # 匹配 markdown 标题标记 + 空格
    m = re.match(r'^(#+ )(.*)$', line)
    if not m:
        return line
    prefix, text = m.group(1), m.group(2)
    # 按顺序清洗
    text = re.sub(r'^第[一二三四五六七八九十百千\d]+章\s*', '', text)
    text = re.sub(r'^第[一二三四五六七八九十百千\d]+节\s*', '', text)
    text = re.sub(r'^\d+\.\d+\.\d+[\.\s、]*', '', text)
    text = re.sub(r'^\d+\.\d+[\.\s、]*', '', text)
    text = re.sub(r'^\d+[\.\s、)]+', '', text)
    text = re.sub(r'^[一二三四五六七八九十]+[、.]?\s*', '', text)
    text = re.sub(r'^\([^)]+\)\s*', '', text)
    return prefix + text

lines = content.split('\n')
cleaned = [clean_heading(l) for l in lines]
for line in cleaned:
    print(line)
" < 输入文件.md > 清洗后_temp.md
```

### 步骤二：执行转换

```bash
SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
pandoc "清洗后_temp.md" \
  -o "输出文件.docx" \
  --reference-doc="$SKILL_DIR/pandoc-A3.docx" \
  --metadata title="技术方案" \
  --from markdown+raw_tex \
  --to docx \
  --toc \
  --toc-depth=3 \
  --wrap=preserve
```

| 参数 | 含义 |
|------|------|
| `--reference-doc` | 使用 A3 模板定义页面布局与样式 |
| `--toc` | 自动生成目录 |
| `--toc-depth=3` | 目录深度3级（`#`、`##`、`###`） |
| `--from markdown+raw_tex` | 支持原始 TeX（数学公式等） |
| `--wrap=preserve` | 保留原文换行 |

### 步骤三：验证输出并清理

```powershell
Get-Item "输出文件.docx" | Select-Object Name, Length
Remove-Item "清洗后_temp.md"
```

## 批量转换

技能目录下使用 `$SKILL_DIR` 变量引用模板：

```bash
SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"

# 单文件转换
pandoc 输入.md -o 输出.docx \
  --reference-doc="$SKILL_DIR/pandoc-A3.docx" \
  --toc --toc-depth=3 \
  --from markdown+raw_tex --to docx --wrap=preserve

# 批量转换
for f in *.md; do
  pandoc "$f" -o "${f%.md}.docx" \
    --reference-doc="$SKILL_DIR/pandoc-A3.docx" \
    --toc --toc-depth=3 \
    --from markdown+raw_tex --to docx --wrap=preserve
done
```

## 故障排除

| 错误现象 | 原因 | 解决 |
|----------|------|------|
| `pandoc: not found` | Pandoc 未安装 | 安装 Pandoc ≥ 3.0 |
| `Could not find reference doc` | 模板路径错误或文件不存在 | 确认技能目录下 `pandoc-A3.docx` 存在，`$SKILL_DIR` 变量正确 |
| 转换后目录编号错乱 | Markdown 标题含手动编号，清洗未覆盖 | 检查清洗后_temp.md 确认编号已清除，补清洗规则后重试 |
| 表格丢失或变形 | 表格语法非标准 GFM | 修复表格 `|` 分隔符 |
| 图片不显示 | 图片路径无效 | 使用绝对路径或确保相对路径正确 |
