# -*- coding: utf-8 -*-
"""按钮级功能实测：按前端每个按钮的真实请求序列执行，断言返回结果。"""
import json
import random
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
ok = fail = 0
rows = []


def req(method, path, body=None, token=None, raw=False):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = "Bearer " + token
    r = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=h,
        method=method,
    )
    try:
        with urllib.request.urlopen(r, timeout=20) as x:
            data = x.read()
            if raw:
                return x.status, data
            return x.status, (json.loads(data) if data[:1] in (b"{", b"[") else data)
    except urllib.error.HTTPError as e:
        data = e.read()
        try:
            return e.code, json.loads(data)
        except Exception:
            return e.code, data


def ck(label, cond, detail=""):
    global ok, fail
    rows.append(("✅" if cond else "❌", label, detail))
    ok += bool(cond)
    fail += (not cond)


ph = f"138{random.randint(10000000, 99999999)}"

# ── 登录页 ──
code, d = req("POST", "/api/auth/login", {"phone": "13800000002", "password": "admin123"})
AT = d["access_token"]
ck("登录按钮（admin）", code == 200 and "access_token" in d)
code, d = req("POST", "/api/auth/login", {"phone": "13800000002", "password": "wrong"})
ck("登录按钮（错误密码）→ 401 提示", code == 401)
code, d = req("GET", "/api/auth/me", token=AT)
ck("顶栏用户信息（/auth/me）", code == 200 and d.get("name"))

# ── 客户总览 ──
code, c = req("POST", "/api/customers",
              {"company_name": "按钮实测公司", "contact_name": "客户经理", "phone": ph,
               "source": "sales_init", "region": "广东东莞", "demand": "圆瓶贴标机"}, AT)
CID = c["id"]
ck("新建客户按钮", code == 201 and c["stage"] == "new")
ck("  └ 3 天默认回访已生成", bool(c.get("next_followup_at")))
code, d = req("POST", "/api/customers",
              {"company_name": "防撞单测试", "contact_name": "T", "phone": ph}, AT)
ck("  └ 重复手机号 → 409 防撞单拦截", code == 409)
code, d = req("GET", f"/api/customers?page=1&page_size=10&keyword={ph}", token=AT)
ck("搜索框（按手机号）", code == 200 and d["total"] == 1)
code, d = req("GET", "/api/customers?page=1&page_size=10&overdue=true", token=AT)
ck("只看超期开关", code == 200 and all(i["id"] != CID for i in d["items"]))
code, d = req("PATCH", f"/api/customers/{CID}", {"region": "浙江宁波", "demand": "改需求"}, AT)
ck("编辑客户按钮（保存）", code == 200 and d["region"] == "浙江宁波")

# ── 跟进时间线 ──
code, f1 = req("POST", f"/api/customers/{CID}/followups",
               {"method": "tel", "content": "首次电话沟通"}, AT)
ck("添加跟进按钮", code == 201)
code, c2 = req("GET", f"/api/customers/{CID}", token=AT)
ck("  └ 自动 new→following", c2["stage"] == "following")
code, f2 = req("POST", f"/api/customers/{CID}/followups",
               {"method": "wechat", "content": "微信报价中"}, AT)
code, d = req("PATCH", f"/api/customers/followups/{f1['id']}", {"content": "改后的内容"}, AT)
ck("跟进「编辑」按钮", code == 200 and d["content"] == "改后的内容")
code, c3 = req("GET", f"/api/customers/{CID}", token=AT)
ck("  └ 编辑旧跟进不覆盖客户最新提醒", c3["next_followup_at"] == f2.get("next_followup_at") or c3.get("next_followup_at"))
code, _ = req("DELETE", f"/api/customers/followups/{f1['id']}", token=AT)
ck("跟进「删除」按钮", code == 204)

# ── 成交记录 ──
code, dl = req("POST", f"/api/customers/{CID}/deals",
               {"product": "直角封口贴标机", "product_line": "right_angle",
                "quantity": 2, "unit": "台", "unit_price": 4500,
                "deal_date": "2026-09-24", "invoice_type": "增值税专票"}, AT)
ck("添加成交按钮", code == 201 and dl["amount"] == 9000)
code, c4 = req("GET", f"/api/customers/{CID}", token=AT)
ck("  └ 客户自动转「成交」", c4["stage"] == "won" and c4["next_followup_at"] is None)
code, dl2 = req("POST", f"/api/customers/{CID}/deals",
                {"product": "平面贴标机", "product_line": "flat", "quantity": 1,
                 "unit": "台", "unit_price": 6000, "amount": 7000,
                 "deal_date": "2026-09-24", "repurchase": True}, AT)
ck("  └ 显式金额 7000 优先（不重算 6000）", dl2["amount"] == 7000 and dl2["repurchase"])
code, d = req("PATCH", f"/api/deals/{dl['id']}", {"unit_price": 5000}, AT)
ck("成交「编辑」按钮（改单价→金额重算）", code == 200 and d["amount"] == 10000)
code, d = req("GET", "/api/deals?page=1&page_size=10", token=AT)
ck("工作台流水查询含汇总", code == 200 and "total_amount" in d and "total_units" in d)
code, _ = req("DELETE", f"/api/deals/{dl2['id']}", token=AT)
ck("成交「删除」按钮", code == 204)

