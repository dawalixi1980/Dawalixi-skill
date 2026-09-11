# -*- coding: utf-8 -*-
"""
公路工程「工程变更」7 张表生成器（JSON 驱动）。

用法:
    python build_change_form.py config.json

config.json 字段见 references/config_schema.md。
依赖: Windows + Excel + pywin32（win32com）。
脚本以 assets/模板.xls 为版式母本，复制为 .xlsx 后填入数据，保留原版式。
"""
import os
import sys
import json

try:
    import win32com.client as win32
except ImportError:
    sys.exit("需要 pywin32：pip install pywin32")


XL_OPENXML = 51          # xlsx
XL_CENTER = -4108
XL_LEFT = -4131
XL_V_CENTER = -4108
XL_THIN = 1


def v(x):
    """空值显示为 —"""
    return x if x not in (None, "") else "—"


def set_cell(ws, addr, val):
    if val not in (None, ""):
        ws.Range(addr).Value = val


def border(ws, addr):
    b = ws.Range(addr).Borders
    b.LineStyle = XL_THIN
    b.Weight = 2


def build(cfg):
    template = cfg["template"]
    out = cfg["output"]
    p = cfg["project"]

    # 模板可为绝对路径，或相对脚本目录（如 assets/模板.xls）
    if not os.path.isabs(template):
        here = os.path.dirname(os.path.abspath(__file__))
        cand = os.path.join(here, "..", template)
        if os.path.exists(cand):
            template = cand
    if not os.path.exists(template):
        sys.exit("模板不存在: %s" % template)
    if os.path.exists(out):
        os.remove(out)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

    excel = win32.Dispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    try:
        wb = excel.Workbooks.Open(os.path.abspath(template))
        wb.SaveAs(os.path.abspath(out), FileFormat=XL_OPENXML)

        # ================= Sheet1 意向审批表（一） =================
        w = wb.Worksheets("工程变更意向审批表（一）")
        set_cell(w, "B3", p["construction_unit"])
        set_cell(w, "F3", p["name"])
        set_cell(w, "B4", p["supervision_unit"])
        set_cell(w, "F4", p["number"])
        set_cell(w, "B5", p["name"])
        set_cell(w, "F5", p["drawing_no"])
        set_cell(w, "B6", p["orig_cost"])
        set_cell(w, "D6", p["new_cost"])
        set_cell(w, "F6", p["delta"])
        set_cell(w, "B7", p["change_type"])
        set_cell(w, "D7", p["change_nature"])
        set_cell(w, "F7", p["pile_range"])
        set_cell(w, "B8", p["reason"])
        set_cell(w, "B9", p["content"])
        set_cell(w, "B10", p["construction_unit"])
        set_cell(w, "F10", p["owner_unit"])
        set_cell(w, "E15", p["owner_unit"] + "（盖章）")

        # ================= Sheet2 现场勘察与论证表 =================
        w = wb.Worksheets("工程变更现场勘察与论证表")
        set_cell(w, "C4", p["construction_unit"])
        set_cell(w, "F4", p["name"])
        set_cell(w, "C5", p["supervision_unit"])
        set_cell(w, "F5", p["number"])
        set_cell(w, "B6", p["reason"])
        set_cell(w, "C16", p["delta"])
        set_cell(w, "C17", p["change_nature"])
        set_cell(w, "C21", p["owner_unit"])

        # ================= Sheet3 报告审批表（一） =================
        w = wb.Worksheets("工程变更报告审批表（一）")
        set_cell(w, "B3", p["construction_unit"])
        set_cell(w, "F3", p["name"])
        set_cell(w, "B4", p["supervision_unit"])
        set_cell(w, "F4", p["number"])
        set_cell(w, "B5", p["change_type"])
        set_cell(w, "D5", p["change_nature"])
        set_cell(w, "F5", p["pile_range"])
        set_cell(w, "B6", p["name"])
        set_cell(w, "F6", p["drawing_no"])
        set_cell(w, "B7", p["delta"])
        set_cell(w, "B8", p["reason"])
        set_cell(w, "B9", p["content"])
        set_cell(w, "B10", p["construction_unit"])
        set_cell(w, "E15", p["owner_unit"] + "（盖章）")

        # ================= Sheet4 报告(意向)审批跟踪表/现场签证单 =================
        w = wb.Worksheets("工程变更报告（意向）审批跟踪表")
        set_cell(w, "A1", p["name"])
        set_cell(w, "B4", p["name"])
        set_cell(w, "B5", p["construction_unit"])
        set_cell(w, "G5", p["supervision_unit"])
        set_cell(w, "B6", p["owner_unit"])
        set_cell(w, "G6", p["design_unit"])
        set_cell(w, "A8", p["content"])

        # ================= Sheet5 造价估算表 =================
        w = wb.Worksheets("工程变更造价估算表")
        w.Columns(5).Insert()          # 插入一列：单价拆为 原设计单价 / 变更后单价
        set_cell(w, "C3", p["name"])
        set_cell(w, "C4", p["construction_unit"])
        set_cell(w, "G4", "监理单位：" + p["supervision_unit"])
        set_cell(w, "K4", "编号:" + p["number"])
        set_cell(w, "D5", "原设计单价(元)")
        set_cell(w, "E5", "变更后单价(元)")
        w.Range("A6:T43").ClearContents()
        r = 6
        for row in cfg["cost_rows"]:
            if "section" in row:
                w.Cells(r, 2).Value = row["section"]
                w.Range(w.Cells(r, 1), w.Cells(r, 11)).Font.Bold = True
            else:
                w.Cells(r, 1).Value = row.get("no")
                w.Cells(r, 2).Value = row.get("name")
                w.Cells(r, 3).Value = row.get("unit")
                w.Cells(r, 4).Value = v(row.get("orig_price"))
                w.Cells(r, 5).Value = v(row.get("new_price"))
                w.Cells(r, 6).Value = v(row.get("orig_qty"))
                w.Cells(r, 7).Value = v(row.get("new_qty"))
                w.Cells(r, 8).Value = v(row.get("dq"))
                w.Cells(r, 9).Value = row.get("delta")
                w.Cells(r, 10).Value = row.get("new_amt")
            r += 1
        n = len(cfg["cost_rows"])
        border(w, "A6:K%d" % (r - 1))
        if 6 + n <= 43:
            w.Rows("%d:43" % (6 + n)).Delete()
        tr = 45 - (38 - n)
        w.Cells(tr, 1).Value = "合计"
        w.Cells(tr, 9).Value = p["delta"]
        w.Cells(tr, 10).Value = p["new_cost"]

        # ================= Sheet6 清单批复表 =================
        w = wb.Worksheets("工程变更清单批复表")
        set_cell(w, "B4", p["name"])
        set_cell(w, "A5", "承包人：")
        set_cell(w, "B5", p["construction_unit"])
        set_cell(w, "G5", p["supervision_unit"])
        w.Range("A8:L45").ClearContents()
        r = 8
        for row in cfg["list_rows"]:
            if "section" in row:
                w.Cells(r, 1).Value = row["section"]
                w.Range(w.Cells(r, 1), w.Cells(r, 12)).Font.Bold = True
            else:
                w.Cells(r, 1).Value = row.get("name")
                w.Cells(r, 4).Value = row.get("unit")
                w.Cells(r, 5).Value = v(row.get("p1"))
                w.Cells(r, 6).Value = v(row.get("q1"))
                w.Cells(r, 7).Value = row.get("m1")
                w.Cells(r, 8).Value = v(row.get("p2"))
                w.Cells(r, 9).Value = v(row.get("q2"))
                w.Cells(r, 10).Value = row.get("m2")
                w.Cells(r, 11).Value = v(row.get("dq"))
                w.Cells(r, 12).Value = row.get("dm")
            r += 1
        n = len(cfg["list_rows"])
        border(w, "A8:L%d" % (r - 1))
        if 8 + n <= 45:
            w.Rows("%d:45" % (8 + n)).Delete()
        tr = 46 - (38 - n)
        w.Cells(tr, 7).Value = p["orig_cost"]
        w.Cells(tr, 10).Value = p["new_cost"]
        w.Cells(tr, 12).Value = p["delta"]
        w.Cells(tr + 1, 7).Value = p["owner_unit"] + "（盖章）"

        # ================= Sheet7 变更工程数量计算表 =================
        w = wb.Worksheets("变更工程数量计算表")
        set_cell(w, "B3", p["construction_unit"])
        set_cell(w, "F3", p["name"])
        set_cell(w, "B4", p["supervision_unit"])
        set_cell(w, "F4", p["number"])
        for addr in ["C7:F7", "C8:F8", "C41:F41", "C42:F42"]:
            try:
                w.Range(addr).UnMerge()
            except Exception:
                pass
        w.Range("A7:H44").ClearContents()
        w.Range("C7:C36").NumberFormat = "@"
        w.Range("A5:H6").Font.Bold = True
        w.Range("A5:H6").HorizontalAlignment = XL_CENTER
        w.Range("A5:H6").VerticalAlignment = XL_V_CENTER
        border(w, "A5:H6")
        r = 7
        item_rows, section_rows = [], []
        for row in cfg["qty_rows"]:
            if "section" in row:
                w.Cells(r, 2).Value = row["section"]
                section_rows.append(r)
            else:
                w.Cells(r, 1).Value = row.get("no")
                w.Cells(r, 2).Value = row.get("name")
                w.Cells(r, 3).Value = row.get("calc")
                w.Cells(r, 7).Value = row.get("unit")
                w.Cells(r, 8).Value = v(row.get("qty"))
                item_rows.append(r)
            r += 1
        n = len(cfg["qty_rows"])
        for ir in item_rows + section_rows:
            w.Range(w.Cells(ir, 3), w.Cells(ir, 6)).Merge()
        for ir in item_rows:
            w.Range(w.Cells(ir, 1), w.Cells(ir, 8)).VerticalAlignment = XL_V_CENTER
            w.Cells(ir, 1).HorizontalAlignment = XL_CENTER
            w.Cells(ir, 2).HorizontalAlignment = XL_LEFT
            w.Cells(ir, 7).HorizontalAlignment = XL_CENTER
            w.Cells(ir, 8).HorizontalAlignment = XL_CENTER
            w.Range(w.Cells(ir, 3), w.Cells(ir, 6)).HorizontalAlignment = XL_CENTER
        for sr in section_rows:
            w.Range(w.Cells(sr, 1), w.Cells(sr, 8)).Font.Bold = True
            w.Range(w.Cells(sr, 1), w.Cells(sr, 8)).Interior.Color = 0xEFEFEF
            w.Cells(sr, 2).HorizontalAlignment = XL_LEFT
        w.Range("A7:H%d" % (r - 1)).VerticalAlignment = XL_V_CENTER
        border(w, "A7:H%d" % (r - 1))
        if 7 + n <= 44:
            w.Rows("%d:44" % (7 + n)).Delete()
        w.Cells(13 + n, 1).Value = p["owner_unit"] + "（盖章）"

        wb.Save()
        wb.Close(False)
        print("已生成:", out)
    finally:
        excel.Quit()


def main():
    if len(sys.argv) < 2:
        sys.exit("用法: python build_change_form.py config.json")
    with open(sys.argv[1], encoding="utf-8") as f:
        cfg = json.load(f)
    build(cfg)


if __name__ == "__main__":
    main()
