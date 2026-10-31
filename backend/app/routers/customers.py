"""客户 CRUD + 防撞单 + 阶段流转 + 跟进记录（含编辑/删除，最新一条同步客户提醒）。行级隔离：sales 只见自己，boss 只读。"""

import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import (
    Attachment,
    Customer,
    Deal,
    Followup,
    Role,
    Stage,
    User,
)
from app.schemas import (
    CustomerCreate,
    CustomerOut,
    CustomerUpdate,
    FollowupCreate,
    FollowupOut,
    FollowupUpdate,
    StageUpdate,
)

router = APIRouter(prefix="/api/customers", tags=["customers"])

ACTIVE_STAGES = (Stage.new, Stage.following)


def _norm_phone(p: str | None) -> str | None:
    """手机号归一存储：去非数字、去 86 前缀（防 +86/横线/空格变体绕过防撞单）。"""
    if not p:
        return p
    digits = re.sub(r"\D", "", p)
    if not digits:
        return p
    return digits[2:] if digits.startswith("86") and len(digits) > 11 else digits


def _default_next_followup(dt: datetime | None) -> datetime:
    """3 天回访规则：未设定时自动 +3 天。"""
    if dt is not None:
        return dt
    return datetime.now() + timedelta(days=settings.DEFAULT_FOLLOWUP_DAYS)


def _to_out(c: Customer) -> CustomerOut:
    out = CustomerOut.model_validate(c)
    out.owner_name = c.owner.name if c.owner else ""
    return out


def _get_customer_or_403(user: User, customer_id: int, db: Session) -> Customer:
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(404, "客户不存在")
    if user.role == Role.admin or user.role == Role.boss:  # boss 只读
        return c
    if user.role == Role.sales and c.owner_id == user.id:
        return c
    raise HTTPException(403, "无权访问该客户")


