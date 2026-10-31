"""把样板文件清成模板：保留全部结构/表头/公式/合并格/样式，仅清数据。"""
import os
from pathlib import Path
from openpyxl import load_workbook

T = str(Path(__file__).resolve().parent / "templates")


def clear_range(ws, min_row, min_col=2):
    """清数值（保留公式与 None），用于数据区。"""
    for row in ws.iter_rows(min_row=min_row, min_col=min_col, max_col=ws.max_column):
        for cell in row:
            if cell.value is not None and not (isinstance(cell.value, str) and cell.value.startswith("=")):
                cell.value = None


# ---------- 1. 销售明细表汇总 ----------
p = os.path.join(T, "销售明细表汇总_样板.xlsx")
wb = load_workbook(p)
for sn, is_month in [("销售汇总明细表", False), ("销售汇总明细表 (2)", True)]:
    ws = wb[sn]
    n = ws.max_row - 1
    if n > 0:
        ws.delete_rows(2, n)
    print(sn, "清至", ws.max_row, "行")
ws = wb["Sheet1"]
clear_range(ws, 3)  # 清透视数值，保留标签
for c in range(2, 5):
    ws.cell(len(units_rows := [3, 4, 5, 6]) + 3, c).value = None
# 大设备
ws = wb["大设备"]
n = ws.max_row - 1
if n > 0:
    ws.delete_rows(2, n)
print("大设备 清至", ws.max_row, "行")
out = os.path.join(T, "销售明细表汇总.xlsx")
wb.save(out)
print("saved:", out, os.path.getsize(out) // 1024, "KB")

# ---------- 2. 业绩汇总 ----------
p = os.path.join(T, "业绩汇总_样板.xlsx")
wb = load_workbook(p)
for ws in wb.worksheets:
    if ws.title.startswith("20"):  # 2026全年：清月度业绩，保留年目标与公式
        for c in range(2, 14):  # B2:M2 各月
            ws.cell(2, c).value = None
        continue
    if "数据分类" in ws.title:
        clear_range(ws, 2)  # 清矩阵值，保留 A 标签/1 行销售名/合计公式
    else:  # 月 sheet：清 r3 起数据（保留公式列 BL/BM 及标签）
        clear_range(ws, 3)
out = os.path.join(T, "业绩汇总.xlsx")
wb.save(out)
print("saved:", out, os.path.getsize(out) // 1024, "KB", "| sheets:", wb.sheetnames)

# ---------- 3. 个人日报 ----------
p = os.path.join(T, "个人日报_样板.xlsx")
wb = load_workbook(p)
keep = wb["26-9"]
clear_range(keep, 2)
for sn in list(wb.sheetnames):
    if sn != "26-9":
        del wb[sn]
out = os.path.join(T, "个人日报.xlsx")
wb.save(out)
print("saved:", out, os.path.getsize(out) // 1024, "KB", "| sheets:", wb.sheetnames)

# ---------- 4. 询盘统计 ----------
p = os.path.join(T, "询盘统计_样板.xlsx")
wb = load_workbook(p)
keep = wb["26年9月"]
clear_range(keep, 3)
for sn in list(wb.sheetnames):
    if sn != "26年9月":
        del wb[sn]
out = os.path.join(T, "询盘统计.xlsx")
wb.save(out)
print("saved:", out, os.path.getsize(out) // 1024, "KB")

# ---------- 5. 大设备商机 ----------
p = os.path.join(T, "大设备商机_样板.xlsx")
wb = load_workbook(p)
ws = wb["Sheet1"]
n = ws.max_row - 1
if n > 0:
    ws.delete_rows(2, n)
for sn in list(wb.sheetnames):
    if sn != "Sheet1":
        del wb[sn]
out = os.path.join(T, "大设备商机.xlsx")
wb.save(out)
print("saved:", out, os.path.getsize(out) // 1024, "KB")
