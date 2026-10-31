"""历史数据一键导入（仅 admin）。

两种表：
- deals-flow    《销售明细表汇总》成交流水：18 列，按「销售手机」归属账号，客户按「客户名」查重（无客户电话 → 999 开头占位号）
- opportunities 《大设备信息表》商机：10 列，无电话，按客户名查重；「是否已成交」=是 → won + 生成成交记录

流程：dry_run=true 预检（不写库）→ 确认后 dry_run=false 正式导入 → 写 import_logs。
GET /template/{kind} 下载对应样板（表头即模板，照列填）。
"""
import io
import re
import threading
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import load_workbook
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Customer, Deal, ImportLog, ProductLine, Role, Source, Stage, User
from app.schemas import PRODUCT_LINE_TEXT

router = APIRouter(prefix="/api/import", tags=["import"])

_import_lock = threading.Lock()  # 单飞：同时只允许一个导入任务（防并发叠加撑爆内存）

TEXT2ENUM = {v: k for k, v in PRODUCT_LINE_TEXT.items()}
MAX_WARN = 50


# ---------- 工具 ----------

def _norm_phone(v) -> str:
    """手机号归一：去非数字、去 86 前缀。"""
    if v is None:
        return ""
    digits = re.sub(r"\D", "", str(v))
    return digits[2:] if digits.startswith("86") and len(digits) > 11 else digits


def _num(v, default=0.0) -> float:
    if v is None or v == "":
        return default
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d.\-]", "", str(v))
    try:
        return float(s)
    except ValueError:
        return default


def _truthy(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip() in {"复购", "是", "y", "Y", "yes", "1", "已成交"}


def _date(v):
    """宽容解析日期：datetime / excel 序列 / 常见字符串。失败返回 None。"""
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)):  # excel 序列号
        try:
            return date(1899, 12, 30) + timedelta(days=int(v))
        except Exception:
            return None
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日", "%m月%d日", "%m-%d", "%m/%d"):
        try:
            d = datetime.strptime(s, fmt).date()
            return d.replace(year=datetime.now().year) if d.year == 1900 else d
        except ValueError:
            continue
    return None


def _s(v, limit=100) -> str:
    return str(v).strip() if v is not None else ""




def _guess_line(*texts) -> ProductLine:
    """从产品/设备名称里模糊识别产品线（含常用别名：圆标→圆瓶、高精度→高精度吸贴）。"""
    text = "".join(t for t in texts if t)
    aliases = {"圆标": "圆瓶", "高精度": "高精度吸贴", "滚贴机": "滚贴"}
    for alias, canonical in aliases.items():
        if alias in text and canonical in TEXT2ENUM:
            return TEXT2ENUM[canonical]
    for name, enum in TEXT2ENUM.items():
        if name != "其他" and name in text:
            return enum
    return ProductLine.other


def _collect_rows(wb, needed: tuple):
    """扫描所有表头含必需列的数据 sheet，合并返回。

    返回 [(slim_dict, sheet名, excel行号), ...]——每行立即投影成
    「表头真实列数」的窄字典（~18 列），丢弃 WPS 填充的 16384 列空数据，
    内存占用从数百 MB 降到个位数 MB。
    """
    all_rows: list[tuple] = []
    used_sheets: list[str] = []
    for ws in wb.worksheets:
        rows_iter = ws.iter_rows(values_only=True)
        try:
            header = next(rows_iter)
        except StopIteration:
            continue
        headers = {}
        for idx, v in enumerate(header, start=1):
            if v is not None:
                headers[_s(v)] = idx
        if not all(any(n in h for h in headers) for n in needed):
            continue
        for excel_rn, row in enumerate(rows_iter, start=2):
            if any(v is not None and str(v).strip() != "" for v in row):
                slim = {h: (row[i - 1] if i - 1 < len(row) else None) for h, i in headers.items()}
                all_rows.append((slim, ws.title, excel_rn))
        used_sheets.append(ws.title)
    if not used_sheets:
        raise HTTPException(400, f"未找到含必需列（{'、'.join(needed)}）的数据 sheet，请下载模板照列填写")
    return all_rows, used_sheets


def _norm_name(s: str) -> str:
    """客户名归一：全角→半角、去空白、小写——用于查重匹配（原文本仍原样入库）。"""
    import unicodedata
    t = unicodedata.normalize("NFKC", str(s))
    return re.sub(r"\s+", "", t).lower()


def _similar(a: str, b: str) -> bool:
    """疑似重复：归一后一方包含另一方（长度≥4）。"""
    if len(a) < 4 or len(b) < 4:
        return False
    return a in b or b in a


