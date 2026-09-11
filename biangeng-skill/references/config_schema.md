# config.json 字段说明

生成脚本 `scripts/build_change_form.py` 的唯一入参是配置文件。所有金额单位为元，数量按对应单位。

```json
{
  "template": "assets/模板.xls",
  "output": "…/变更表.xlsx",
  "project": {
    "name": "工程名称",
    "construction_unit": "施工单位",
    "supervision_unit": "监理单位",
    "design_unit": "设计单位",
    "owner_unit": "建设单位",
    "number": "BG-1",
    "drawing_no": "图号，无则 -",
    "pile_range": "桩号",
    "change_type": "一般变更",
    "change_nature": "增加与扣减",
    "orig_cost": 4910278,
    "new_cost": 4728337,
    "delta": -181941,
    "reason": "变更原因（多行用 \\n）",
    "content": "变更内容（多行用 \\n）"
  },
  "cost_rows": [ ... ],
  "list_rows": [ ... ],
  "qty_rows": [ ... ]
}
```

## project
- `orig_cost` 原设计（施工图预算）总造价；`new_cost` 变更后（结算）总造价；`delta = new_cost - orig_cost`。
- `reason` 写入意向审批表「变更原因」、勘察表「变更原因及方案简述」、报告审批表「变更原因」。
- `content` 写入意向/报告审批表「变更内容」、现场签证单「签证原因、内容及工程量」。

## cost_rows（工程变更造价估算表）
数组，元素二选一：
- 分部行：`{"section": "路基工程"}` —— 加粗显示，不带数据。
- 明细行：
```json
{"no":2,"name":"挖除水泥混凝土面层","unit":"m2",
 "orig_price":23.26,"new_price":21.54,
 "orig_qty":245,"new_qty":407,"dq":162,
 "delta":3067,"new_amt":8766}
```
- `orig_price` 原设计单价、`new_price` 变更后单价；无对应值时填 `"—"`。
- `delta` 增减造价 = `new_amt - 原设计金额`；`new_amt` 变更后总造价。
- 生成后表格列：序号 | 变更项目名称 | 单位 | 原设计单价 | 变更后单价 | 原设计工程量 | 变更后工程量 | 增减工程量 | 增减造价 | 变更后总造价 | 备注。

## list_rows（工程变更清单批复表）
- 分部行：`{"section": "路基工程"}`。
- 明细行：
```json
{"name":"挖除水泥混凝土面层","unit":"m2",
 "p1":23.26,"q1":245,"m1":5699,
 "p2":21.54,"q2":407,"m2":8766,
 "dq":162,"dm":3067}
```
p=单价、q=数量、m=金额；1 为变更前（原设计），2 为变更后（结算），dq/dm 为增减数量/金额。

## qty_rows（变更工程数量计算表）
- 分部行：`{"section": "路基工程"}`。
- 明细行：
```json
{"no":2,"name":"挖除水泥混凝土面层","calc":"407-245","unit":"m2","qty":162}
```
- `calc` 计算式；`qty` 增减数量（无对应量填 `"—"`）。

## 约定
- 三个数组的分部名应保持一致（临时/路基/路面/桥梁涵洞/交叉/交通工程及沿线设施/专项费用）。
- 每个数组内部：**所有明细的金额/数量之增减合计，应等于该部分及全表合计**（见 `references/extraction_rules.md`）。
- 空值（`null`/`""`）在生成时显示为 `—`。
