"""三遍审核修复点回归：boss stage 403 + ingest source 校验。"""
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
ok = fail = 0


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


def ck(l, c):
    global ok, fail
    print(("[OK]   " if c else "[FAIL] ") + l)
    ok += c
    fail += not c


_, d = req("POST", "/api/auth/login", {"phone": "13800000002", "password": "admin123"})
AT = d["access_token"]
_, d = req("POST", "/api/auth/login", {"phone": "13800000003", "password": "boss123"})
BT = d["access_token"]

for it in req("GET", "/api/customers?page=1&page_size=100", t=AT)[1]["items"]:
    if "stage回归" in it["company_name"]:
        req("DELETE", f"/api/customers/{it['id']}", t=AT)

_, c = req("POST", "/api/customers", {"company_name": "stage回归测试", "contact_name": "T", "phone": "13688889999"}, AT)
code, _ = req("POST", f"/api/customers/{c['id']}/stage", {"stage": "won"}, BT)
ck("boss 改 stage 403（漏洞修复）", code == 403)
code, _ = req("POST", f"/api/customers/{c['id']}/stage", {"stage": "won"}, AT)
ck("admin 改 stage 200", code == 200)

# ingest source 校验（生产 key 与 compose 一致）
r = urllib.request.Request(
    BASE + "/api/leads/ingest",
    data=json.dumps({"company_name": "ingest校验", "phone": "13977776666", "source": "bad-source"}).encode(),
    headers={"Content-Type": "application/json", "X-API-Key": "dev-ingest-key-change-me"},
    method="POST",
)
try:
    urllib.request.urlopen(r)
    ck("ingest 非法 source 拦截", False)
except urllib.error.HTTPError as e:
    ck(f"ingest 非法 source {e.code}（期望422）", e.code == 422)

# 合法 source 正常创建
r = urllib.request.Request(
    BASE + "/api/leads/ingest",
    data=json.dumps({"company_name": "ingest合法测试", "phone": "13977776667", "source": "wecom"}).encode(),
    headers={"Content-Type": "application/json", "X-API-Key": "dev-ingest-key-change-me"},
    method="POST",
)
try:
    with urllib.request.urlopen(r) as x:
        d = json.loads(x.read())
    ck("ingest 合法 source 201", x.status == 201 and d.get("status") == "created")
except Exception as e:
    ck("ingest 合法 source 201", False)

req("DELETE", f"/api/customers/{c['id']}", t=AT)
_, l = req("GET", "/api/customers?page=1&page_size=100", t=AT)
for it in l["items"]:
    if "ingest" in it["company_name"]:
        req("DELETE", f"/api/customers/{it['id']}", t=AT)
print(f"\n===== 通过 {ok} / 失败 {fail} =====")
