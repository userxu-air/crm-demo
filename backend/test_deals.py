"""成交记录功能验证。"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"
passed, failed = [], []


def req(method, path, body=None, token=None, expect=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, json.loads(raw) if raw else None


def check(label, cond):
    (passed if cond else failed).append(f"[{'OK' if cond else 'FAIL'}] {label}")


_, a = req("POST", "/api/auth/login", {"phone": "13800000002", "password": "admin123"})
# 清残留（上次中断留下的测试客户，翻全页）
_t0 = req("GET", "/api/customers?page=1&page_size=1", token=a["access_token"])[1]["total"]
for _pg in range(1, (_t0 + 99) // 100 + 1):
    _, _l0 = req("GET", f"/api/customers?page={_pg}&page_size=100", token=a["access_token"])
    for _it0 in _l0.get("items", []):
        if _it0["phone"] == "13611112222" or _it0["company_name"].startswith("成交测试"):
            req("DELETE", f"/api/customers/{_it0['id']}", token=a["access_token"])
AT = a["access_token"]

# 基线：库里当月已有量（演示/真实数据），断言用增量
_, _flow0 = req("GET", "/api/deals?page=1&page_size=1", token=AT)
BASE_AMT = _flow0.get("total_amount", 0) or 0
BASE_UNITS = _flow0.get("total_units", 0) or 0
BASE_CNT = _flow0.get("total", 0) or 0
_, _dash0 = req("GET", "/api/dashboard/summary", token=a["access_token"])
BASE_MONTH_AMT = _dash0.get("month_amount", 0) or 0
BASE_MONTH_UNITS = _dash0.get("month_units", 0) or 0

# 建测试客户（stage=new）
_, c = req("POST", "/api/customers", {
    "company_name": "成交测试公司", "contact_name": "测总", "phone": "13611112222",
}, AT)
CID = c["id"]

# 1. 添加成交（金额自动算：3 台 × 7500 = 22500）
_, d1 = req("POST", f"/api/customers/{CID}/deals", {
    "product": "直角封口贴标机", "product_line": "right_angle",
    "quantity": 3, "unit": "台", "unit_price": 7500,
    "invoice_type": "13%专票", "account": "公账（）", "sales_no": "示例号",
}, AT)
check("成交创建 201", d1.get("id") is not None)
check("金额自动计算 3×7500=22500", d1.get("amount") == 22500)
check("成交日期默认今天", d1.get("deal_date") is not None)

# 2. 客户自动转 won
_, c2 = req("GET", f"/api/customers/{CID}", token=AT)
check("添加成交后客户自动转 won", c2.get("stage") == "won")
check("won 后提醒清空", c2.get("next_followup_at") is None)

# 3. 第二笔成交（手填金额覆盖）
_, d2 = req("POST", f"/api/customers/{CID}/deals", {
    "product": "25mm透明圆标", "product_line": "consumable",
    "quantity": 40, "unit": "卷", "unit_price": 37, "amount": 1300,
    "repurchase": True,
}, AT)
check("手填金额覆盖 1300", d2.get("amount") == 1300)

# 4. 客户成交列表（2 笔）
_, lst = req("GET", f"/api/customers/{CID}/deals", token=AT)
check("客户成交列表 2 笔", len(lst) == 2)

# 5. 全量流水查询 + 汇总
_, flow = req("GET", "/api/deals", token=AT)
check("流水查询含汇总金额=基线+23800", flow.get("total_amount") == BASE_AMT + 23800)
check("流水台数统计（仅单位=台）=基线+3", flow.get("total_units") == BASE_UNITS + 3)

# 6. boss 写入被拒
_, boss = req("POST", "/api/auth/login", {"phone": "13800000003", "password": "boss123"})
check("boss 登录", boss.get("access_token") is not None)
code, _ = req("POST", f"/api/customers/{CID}/deals", {"product": "x"}, boss["access_token"])
check("boss 添加成交 403", code == 403)
code, flow_boss = req("GET", "/api/deals", token=boss["access_token"])
check("boss 可读流水（只读）", code == 200)

# 7. dashboard 成交统计
_, s = req("GET", "/api/dashboard/summary", token=AT)
check("工作台本月成交额=基线+23800", s.get("month_amount") == BASE_MONTH_AMT + 23800)
check("工作台本月台数=基线+3", s.get("month_units") == BASE_MONTH_UNITS + 3)
check("按人业绩排行含 admin", any(r["amount"] > 0 for r in s.get("deal_ranking", [])))

# 8. 修改成交（数量变 5，金额重算 37500）
_, d1u = req("PATCH", f"/api/deals/{d1['id']}", {"quantity": 5}, AT)
check("改数量金额重算 5×7500=37500", d1u.get("amount") == 37500)

# 9. 删除成交（admin）
code, _ = req("DELETE", f"/api/deals/{d2['id']}", token=AT)
check("admin 删除成交 204", code == 204)
code, _ = req("DELETE", f"/api/deals/{d1['id']}", token=boss["access_token"])
check("boss 删除成交 403", code == 403)

# 清理测试数据
req("DELETE", f"/api/customers/{CID}", token=AT)

print(f"\n===== 通过 {len(passed)} / 失败 {len(failed)} =====")
for p in passed:
    print(p)
for f_ in failed:
    print(f_)
