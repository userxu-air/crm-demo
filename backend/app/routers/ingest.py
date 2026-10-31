"""外部 bot 写入口（X-API-Key + 限频）：灵犀 bot/企微推送线索用，V2 预留。"""

import time
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Customer, Role, Source, Stage, User

router = APIRouter(prefix="/api/leads", tags=["ingest"])

_rate: dict[str, list] = defaultdict(lambda: [0, time.time()])
RATE_LIMIT = 60  # 次/分钟/IP


def _check_rate(key: str):
    # 防内存泄漏：顺带清理超过 5 分钟未活跃的窗口
    now0 = time.time()
    for k in [k for k, v in _rate.items() if now0 - v[1] > 300]:
        del _rate[k]
    count, window_start = _rate[key]
    now = time.time()
    if now - window_start > 60:
        _rate[key] = [1, now]
        return
    count += 1
    _rate[key] = [count, window_start]
    if count > RATE_LIMIT:
        raise HTTPException(429, "请求过于频繁，请稍后再试")


@router.post("/ingest", status_code=201)
def ingest_lead(
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: str = Header(default=""),
):
    """bot 写入预留口：Header X-API-Key 认证。V2 接灵犀 bot 零后端改动。

    body: {company_name, contact_name, phone, source?, remark?, owner_id?}
    """
    _check_rate(request.client.host if request.client else "anon")
    if x_api_key != settings.INGEST_API_KEY:
        raise HTTPException(401, "X-API-Key 无效")

    company_name = (body.get("company_name") or "").strip()
    phone = (body.get("phone") or "").strip()
    if not company_name or not phone:
        raise HTTPException(422, "company_name 与 phone 为必填")

    dup = db.query(Customer).filter(Customer.phone == phone).first()
    if dup:
        return {"status": "skipped", "reason": "duplicate", "customer_id": dup.id}

    owner_id = body.get("owner_id")
    if owner_id and db.get(User, owner_id):
        pass
    else:
        admin = (
            db.query(User)
            .filter(User.role == Role.admin, User.is_active.is_(True))
            .order_by(User.id)
            .first()
        )
        owner_id = admin.id if admin else None
    if not owner_id:
        raise HTTPException(500, "系统无活跃管理员，无法归属线索")

    source = body.get("source") or "wecom"
    try:
        source_enum = Source(source)
    except ValueError:
        raise HTTPException(422, f"source 非法，允许值：{[s.value for s in Source]}")

    c = Customer(
        company_name=company_name,
        contact_name=body.get("contact_name", ""),
        phone=phone,
        source=source_enum,
        stage=Stage.new,
        owner_id=owner_id,
        demand=body.get("remark", ""),
        next_followup_at=datetime.now() + timedelta(days=settings.DEFAULT_FOLLOWUP_DAYS),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"status": "created", "customer_id": c.id}