def _dedupe(items: list[str]) -> list[str]:
    """同类告警聚合：『xxx ×N』，控制刷屏。"""
    counts: dict[str, int] = {}
    for it in items:
        counts[it] = counts.get(it, 0) + 1
    return [f"{k}（×{n}）" if n > 1 else k for k, n in counts.items()]


# ---------- 端点 ----------

@router.get("/template/{kind}")
def download_template(kind: str, user: User = Depends(get_current_user)):
    if user.role == Role.boss:
        raise HTTPException(403, "老板账号为只读")
    files = {
        "deals-flow": ("销售明细表汇总.xlsx", "成交流水导入模板"),
        "opportunities": ("大设备商机.xlsx", "商机导入模板"),
    }
    if kind not in files:
        raise HTTPException(400, "kind 仅支持 deals-flow / opportunities")
    name, _ = files[kind]
    p = Path(settings.TEMPLATE_DIR) / name
    if not p.exists():
        raise HTTPException(500, f"模板缺失: {name}")
    buf = io.BytesIO()
    buf.write(p.read_bytes())
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"},
    )


# ---------- 归属解析 ----------

def _resolve_owner(user: User, forced_owner: User | None, sales_phone: str,
                   users_by_phone: dict, admin: User) -> tuple[User, bool]:
    """分账号归属。返回 (归属账号, 是否告警)。

    - sales：强制本人（不看列）
    - admin 指定 forced_owner：强制该账号（不看列）
    - admin 默认：按文件「销售手机」列匹配，匹配不到归管理员并告警
    """
    if user.role == Role.sales:
        return user, False
    if forced_owner is not None:
        return forced_owner, False
    matched = users_by_phone.get(sales_phone)
    if matched:
        return matched, False
    return admin, bool(sales_phone)


