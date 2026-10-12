---
name: dantuqiang
description: >-
  挡土墙设计/验算技能（对标理正岩土 DangTu）。当用户给出挡土墙断面图/计算简图/参数，要求做挡土墙验算、
  稳定性计算、生成挡土墙计算书，或提到：挡土墙、重力式/衡重式/悬臂式/扶壁式/半重力式/加筋土/桩板式/锚杆式/
  锚定板式/卸荷板式挡土墙、墙背/面坡/背坡、墙趾台阶、库仑土压力、主动土压力、滑动稳定 Kc、倾覆稳定 K0、
  偏心距、地基承载力、墙身截面强度、整体稳定、换算土柱、车辆荷载、理正/理正岩土/DangTu 时使用。
  能力：①理解用户给的图片（断面图）提取墙型与几何/材料/土/地基/荷载参数；②交互式问答补全缺失参数；
  ③按库仑土压力与公路规范自算（滑动/倾覆/地基应力与偏心距/截面强度/整体稳定）；④生成理正风格的 Word 计算书；
  ⑤力学不足时给出调整建议。执行标准默认公路（JTG D30-2015）。
  触发词：挡土墙、挡墙、挡土墙计算书、挡土墙验算、重力式挡土墙、库仑土压力、滑动稳定、倾覆稳定、挡土墙断面、
  retaining wall、gravity wall、Coulomb earth pressure。
---

# 挡土墙设计/验算（dantuqiang）

对标理正岩土 `DangTu`：理解图片 → 交互补参 → 自算 → 出理正风格 Word 计算书 → 提出建议。

## 工作流（按序执行）

### 第 1 步 · 读取输入
- 用户给**图片**（断面图/计算简图）：用你的视觉能力按 `references/parameters.md` 第 1 节逐项读图，
  提取墙型、执行标准、geometry、materials、soil、foundation、surface、荷载，并列成清单。
- 用户给**文字/表格**：同法整理。
- 用户给**理正导出文本/已有计算书**：从中提取“原始条件”各参数。

### 第 2 步 · 交互补全（重要）
- 对照 `references/parameters.md` 检查缺项与歧义；**不得臆造**。
- 用 question 工具一次问 3~5 个最关键项（墙型、执行标准、H 与坡比、φ/γ/δ、地基承载力 fa、墙底摩擦系数 f、
  是否有车辆/地震/浸水）。
- 把从图中所读数值列出来请用户确认；默认值须注明“取默认”。

### 第 3 步 · 计算
- 依据得到的参数写输入 JSON（结构见 `assets/input_template.json`），保存为临时文件。
- 运行内核：
  ```
  python "<skill>/scripts/dantu_calc.py" input.json -o result.json
  ```
  核心理念与公式见 `references/theory.md`，安全系数见 `references/standards.md`。
- 内核已实现：重力式（水平/倾斜基底、天然/换填地基、坡线土柱、附加集中力、库仑数值扫描）。
  其它墙型（衡重式/悬臂式/扶壁式/加筋土等）按 `references/theory.md` 第 3 节扩展；未实现时明确告知用户
  并给出按规范的手算过程或建议用理正复核。

### 第 4 步 · 生成计算书
- 单墙验算书（默认，对标 `路堤挡土墙2.5m.docx`）：
  ```
  python "<skill>/scripts/gen_report.py" input.json 输出计算书.docx
  ```
- 需封面/正式设计计算书（对标 `江台路...计算书.doc`）追加 `--cover --unit "单位名" --stage 施工图`。
- 格式要求见 `references/output-format.md`。

### 第 5 步 · 校核与建议
- 汇总 Kc、K0、e、σ、截面强度、整体稳定是否满足安全系数（`references/standards.md`）。
- **任一项不满足时，必须给出调整建议**（见 `references/advice.md`）：不满足项清单 + 对应措施 + 可选方案。

## 关键约定
- 单位：力 kN（每延米）、应力 kPa、长度 m、角度 度。
- 破裂角按理正口径输出（与竖直面夹角）。
- 土压力默认库仑；`Ex=Ea·cos(α+δ)`，`Ey=Ea·sin(α+δ)`。
- 与理正**对齐程度**：平基/竖直台阶等简单工况可逐字段复现（如 2m 无凸榫算例 Ea、Ex、Ey、Zy、B、e 全一致）；
  陡坡线 + 车辆换算土柱 + 倾斜基底组合工况，几何/荷载归化可能与理正有小差异，需以理正复核为准。

## 目录
- `scripts/dantu_calc.py`：计算内核 + 计算书文本
- `scripts/gen_report.py`：Word 计算书生成（python-docx）
- `references/theory.md`：计算原理与全部墙型要点
- `references/parameters.md`：参数识别与交互指南
- `references/output-format.md`：计算书输出格式
- `references/standards.md`：执行标准与安全系数、编制依据
- `references/advice.md`：力学不足时的调整建议
- `assets/input_template.json`：输入 JSON 模板