@router.get("")
def list_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source: str | None = None,
    stage: str | None = None,
    owner_id: int | None = None,
    keyword: str | None = None,
    overdue: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Customer).options(joinedload(Customer.owner))
    if user.role == Role.sales:
        q = q.filter(Customer.owner_id == user.id)  # 行级隔离：销售只看自己
    elif owner_id:
        q = q.filter(Customer.owner_id == owner_id)  # admin/boss 按负责人筛选
    if source:
        q = q.filter(Customer.source == source)
    if stage:
        q = q.filter(Customer.stage == stage)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            or_(
                Customer.company_name.ilike(like),
                Customer.contact_name.ilike(like),
                Customer.phone.ilike(like),
            )
        )
    if overdue:
        q = q.filter(
            Customer.next_followup_at < datetime.now(),
            Customer.stage.in_(ACTIVE_STAGES),
        )
    total = q.count()
    items = (
        q.order_by(Customer.next_followup_at.asc().nullslast(), Customer.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "items": [_to_out(c) for c in items]}


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(
    body: CustomerCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role == Role.boss:
        raise HTTPException(403, "老板账号为只读")
    dup = (
        db.query(Customer).filter(Customer.phone == body.phone).first() if body.phone else None
    )
    if dup:
        owner_name = dup.owner.name if dup.owner else "未知"
        raise HTTPException(409, f"手机号已存在，客户「{dup.company_name}」归属：{owner_name}，防撞单拦截")
    if user.role == Role.sales:
        owner_id = user.id  # 销售新建自动归属本人
    else:
        owner_id = body.owner_id or user.id
        if not db.get(User, owner_id):
            raise HTTPException(400, "指定的负责人不存在")
    c = Customer(
        company_name=body.company_name,
        contact_name=body.contact_name,
        phone=_norm_phone(body.phone),
        wechat=body.wechat,
        source=body.source,
        stage=Stage.new,
        owner_id=owner_id,
        region=body.region,
        demand=body.demand,
        next_followup_at=_default_next_followup(body.next_followup_at),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _to_out(c)


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _to_out(_get_customer_or_403(user, customer_id, db))


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: int,
    body: CustomerUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role == Role.boss:
        raise HTTPException(403, "老板账号为只读")
    c = _get_customer_or_403(user, customer_id, db)
    data = body.model_dump(exclude_unset=True)
    if "owner_id" in data:
        if user.role != Role.admin:
            raise HTTPException(403, "仅管理员可转移负责人")
        if not db.get(User, data["owner_id"]):
            raise HTTPException(400, "目标负责人不存在")
    if "phone" in data and data["phone"]:
        data["phone"] = _norm_phone(data["phone"])
    if "phone" in data and data["phone"] and data["phone"] != c.phone:
        dup = db.query(Customer).filter(Customer.phone == data["phone"], Customer.id != c.id).first()
        if dup:
            raise HTTPException(409, f"手机号已被客户「{dup.company_name}」占用")
    if "stage" in data and data["stage"] in (Stage.won, Stage.lost):
        data["next_followup_at"] = None  # 成交/流失后退出提醒
    for k, v in data.items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return _to_out(c)


@router.post("/{customer_id}/stage", response_model=CustomerOut)
def change_stage(
    customer_id: int,
    body: StageUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role == Role.boss:
        raise HTTPException(403, "老板账号为只读")
    c = _get_customer_or_403(user, customer_id, db)
    c.stage = body.stage
    if body.stage in (Stage.won, Stage.lost):
        c.next_followup_at = None
    db.commit()
    db.refresh(c)
    return _to_out(c)


@router.delete("/{customer_id}", status_code=204)
def delete_customer(
    customer_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理员删除客户（级联删除跟进记录，不可恢复，每日备份兜底）。"""
    if user.role != Role.admin:
        raise HTTPException(403, "仅管理员可删除客户")
    c = _get_customer_or_403(user, customer_id, db)
    db.query(Followup).filter(Followup.customer_id == c.id).delete()
    db.query(Deal).filter(Deal.customer_id == c.id).delete()
    for att in db.query(Attachment).filter(Attachment.customer_id == c.id).all():
        p = Path(settings.UPLOAD_DIR) / att.stored_name
        if p.exists():
            os.remove(p)  # 同步删磁盘文件
        db.delete(att)
    db.delete(c)
    db.commit()


@router.get("/{customer_id}/followups", response_model=list[FollowupOut])
def list_followups(
    customer_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_customer_or_403(user, customer_id, db)
    rows = (
        db.query(Followup)
        .filter(Followup.customer_id == customer_id)
        .order_by(Followup.created_at.desc())
        .all()
    )
    outs = []
    for f in rows:
        o = FollowupOut.model_validate(f)
        o.user_name = f.user.name if f.user else ""
        outs.append(o)
    return outs


@router.post("/{customer_id}/followups", response_model=FollowupOut, status_code=201)
def create_followup(
    customer_id: int,
    body: FollowupCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role == Role.boss:
        raise HTTPException(403, "老板账号为只读")
    c = _get_customer_or_403(user, customer_id, db)
    f = Followup(
        customer_id=c.id,
        user_id=user.id,
        method=body.method,
        content=body.content,
        next_followup_at=_default_next_followup(body.next_followup_at),
    )
    db.add(f)
    c.last_contacted_at = datetime.now()
    if c.stage == Stage.new:
        c.stage = Stage.following  # 首次跟进自动转入跟进中
    c.next_followup_at = f.next_followup_at
    db.commit()
    db.refresh(f)
    o = FollowupOut.model_validate(f)
    o.user_name = user.name
    return o


def _get_followup_or_403(user: User, followup_id: int, db: Session) -> Followup:
    f = db.get(Followup, followup_id)
    if not f:
        raise HTTPException(404, "跟进记录不存在")
    if user.role == Role.admin or f.user_id == user.id:
        return f
    raise HTTPException(403, "仅管理员或本人可操作该跟进记录")


@router.patch("/followups/{followup_id}", response_model=FollowupOut)
def update_followup(
    followup_id: int,
    body: FollowupUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """编辑跟进（admin 或本人）。"""
    if user.role == Role.boss:
        raise HTTPException(403, "老板账号为只读")
    f = _get_followup_or_403(user, followup_id, db)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        if v is not None:
            setattr(f, k, v)
    # 仅当编辑的是该客户「最新一条」跟进时，才同步客户下次提醒（避免旧跟进覆盖新提醒）
    if "next_followup_at" in data and f.customer:
        latest = (
            db.query(Followup)
            .filter(Followup.customer_id == f.customer_id)
            .order_by(Followup.created_at.desc(), Followup.id.desc())
            .first()
        )
        if latest and latest.id == f.id:
            f.customer.next_followup_at = f.next_followup_at
    db.commit()
    db.refresh(f)
    o = FollowupOut.model_validate(f)
    o.user_name = f.user.name if f.user else ""
    return o


@router.delete("/followups/{followup_id}", status_code=204)
def delete_followup(
    followup_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role == Role.boss:
        raise HTTPException(403, "老板账号为只读")
    f = _get_followup_or_403(user, followup_id, db)
    db.delete(f)
    db.commit()
