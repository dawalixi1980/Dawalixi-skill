---
name: pdf-drawings
description: 读施工图/设计图纸类 PDF（A3-A0 图纸、图框、图纸目录、设计说明），定位到具体图号那一页并低成本看图。当用户提到施工图、图纸、图框、图纸目录、图号、看图、读图、平面图、横断面、大样图、系统图、节点详图、设计说明、初设、CAD 导出的 pdf，或要求"从这份图纸里找某某图/查某个做法/核对某个尺寸"时使用。也适用于任何"PDF 太大不想整本读、只想看其中几页"的场景。
---

# 读施工图 PDF

本机模型能看图但**不能直接读 PDF**（Read 一个 .pdf 会报 "this model does not support pdf input"）。
所以一切都要先转图。本 skill 解决的正是「怎么花最少的 token 找到该看的那一页」。

## 核心事实（别凭直觉，这是实测的）

| 事实 | 数值 |
|---|---|
| 图片输入计费 | **每张图封顶 384 token**，与像素多少无关 |
| 密排正文转文本 | 约 1500–3000 token/页（比图片贵） |
| 施工图文本层 | 约 100–140 字/页，**只有图号**，图名是栅格图 |
| 设计说明页文本层 | 约 1000+ 字/页 |
| 图框位置 | **页面最底部、横贯全宽**；图号常在右下 x≈0.86W, y≈0.92H |
| 拼图上限 | 单格 ≥1400px 宽、整图 ≤3000px 宽时图框字可读；再小就读不清 |

**推论：先做 0 token 的本地索引，再只渲染要看的那几页。绝不整本转图。**

## 三步工作流

### 第 1 步：体检（0 token）
```
python <skill>/scripts/probe.py 图纸.pdf
```
看 `索引路线` 和 `成本预估`。它会告诉你走 toc / 图框文字 / 还是必须视觉兜底。

### 第 2 步：建索引（0 token，关键）
```
python <skill>/scripts/index.py 图纸.pdf -o idx.json
```
自动三级回退：**书签 → 图纸目录页 → 逐页图框文字**。
产出「图号/图名 → PDF 页码」映射，全本地，不调模型。

拿到索引后，把用户的问题对到页码上。例如用户说「看路基防护设计图」→ 索引里查到 `p52 DL-07 路基防护工程设计图`。

### 第 3 步：按需看图（每次几百 token）
```
# 通读某一页（看整体布局、尺寸标注）
python <skill>/scripts/render.py 图纸.pdf --page 52 --box full --dpi 150

# 只读图框（索引里图名缺失时补图名）
python <skill>/scripts/render.py 图纸.pdf --page 52 --box auto --dpi 200

# 看细部（低 DPI 通读后，裁剪局部高 DPI 复核尺寸）
python <skill>/scripts/render.py 图纸.pdf --page 52 --crop 0.05,0.10,0.45,0.40 --dpi 400
```
然后用 Read 工具读输出的 png。

**图名缺失很多页时，用拼图**（本 skill 最省 token 的一招）：
```
python <skill>/scripts/render.py 图纸.pdf --sheet --box auto --pages 16-23 \
       --cols 2 --sheet-width 1400 --dpi 150
```
一张图装 8 个图框 = 384 token；逐张渲染要 3072。**务必遵守 `--cols 2 --sheet-width 1400`**，
这是实测的可读下限，贪多会糊成一片。

## 区域预设

`--box` 可选：`auto`（按图号/图名文字坐标自动定位，推荐）、`titleblock`（右下图号图名）、
`titleblock_l`（整条图框含工程名称）、`notes`（上半页，说明常在这）、`full`（整页）、
`center`（图面主体）。用 `render.py --boxes` 查看全部。

## 硬规则

1. **不要 `Read` 一个 .pdf** —— 一定会失败。先 `probe.py`。
2. **不要整本转图**。先 `index.py`，再挑页。89 页全转 = 34K token，索引后通常 <2K。
3. **不要一次性渲染超过 10 页**，超了就用 `--sheet`。
4. **拼图别贪**：`--cols 2 --sheet-width 1400` 是实测可读下限。
5. **索引里的图号要抽检**：图框文字是按坐标和正则猜的，低置信条目用
   `--box auto` 渲染该页图框复核一次再用。
6. **要精确尺寸/金额/编号时，一定裁剪局部高 DPI 复核**，别信 150 DPI 整页看出来的数字。

## 让路给别的 skill

合并、拆分、加水印、填表单、加密 —— 属于结构操作，用 `anthropics/skills` 的 `pdf` skill。
本 skill 只负责「看」。

详见 `reference/tactics.md`（含各案例实测数据与失败模式）。