@router.post("/deals-flow")
def import_deals_flow(
    file: UploadFile = File(...),
    dry_run: bool = False,
    owner_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role == Role.boss:
        raise HTTPException(403, "老板账号为只读")
    if not _import_lock.acquire(blocking=False):
        raise HTTPException(409, "已有导入任务在执行中，请等它完成后再试（勿重复点击）")
    try:
        return _run_deals_flow(file, dry_run, owner_id, user, db)
    finally:
        _import_lock.release()


def _run_deals_flow(file: UploadFile, dry_run: bool, owner_id: int | None, user: User, db: Session):
    content = file.file.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(413, "文件超过 15MB，请拆分后导入")
    wb = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    needed = ("日期", "客户名", "产品", "成交金额")
    collected, used_sheets = _collect_rows(wb, needed)

    users_by_phone = {u.phone: u for u in db.query(User).all()}
    admin = next((u for u in users_by_phone.values() if u.role == Role.admin), user)
    # admin 可强制指定归属账号（覆盖列匹配）；sales 由 _resolve_owner 强制本人
    forced_owner = None
    if user.role == Role.admin and owner_id:
        forced_owner = db.get(User, owner_id)
        if not forced_owner or not forced_owner.is_active:
            raise HTTPException(400, "指定的归属账号不存在或已停用")
    cust_by_name: dict[str, Customer] = {}
    # 归一客户表：一次性载入全库（按归一名索引），名称变体（全角/空格）也能撞上
    cust_by_norm: dict[str, Customer] = {}
    for c0 in db.query(Customer).all():
        cust_by_norm.setdefault(_norm_name(c0.company_name), c0)
    batch = uuid.uuid4().hex

    total = customers_new = customers_hit = deals_new = 0
    warnings: list[str] = []
    errors: list[str] = []
    new_customers: list[Customer] = []
    new_deals: list[Deal] = []

    for slim, sheet_title, excel_rn in collected:
        total += 1

        def col(key):
            return slim.get(key)

        src = f"[{sheet_title} 第{excel_rn}行]"
        name = _s(col("客户名"))
        ddate = _date(col("日期"))
        if not name:
            errors.append(f"{src}：客户名为空，跳过")
            continue
        if ddate is None:
            errors.append(f"{src}：日期无法解析（{col('日期')}），跳过")
            continue

        # 成交金额：显式优先，否则数量×单价；全空视为退货/作废行跳过
        qty = _num(col("数量"), 1)
        price = _num(col("单价"))
        amount = _num(col("成交金额"))
        if amount == 0:
            amount = round(qty * price, 2)
        if amount == 0 and price == 0:
            errors.append(f"{src}：金额与单价均为空（疑似退货/作废行），跳过")
            continue

        # 销售归属（分账号导入：sales=本人；admin=列匹配或指定账号）
        sales_phone = _norm_phone(col("销售手机"))
        sales_user, warn = _resolve_owner(user, forced_owner, sales_phone, users_by_phone, admin)
        if warn:
            warnings.append(f"销售手机 {sales_phone} 无匹配账号 → 归属管理员")

        # 客户查重（归一名匹配，名称变体也撞得上）
        nn = _norm_name(name)
        cust = cust_by_name.get(name) or cust_by_norm.get(nn)
        if cust is None:
            near = next((c1 for k1, c1 in cust_by_norm.items() if _similar(nn, k1)), None)
            if near:
                warnings.append(f"「{name}」与已有客户「{near.company_name}」名称疑似重复，已按新客户建档（建议人工合并）")
            cust = Customer(
                company_name=name[:100],
                contact_name=name[:50],
                phone=None,
                source=Source.other,
                stage=Stage.won,
                owner_id=sales_user.id,
                region=_s(col("地区"), 50),
                demand=_s(col("行业"), 200),
                import_batch=batch,
            )
            new_customers.append(cust)
            customers_new += 1
            cust_by_norm.setdefault(nn, cust)
        else:
            customers_hit += 1
        cust_by_name[name] = cust

        remark_parts = [_s(col("备注")), _s(col("发货地址"))]
        added = _date(col("添加日期"))
        product_name = _s(col("产品"), 100) or "未填产品"
        short_name = _s(col("产品简称"))
        deal = Deal(
            customer=cust,
            user_id=sales_user.id,
            deal_date=ddate,
            product=product_name,
            product_line=(TEXT2ENUM.get(short_name) if short_name else None) or _guess_line(product_name),
            quantity=qty,
            unit=_s(col("单位"), 10) or "台",
            unit_price=price,
            amount=amount,
            invoice_type=_s(col("开票类型"), 20),
            account=_s(col("收款账户"), 50),
            sales_no=_s(col("销售手机"), 50),
            repurchase=_truthy(col("复购")),
            remark="｜".join(p for p in remark_parts if p),
            import_batch=batch,
        )
        if added:
            deal.created_at = datetime.combine(added, datetime.min.time())
        new_deals.append(deal)
        deals_new += 1

    # 成交去重：同客户+同日期+同产品+同金额 已存在 → 跳过（防重复导入翻倍）
    # 键用 Customer 对象定位：已落库用 c.id，本次新建用 id(c)（库中不可能有它的旧成交）
    dup_deals = 0
    existing_keys: set = set()
    cust_ids = [c.id for c in cust_by_name.values() if c.id]
    if cust_ids:
        for d0 in db.query(Deal).filter(Deal.customer_id.in_(cust_ids)).all():
            dd = d0.deal_date.date() if isinstance(d0.deal_date, datetime) else d0.deal_date
            existing_keys.add((d0.customer_id, dd, d0.product, round(float(d0.amount), 2)))
    kept_deals: list[Deal] = []
    for d0 in new_deals:
        dd = d0.deal_date.date() if isinstance(d0.deal_date, datetime) else d0.deal_date
        cobj = d0.customer
        cid = cobj.id if cobj.id is not None else id(cobj)
        key = (cid, dd, d0.product, round(float(d0.amount or 0), 2))
        if key in existing_keys:
            dup_deals += 1
            deals_new -= 1
            errors.append(f"成交重复跳过：{d0.customer.company_name if d0.customer else '?'}｜{dd}｜{d0.product}｜¥{d0.amount}")
            continue
        existing_keys.add(key)
        kept_deals.append(d0)

    if not dry_run:
        db.add_all(new_customers)
        db.flush()  # 拿到新客户 id（deal 的 FK 由 relationship 在 flush 时自动绑定）
        db.add_all(kept_deals)
        db.add(ImportLog(filename=file.filename or "deals-flow", total=total, batch=batch,
                         success_count=deals_new, fail_count=total - deals_new, user_id=user.id))
        db.commit()

    return {
        "dry_run": dry_run,
        "batch": batch,
        "sheets": used_sheets,
        "total_rows": total,
        "customers_created": customers_new,
        "customers_matched": customers_hit,
        "deals_created": deals_new,
        "duplicates": dup_deals,
        "skipped": len(errors),
        "warnings": _dedupe(warnings)[:MAX_WARN],
        "errors": _dedupe(errors)[:MAX_WARN],
    }


@router.post("/opportunities")
def import_opportunities(
    file: UploadFile = File(...),
    dry_run: bool = False,
    owner_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role == Role.boss:
        raise HTTPException(403, "老板账号为只读")
    if not _import_lock.acquire(blocking=False):
        raise HTTPException(409, "已有导入任务在执行中，请等它完成后再试（勿重复点击）")
    try:
        return _run_opportunities(file, dry_run, owner_id, user, db)
    finally:
        _import_lock.release()


def _run_opportunities(file: UploadFile, dry_run: bool, owner_id: int | None, user: User, db: Session):
    content = file.file.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(413, "文件超过 15MB，请拆分后导入")
    wb = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    needed = ("客户名称", "设备名称", "销售手机")
    collected, used_sheets = _collect_rows(wb, needed)

    users_by_phone = {u.phone: u for u in db.query(User).all()}
    admin = next((u for u in users_by_phone.values() if u.role == Role.admin), user)
    forced_owner = None
    if user.role == Role.admin and owner_id:
        forced_owner = db.get(User, owner_id)
        if not forced_owner or not forced_owner.is_active:
            raise HTTPException(400, "指定的归属账号不存在或已停用")
    cust_by_name: dict[str, Customer] = {}
    cust_by_norm: dict[str, Customer] = {}
    for c0 in db.query(Customer).all():
        cust_by_norm.setdefault(_norm_name(c0.company_name), c0)
    batch = uuid.uuid4().hex

    total = customers_new = customers_hit = deals_new = won_count = 0
    warnings: list[str] = []
    errors: list[str] = []
    new_customers: list[Customer] = []
    new_deals: list[Deal] = []
    default_next = datetime.now() + timedelta(days=settings.DEFAULT_FOLLOWUP_DAYS)

    for slim, sheet_title, excel_rn in collected:
        total += 1

        def col(key):
            return slim.get(key)

        src = f"[{sheet_title} 第{excel_rn}行]"
        name = _s(col("客户名称"))
        if not name:
            errors.append(f"{src}：客户名称为空，跳过")
            continue

        sales_phone = _norm_phone(col("销售手机"))
        sales_user, warn = _resolve_owner(user, forced_owner, sales_phone, users_by_phone, admin)
        if warn:
            warnings.append(f"销售手机 {sales_phone} 无匹配账号 → 归属管理员")

        nn = _norm_name(name)
        cust = cust_by_name.get(name) or cust_by_norm.get(nn)
        dealt = _truthy(col("是否已成交"))
        if cust is None:
            near = next((c1 for k1, c1 in cust_by_norm.items() if _similar(nn, k1)), None)
            if near:
                warnings.append(f"「{name}」与已有客户「{near.company_name}」名称疑似重复，已按新客户建档（建议人工合并）")
            device = _s(col("设备名称"))
            situation = _s(col("客户具体情况"))
            cust = Customer(
                company_name=name[:100],
                contact_name=name[:50],
                phone=None,
                source=Source.other,
                stage=Stage.won if dealt else Stage.following,
                owner_id=sales_user.id,
                demand="｜".join(p for p in (device, situation) if p)[:200],
                next_followup_at=None if dealt else default_next,
                import_batch=batch,
            )
            new_customers.append(cust)
            customers_new += 1
            cust_by_norm.setdefault(nn, cust)
        else:
            customers_hit += 1
            if not dealt and cust.stage == Stage.won:
                cust.stage = Stage.following
        cust_by_name[name] = cust

        # 已成交商机 → 生成成交记录（报价为金额，咨询时间为日期）
        if dealt:
            ask_date = _date(col("咨询时间"))
            device_name = _s(col("设备名称"), 100) or "未填产品"
            new_deals.append(Deal(
                customer=cust,
                user_id=sales_user.id,
                deal_date=ask_date or date.today(),
                product=device_name,
                product_line=_guess_line(device_name, _s(col("客户具体情况"))),
                quantity=1,
                unit="台",
                unit_price=_num(col("报价")),
                amount=_num(col("报价")),
                sales_no=_s(col("销售手机"), 50),
                remark="｜".join(p for p in (_s(col("回访")), _s(col("备注"))) if p),
                import_batch=batch,
            ))
            deals_new += 1
            won_count += 1

    if not dry_run:
        db.add_all(new_customers)
        db.flush()
        db.add_all(new_deals)
        db.add(ImportLog(filename=file.filename or "opportunities", total=total, batch=batch,
                         success_count=customers_new + deals_new, fail_count=len(errors), user_id=user.id))
        db.commit()

    return {
        "dry_run": dry_run,
        "batch": batch,
        "sheets": used_sheets,
        "total_rows": total,
        "customers_created": customers_new,
        "customers_matched": customers_hit,
        "deals_created": deals_new if not dry_run else len(new_deals),
        "skipped": len(errors),
        "warnings": warnings[:MAX_WARN],
        "errors": errors[:MAX_WARN],
    }
