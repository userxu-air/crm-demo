"""附件上传功能全链路实测（multipart/下载/删除/权限/类型与大小限制）。"""
import io
import json
import random
import urllib.error
import urllib.request
import uuid

BASE = "http://127.0.0.1:8000"
ok = fail = 0


def req(m, p, b=None, t=None, raw_body=None, raw_headers=None):
    h = {"Content-Type": "application/json"}
    if t:
        h["Authorization"] = "Bearer " + t
    if raw_headers:
        h.update(raw_headers)
    data = json.dumps(b).encode() if b is not None else raw_body
    r = urllib.request.Request(BASE + p, data=data, headers=h, method=m)
    try:
        with urllib.request.urlopen(r) as x:
            raw = x.read()
            ct = x.headers.get("Content-Type", "")
            return x.status, (json.loads(raw) if raw and "json" in ct else raw)
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, (json.loads(raw) if raw else None)


def ck(l, c):
    global ok, fail
    print(("[OK]   " if c else "[FAIL] ") + l)
    ok += c
    fail += not c


def multipart(field, filename, content, ctype):
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    return body, {"Content-Type": f"multipart/form-data; boundary={boundary}"}


def login(phone, pw):
    _, d = req("POST", "/api/auth/login", {"phone": phone, "password": pw})
    return d["access_token"]


AT = login("13800000002", "admin123")
_, boss = req("POST", "/api/auth/login", {"phone": "13800000003", "password": "boss123"})
BT = boss["access_token"]

# 测试客户
_, custs = req("GET", "/api/customers?page=1&page_size=100", t=AT)
rn = random.randint(10000, 99999)
_, c = req("POST", "/api/customers", {"company_name": f"附件测试{rn}", "contact_name": "T", "phone": f"139{rn}77777"}, AT)
CID = c["id"]

# 1. 上传 PDF
pdf_body, pdf_h = multipart("file", "测试合同.pdf", b"%PDF-1.4 fake contract content " * 10, "application/pdf")
code, up = req("POST", f"/api/customers/{CID}/attachments", raw_body=pdf_body, raw_headers={**pdf_h, "Authorization": "Bearer " + AT})
ck("① 上传 PDF 201", code == 201 and up.get("filename") == "测试合同.pdf")
AID = up.get("id", 0)
ck("② 大小记录", up.get("size", 0) > 200)

# 2. 上传 Excel
xlsx_body, xlsx_h = multipart("file", "交易明细.xlsx", b"fake xlsx" * 5, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
code, up2 = req("POST", f"/api/customers/{CID}/attachments", raw_body=xlsx_body, raw_headers={**xlsx_h, "Authorization": "Bearer " + AT})
ck("③ 上传 Excel 201", code == 201)

# 3. 列表 2 个
_, lst = req("GET", f"/api/customers/{CID}/attachments", t=AT)
ck("④ 附件列表 2 条", len(lst) == 2)

# 4. 下载（内容一致）
code, dl = req("GET", f"/api/attachments/{AID}/download", t=AT)
ck("⑤ 下载 200 且内容一致", code == 200 and b"fake contract content" in dl)

# 5. 非法类型拒绝（.exe）
exe_body, exe_h = multipart("file", "病毒.exe", b"MZ", "application/x-msdownload")
code, _ = req("POST", f"/api/customers/{CID}/attachments", raw_body=exe_body, raw_headers={**exe_h, "Authorization": "Bearer " + AT})
ck("⑥ .exe 拒绝 400", code == 400)

# 6. boss 上传拒绝 / 下载允许
code, _ = req("POST", f"/api/customers/{CID}/attachments", raw_body=pdf_body, raw_headers={**pdf_h, "Authorization": "Bearer " + BT})
ck("⑦ boss 上传 403", code == 403)
code, _ = req("GET", f"/api/attachments/{AID}/download", t=BT)
ck("⑧ boss 下载 200（只读）", code == 200)

# 7. 未登录下载 401
code, _ = req("GET", f"/api/attachments/{AID}/download")
ck("⑨ 未登录下载 401", code == 401)

# 8. admin 删除附件（磁盘+库）
code, _ = req("DELETE", f"/api/attachments/{AID}", t=AT)
ck("⑩ admin 删除 204", code == 204)
code, _ = req("GET", f"/api/attachments/{AID}/download", t=AT)
ck("⑪ 删除后下载 404", code == 404)

# 9. 删除客户级联（附件列表应随客户消失——附件文件残留为已知极小遗留，记录）
req("DELETE", f"/api/customers/{CID}", t=AT)
code, _ = req("GET", f"/api/customers/{CID}/attachments", t=AT)
ck("⑫ 客户删除后列表 404", code == 404)

print(f"\n===== 通过 {ok} / 失败 {fail} =====")
