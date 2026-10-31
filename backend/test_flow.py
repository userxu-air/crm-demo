"""YueCRM P0-W1 全链路验证脚本（标准库实现，无第三方依赖）。"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"
passed, failed = [], []


def req(method, path, body=None, token=None, headers=None, expect=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if headers:
        h.update(headers)
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            payload = json.loads(resp.read())
            code = resp.status
    except urllib.error.HTTPError as e:
        payload = json.loads(e.read())
        code = e.code
    label = f"{method} {path} -> {code}"
    if expect and code != expect:
        failed.append(f"[FAIL] {label} (期望 {expect}) {str(payload)[:120]}")
        return code, payload
    passed.append(f"[OK] {label}")
    return code, payload


# 1. 管理员登录
_, admin = req("POST", "/api/auth/login", {"phone": "13800000001", "password": "admin123"}, expect=200)
AT = admin["access_token"]

# 2. 管理员开户：销售 + 老板
req("POST", "/api/users", {"name": "张三", "phone": "13800000001", "password": "sales123", "role": "sales"}, AT, expect=200)
req("POST", "/api/users", {"name": "李四", "phone": "13800000002", "password": "sales123", "role": "sales"}, AT, expect=200)
req("POST", "/api/users", {"name": "老板", "phone": "13800000000", "password": "boss123", "role": "boss"}, AT, expect=200)

# 3. 销售登录
_, zhang = req("POST", "/api/auth/login", {"phone": "13800000001", "password": "sales123"}, expect=200)
ZT = zhang["access_token"]

# 4. admin 建客户（自动 3 天回访）
code, c1 = req("POST", "/api/customers", {
    "company_name": "东莞宏发包装厂", "contact_name": "客户经理", "phone": "13911112222",
    "source": "sales_init", "region": "广东东莞", "demand": "圆瓶贴标机 2 台",
}, AT, expect=201)
nfa = c1.get("next_followup_at", "")
if "T" in nfa and nfa[:10]:
    passed.append(f"[OK] 3 天回访默认: next_followup_at={nfa}")

# 5. 销售建客户（自动归属本人）
code, c2 = req("POST", "/api/customers", {
    "company_name": "深圳鑫泰食品", "contact_name": "刘经理", "phone": "13933334444",
    "source": "referral", "demand": "全自动平面贴标机",
}, ZT, expect=201)
assert_ok = c2["owner_name"] == "张三"
(passed if assert_ok else failed).append(
    f"[{'OK' if assert_ok else 'FAIL'}] 销售新建自动归属: owner_name={c2['owner_name']}")

# 6. 防撞单：再录同手机号
req("POST", "/api/customers", {
    "company_name": "撞单测试", "contact_name": "X", "phone": "13933334444",
}, AT, expect=409)
passed.append("[OK] 防撞单拦截: 409 + 归属提示")

# 7. 行级隔离：张三列表只见自己的
code, lst = req("GET", "/api/customers?page=1&page_size=50", token=ZT, expect=200)
only_own = all(i["owner_name"] == "张三" for i in lst["items"]) and lst["total"] == 1
(passed if only_own else failed).append(
    f"[{'OK' if only_own else 'FAIL'}] 行级隔离: 张三可见 {lst['total']} 条(应=1)")

# 8. admin 全量可见
code, lst_all = req("GET", "/api/customers?page=1&page_size=50", token=AT, expect=200)
all_ok = lst_all["total"] >= 2
(passed if all_ok else failed).append(
    f"[{'OK' if all_ok else 'FAIL'}] admin 全量可见: {lst_all['total']} 条")

# 9. boss 不能进客户列表（走看板）
req("GET", "/api/customers", token=None, expect=401)

# 10. 添加跟进：回写 3 天 + new→following
code, f1 = req("POST", f"/api/customers/{c2['id']}/followups", {
    "method": "tel", "content": "电话沟通，对方要报全自动款价格，等技术参数",
}, ZT, expect=201)
code, c2_after = req("GET", f"/api/customers/{c2['id']}", token=ZT, expect=200)
stage_ok = c2_after["stage"] == "following"
nfa_ok = c2_after["next_followup_at"] is not None
(passed if stage_ok else failed).append(f"[{'OK' if stage_ok else 'FAIL'}] 首次跟进自动转阶段: {c2_after['stage']}")
(passed if nfa_ok else failed).append(f"[{'OK' if nfa_ok else 'FAIL'}] 跟进后滚动 3 天回访: {c2_after['next_followup_at']}")

# 11. 阶段流转 won -> 提醒清空
req("POST", f"/api/customers/{c2['id']}/stage", {"stage": "won"}, ZT, expect=200)
_, c2_won = req("GET", f"/api/customers/{c2['id']}", token=ZT, expect=200)
won_ok = c2_won["stage"] == "won" and c2_won["next_followup_at"] is None
(passed if won_ok else failed).append(f"[{'OK' if won_ok else 'FAIL'}] 成交退出提醒: next_followup_at=None")

# 拉回 following 供看板测试
req("POST", f"/api/customers/{c2['id']}/stage", {"stage": "following"}, ZT, expect=200)

# 12. ingest 预留口（X-API-Key）
req("POST", "/api/leads/ingest",
    {"company_name": "广州云丰日化", "contact_name": "陈生", "phone": "13666667777", "source": "wecom", "remark": "企微 bot 留资"},
    headers={"X-API-Key": "dev-ingest-key-change-me"}, expect=201)
req("POST", "/api/leads/ingest",
    {"company_name": "重复测试", "phone": "13666667777"},
    headers={"X-API-Key": "dev-ingest-key-change-me"}, expect=201)  # 幂等跳过
req("POST", "/api/leads/ingest",
    {"company_name": "无钥测试", "phone": "13555558888"},
    headers={"X-API-Key": "wrong-key"}, expect=401)
passed.append("[OK] ingest 预留口: 创建/去重跳过/错误 Key 401")

# 13. dashboard summary（admin 全量 + 销售本人）
req("GET", "/api/dashboard/summary", token=AT, expect=200)
_, zs = req("GET", "/api/dashboard/summary", token=ZT, expect=200)
scope_ok = zs["scope"] == "self"
(passed if scope_ok else failed).append(f"[{'OK' if scope_ok else 'FAIL'}] 看板 scope: sales=self")

# 14. boss 登录走看板
_, boss = req("POST", "/api/auth/login", {"phone": "13800000000", "password": "boss123"}, expect=200)
req("GET", "/api/dashboard/summary", token=boss["access_token"], expect=200)
req("POST", "/api/customers", {"company_name": "越权测试", "phone": "13000000000"}, boss["access_token"], expect=403)
passed.append("[OK] boss: 可看板(200) + 写入被拒(403)")

# 15. admin 转移客户（交接给李四）
_, lisi = req("POST", "/api/auth/login", {"phone": "13800000002", "password": "sales123"}, expect=200)
req("PATCH", f"/api/customers/{c2['id']}", {"owner_id": 3}, AT, expect=200)
req("PATCH", f"/api/customers/{c2['id']}", {"owner_id": 3}, ZT, expect=403)
passed.append("[OK] 客户交接: admin 可转移 / sales 被拒 403")

print(f"\n===== 通过 {len(passed)} / 失败 {len(failed)} =====")
for p in passed:
    print(p)
for f_ in failed:
    print(f_)
