"""客户总览页面全功能实测：对应 UI 每个筛选控件。"""
import json
import urllib.error
import urllib.request
from urllib.parse import quote
from datetime import datetime, timedelta

BASE = "http://127.0.0.1:8000"
ok = fail = 0
made = []


def req(m, p, b=None, t=None):
    h = {"Content-Type": "application/json"}
    if t:
        h["Authorization"] = "Bearer " + t
    r = urllib.request.Request(BASE + p, data=json.dumps(b).encode() if b else None, headers=h, method=m)
    try:
        with urllib.request.urlopen(r) as x:
            raw = x.read()
            return x.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, (json.loads(raw) if raw else None)


def ck(l, cond, detail=""):
    global ok, fail
    print(("[OK]   " if cond else "[FAIL] ") + l + (f"  -> {detail}" if detail else ""))
    ok += cond
    fail += not cond


_, a = req("POST", "/api/auth/login", {"phone": "13800000002", "password": "admin123"})
AT = a["access_token"]

# 清残留
_, old = req("GET", "/api/customers?page=1&page_size=100", t=AT)
for it in old.get("items", []):
    req("DELETE", f"/api/customers/{it['id']}", t=AT)

# —— 造 5 个差异客户 ——
yesterday = (datetime.now() - timedelta(days=1)).isoformat()
_, sales = req("GET", "/api/users", t=AT)
sid = next(u["id"] for u in sales if u["role"] == "sales")

def mk(company, phone, contact="", source="sales_init", stage="following", owner=None, overdue=False):
    _, c = req("POST", "/api/customers", {"company_name": company, "contact_name": contact, "phone": phone, "source": source}, t=AT)
    body = {}
    if stage:
        body["stage"] = stage
    body["next_followup_at"] = yesterday if overdue else (datetime.now() + timedelta(days=3)).isoformat()
    if owner:
        body["owner_id"] = owner
    req("PATCH", f"/api/customers/{c['id']}", body, t=AT)
    made.append(c["id"])
    return c["id"]

A = mk("超期测试A公司", "13799000001", contact="李超期", overdue=True)                    # 唯一超期
B = mk("爱采购测试B公司", "13799000002", source="aigopo", stage="won")                     # 唯一爱采购+成交
C = mk("联系人测试C公司", "13799000003", contact="张三丰", source="tel")                   # 唯一联系人+电话来源
D = mk("流失测试D公司", "13800099999", source="website", stage="lost")                     # 唯一流失+唯一电话尾号
E = mk("指定销售E公司", "13799000005", owner=sid)                                          # 唯一归属销售

def names(lst):
    return sorted(i["company_name"] for i in lst["items"])

# —— 逐项断言 ——
code, r = req("GET", "/api/customers?page=1&page_size=100", t=AT)
ck("① 全量列表（本测试 5 客户在库）", r["total"] >= 5, f"total={r['total']}")

code, r = req("GET", "/api/customers?page=1&page_size=100&overdue=true", t=AT)
ck("② 只看超期（UI Switch）", r["total"] == 1 and names(r) == ["超期测试A公司"], f"total={r['total']}")

code, r = req("GET", "/api/customers?page=1&page_size=100&keyword=" + quote("超期测试A"), t=AT)
ck("③ 公司名称搜索", r["total"] == 1 and names(r) == ["超期测试A公司"], f"total={r['total']}")

code, r = req("GET", "/api/customers?page=1&page_size=100&keyword=" + quote("张三丰"), t=AT)
ck("④ 联系人搜索", r["total"] == 1 and names(r) == ["联系人测试C公司"], f"total={r['total']}")

code, r = req("GET", "/api/customers?page=1&page_size=100&keyword=13800099999", t=AT)
ck("⑤ 电话搜索", r["total"] == 1 and names(r) == ["流失测试D公司"], f"total={r['total']}")

code, r = req("GET", "/api/customers?page=1&page_size=100&source=aigopo", t=AT)
ck("⑥ 来源筛选（爱采购）", r["total"] == 1 and names(r) == ["爱采购测试B公司"], f"total={r['total']}")

code, r = req("GET", "/api/customers?page=1&page_size=100&stage=lost", t=AT)
ck("⑦ 阶段筛选（流失）", r["total"] == 1 and names(r) == ["流失测试D公司"], f"total={r['total']}")

code, r = req("GET", f"/api/customers?page=1&page_size=100&owner_id={sid}", t=AT)
ck("⑧ 负责人筛选（下拉）", r["total"] == 1 and names(r) == ["指定销售E公司"], f"total={r['total']}")

code, r = req("GET", "/api/customers?page=1&page_size=2", t=AT)
code, r = req("GET", "/api/customers?page=1&page_size=2", t=AT)
ck("⑨ 分页 page_size=2", len(r["items"]) == 2 and r["total"] >= 5, f"页内{len(r['items'])}条/total={r['total']}")

code, r = req("GET", "/api/customers?page=1&page_size=100&stage=won&source=aigopo", t=AT)
ck("⑩ 组合筛选（阶段+来源）", r["total"] == 1 and names(r) == ["爱采购测试B公司"], f"total={r['total']}")

code, r = req("GET", "/api/customers?page=1&page_size=100&keyword=" + quote("不存在的公司XYZ"), t=AT)
ck("⑪ 无结果搜索", r["total"] == 0, f"total={r['total']}")

for i in made:
    req("DELETE", f"/api/customers/{i}", t=AT)
print(f"\n===== 通过 {ok} / 失败 {fail} =====（测试数据已清理）")