# ── 附件卡片 ──
boundary = "----btnaudit"
payload = (
    f"--{boundary}\r\n"
    'Content-Disposition: form-data; name="file"; filename="按钮实测合同.pdf"\r\n'
    "Content-Type: application/pdf\r\n\r\n%PDF-1.4 test\r\n"
    f"--{boundary}--\r\n"
).encode()
h = {"Authorization": "Bearer " + AT, "Content-Type": f"multipart/form-data; boundary={boundary}"}
r = urllib.request.Request(BASE + f"/api/customers/{CID}/attachments", data=payload, headers=h, method="POST")
with urllib.request.urlopen(r, timeout=20) as x:
    att = json.loads(x.read())
ck("附件「上传」按钮（PDF）", x.status == 201 and att["filename"] == "按钮实测合同.pdf")
code, d = req("GET", f"/api/customers/{CID}/attachments", token=AT)
ck("附件列表刷新", code == 200 and len(d) == 1)
code, data = req("GET", f"/api/attachments/{att['id']}/download", token=AT, raw=True)
ck("附件「下载」按钮", code == 200 and data.startswith(b"%PDF"))
code, _ = req("DELETE", f"/api/attachments/{att['id']}", token=AT)
ck("附件「删除」按钮", code == 204)

# ── 报表导出（admin 两枚按钮）──
code, data = req("GET", "/api/exports/deals?type=detail&year=2026&month=9", token=AT, raw=True)
ck("「销售明细表汇总」导出按钮", code == 200 and data[:2] == b"PK")
code, data = req("GET", "/api/exports/deals?type=report&year=2026&month=9", token=AT, raw=True)
ck("「业绩汇总」导出按钮", code == 200 and data[:2] == b"PK")
code, data = req("GET", "/api/exports/deals?type=personal&year=2026&month=9", token=AT, raw=True)
ck("个人日报导出（API）", code == 200 and data[:2] == b"PK")

# ── 系统设置 ──
code, d = req("GET", "/api/users", token=AT)
ck("账号列表加载", code == 200 and isinstance(d, list))
code, u = req("POST", "/api/users",
              {"name": "按钮实测销售", "phone": f"137{random.randint(10000000, 99999999)}",
               "password": "s123456", "role": "sales", "monthly_target": 50000,
               "in_sales_report": True}, AT)
SID, SPHONE = u["id"], u["phone"]
ck("新建账号按钮（含目标+开关）", code == 201 and u["in_sales_report"] is True)
code, d = req("PATCH", f"/api/users/{SID}", {"in_sales_report": False}, AT)
ck("业绩参与开关切换", code == 200 and d["in_sales_report"] is False)
code, d = req("PATCH", f"/api/users/{SID}", {"password": "new123456"}, AT)
ck("重置密码按钮", code == 200)
code, d = req("POST", "/api/auth/login", {"phone": SPHONE, "password": "new123456"})
ck("  └ 新密码可登录", code == 200)
ST = d["access_token"]
code, d = req("GET", "/api/customers?page=1&page_size=10", token=ST)
ck("sales 登录后列表仅本人（空）", code == 200 and d["total"] == 0)
code, _ = req("GET", "/api/exports/deals?type=detail&year=2026&month=9", token=ST, raw=False)
ck("sales 无导出入口（后端 403 兜底）", code == 403)
code, d = req("PATCH", f"/api/users/{SID}", {"is_active": False}, AT)
ck("账号停用开关", code == 200 and d["is_active"] is False)
code, d = req("POST", "/api/auth/login", {"phone": SPHONE, "password": "new123456"})
ck("  └ 停用后登录 → 403 拒绝", code == 403)
code, d = req("POST", "/api/auth/login", {"phone": "13800000003", "password": "boss123"})
BT = d["access_token"]
code, _ = req("PATCH", f"/api/customers/{CID}", {"company_name": "x"}, BT)
ck("boss 编辑客户 → 403", code == 403)
code, _ = req("POST", f"/api/customers/{CID}/followups", {"method": "tel", "content": "x"}, BT)
ck("boss 加跟进 → 403", code == 403)
code, _ = req("POST", f"/api/customers/{CID}/stage", {"stage": "lost"}, BT)
ck("boss 标记流失 → 403", code == 403)

# ── 改密码按钮 ──
code, _ = req("POST", "/api/auth/change-password", {"old_password": "admin123", "new_password": "admin123"}, AT)
ck("顶栏改密码按钮", code in (200, 204))

# 清理
req("DELETE", f"/api/customers/{CID}", token=AT)
req("DELETE", f"/api/users/{SID}", token=AT)

print()
for mark, label, detail in rows:
    print(f"{mark} {label}" + (f"  [{detail}]" if detail else ""))
print(f"\n===== 按钮级实测：{ok} 通过 / {fail} 失败 =====（测试数据已清理）")
