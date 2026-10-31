"""成交记录：客户详情流水 + 全量流水查询（带汇总）。金额=显式值优先，否则数量×单价；添加成交自动转 won。"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user
from app.models import Customer, Deal, Role, Stage, User
from app.schemas import DealCreate, DealOut, DealUpdate

router = APIRouter(prefix="/api", tags=["deals"])


def _to_out(d: Deal) -> DealOut:
    o = DealOut.model_validate(d)
    o.user_name = d.user.name if d.user else ""
    o.company_name = d.customer.company_name if d.customer else ""
    return o


def _get_customer_or_403(user: User, customer_id: int, db: Session) -> Customer:
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(404, "客户不存在")
    if user.role == Role.admin or user.role == Role.boss:  # boss 只读
        return c
    if user.role == Role.sales and c.owner_id == user.id:
        return c
    raise HTTPException(403, "无权访问该客户")


@router.get("/customers/{customer_id}/deals", response_model=list[DealOut])
def list_customer_deals(
    customer_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_customer_or_403(user, customer_id, db)
    rows = (
        db.query(Deal)
        .filter(Deal.customer_id == customer_id)
        .order_by(Deal.deal_date.desc(), Deal.id.desc())
        .all()
    )
    return [_to_out(d) for d in rows]


@router.post("/customers/{customer_id}/deals", response_model=DealOut, status_code=201)
def create_deal(
    customer_id: int,
    body: DealCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """添加成交记录；客户未成交时自动转 won。"""
    if user.role == Role.boss:
        raise HTTPException(403, "老板账号为只读")
    c = _get_customer_or_403(user, customer_id, db)
    amount = body.amount if body.amount > 0 else round(body.quantity * body.unit_price, 2)
    d = Deal(
        customer_id=c.id,
        user_id=user.id,
        deal_date=body.deal_date or date.today(),
        product=body.product,
        product_line=body.product_line,
        quantity=body.quantity,
        unit=body.unit,
        unit_price=body.unit_price,
        amount=amount,
        invoice_type=body.invoice_type,
        account=body.account,
        sales_no=body.sales_no,
        repurchase=body.repurchase,
        remark=body.remark,
    )
    db.add(d)
    if c.stage in (Stage.new, Stage.following):
        c.stage = Stage.won
        c.next_followup_at = None
    db.commit()
    db.refresh(d)
    return _to_out(d)


def _get_deal_or_403(user: User, deal_id: int, db: Session) -> Deal:
    d = db.get(Deal, deal_id)
    if not d:
        raise HTTPException(404, "成交记录不存在")
    if user.role == Role.admin:
        return d
    if user.role == Role.sales and d.user_id == user.id:
        return d
    raise HTTPException(403, "无权操作该成交记录")


@router.patch("/deals/{deal_id}", response_model=DealOut)
def update_deal(
    deal_id: int,
    body: DealUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role == Role.boss:
        raise HTTPException(403, "老板账号为只读")
    d = _get_deal_or_403(user, deal_id, db)
    data = body.model_dump(exclude_unset=True)
    # 金额留空/0 → 按数量×单价重算；显式给了正数金额则以用户为准
    if data.get("amount") in (None, 0):
        data.pop("amount", None)
    if "amount" not in data:
        q = data.get("quantity", d.quantity)
        p = data.get("unit_price", d.unit_price)
        data["amount"] = round(q * p, 2)
    for k, v in data.items():
        if v is not None:
            setattr(d, k, v)
    db.commit()
    db.refresh(d)
    return _to_out(d)


@router.delete("/deals/{deal_id}", status_code=204)
def delete_deal(
    deal_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除成交记录（仅管理员）。"""
    if user.role != Role.admin:
        raise HTTPException(403, "仅管理员可删除成交记录")
    d = _get_deal_or_403(user, deal_id, db)
    db.delete(d)
    db.commit()


@router.get("/deals")
def list_deals(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    start: date | None = None,
    end: date | None = None,
    user_id: int | None = None,
    product_line: str | None = None,
    keyword: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """全量流水查询（sales 仅本人，admin/boss 全量）——表格导出/统计的数据源。"""
    q = db.query(Deal).options(joinedload(Deal.user), joinedload(Deal.customer))
    if user.role == Role.sales:
        q = q.filter(Deal.user_id == user.id)
    elif user_id:
        q = q.filter(Deal.user_id == user_id)
    if start:
        q = q.filter(Deal.deal_date >= start)
    if end:
        q = q.filter(Deal.deal_date <= end)
    if product_line:
        q = q.filter(Deal.product_line == product_line)
    if keyword:
        like = f"%{keyword}%"
        q = q.join(Customer, Deal.customer_id == Customer.id).filter(
            Customer.company_name.ilike(like)
        )
    total = q.count()
    sum_amount = q.with_entities(func.coalesce(func.sum(Deal.amount), 0)).scalar()
    sum_qty = (
        q.filter(Deal.unit == "台").with_entities(func.coalesce(func.sum(Deal.quantity), 0)).scalar()
    )
    items = (
        q.order_by(Deal.deal_date.desc(), Deal.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "total_amount": round(sum_amount or 0, 2),
        "total_units": sum_qty or 0,
        "items": [_to_out(d) for d in items],
    }
