import json
import random
import urllib.error
import urllib.request


def req(m, p, b=None, t=None):
    h = {"Content-Type": "application/json"}
    if t:
        h["Authorization"] = "Bearer " + t
    r = urllib.request.Request(
        "http://127.0.0.1:8000" + p,
        data=json.dumps(b).encode() if b else None,
        headers=h,
        method=m,
    )
    try:
        with urllib.request.urlopen(r) as x:
            raw = x.read()
            return x.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, (json.loads(raw) if raw else None)


ok = fail = 0


def ck(l, c):
    global ok, fail
    print(("[OK] " if c else "[FAIL] ") + l)
    ok += c
    fail += not c


_, a = req("POST", "/api/auth/login", {"phone": "13800000002", "password": "admin123"})
AT = a["access_token"]
_, b = req("POST", "/api/auth/login", {"phone": "13800000003", "password": "boss123"})
BT = b["access_token"]
# 清理上次残留（按精确手机号）
_, old = req("GET", "/api/customers?page=1&page_size=100", AT)
for it in old.get("items", []):
    if it["phone"] in ("13722223333", "13744445555"):
        req("DELETE", f"/api/customers/{it['id']}", AT)
RN = random.randint(1000, 9999)
_, c = req("POST", "/api/customers", {"company_name": "boss只读测试", "contact_name": "T", "phone": f"137{RN:08d}"}, AT)
CID = c["id"]
_, f = req("POST", f"/api/customers/{CID}/followups", {"method": "tel", "content": "跟进内容"}, AT)

# boss 读放行
code, _ = req("GET", "/api/customers", t=BT); ck("boss 客户列表 200", code == 200)
code, _ = req("GET", f"/api/customers/{CID}", t=BT); ck("boss 客户详情 200", code == 200)
code, _ = req("GET", f"/api/customers/{CID}/deals", t=BT); ck("boss 成交列表 200", code == 200)
code, _ = req("GET", f"/api/customers/{CID}/followups", t=BT); ck("boss 跟进列表 200", code == 200)
code, _ = req("GET", "/api/deals", t=BT); ck("boss 流水 200", code == 200)
# boss 写仍被拒
code, _ = req("POST", f"/api/customers/{CID}/followups", {"method": "tel", "content": "x"}, BT); ck("boss 加跟进 403", code == 403)
code, _ = req("PATCH", f"/api/customers/{CID}", {"company_name": "x"}, BT); ck("boss 改客户 403", code == 403)
# admin 编辑/删除跟进
code, fu = req("PATCH", f"/api/customers/followups/{f['id']}", {"content": "改后的内容"}, AT)
ck("admin 编辑跟进 200", code == 200 and fu.get("content") == "改后的内容")
code, why = req("DELETE", f"/api/customers/followups/{f['id']}", t=AT)
ck(f"admin 删除跟进 204 (got {code} {why})", code == 204)
# sales 本人编辑自己的跟进
req("POST", "/api/users", {"name": "销售T", "phone": "13733334444", "password": "s123456", "role": "sales"}, AT)
_, st = req("POST", "/api/auth/login", {"phone": "13733334444", "password": "s123456"})
ST = st["access_token"]
_, c2 = req("POST", "/api/customers", {"company_name": "销售T客户", "contact_name": "T", "phone": f"137{random.randint(1000, 9999):06d}"}, ST)
_, f2 = req("POST", f"/api/customers/{c2['id']}/followups", {"method": "wechat", "content": "自己的跟进"}, ST)
code, fu2 = req("PATCH", f"/api/customers/followups/{f2['id']}", {"content": "本人改"}, ST)
ck("sales 本人编辑跟进 200", code == 200 and fu2.get("content") == "本人改")
code, _ = req("PATCH", f"/api/customers/followups/{f2['id']}", {"content": "越权改"}, BT); ck("boss 编辑跟进 403", code == 403)
req("DELETE", f"/api/customers/{c2['id']}", ST)
req("DELETE", f"/api/customers/{CID}", AT)
print(f"== {ok} pass / {fail} fail ==")
