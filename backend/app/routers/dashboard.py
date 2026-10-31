"""工作台聚合：待跟进/超期统计 + 本月业绩 + 按人排行 + 待回访清单。"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Customer, Deal, Role, Stage, User

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

ACTIVE_STAGES = (Stage.new, Stage.following)


@router.get("/summary")
def summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """工作台聚合。sales 只看自己；admin/boss 看全量。"""
    q = db.query(Customer)
    if user.role == Role.sales:
        q = q.filter(Customer.owner_id == user.id)

    now = datetime.now()
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    base = q.filter(Customer.stage.in_(ACTIVE_STAGES))
    overdue = base.filter(Customer.next_followup_at < now).count()
    today_due = base.filter(
        Customer.next_followup_at >= now, Customer.next_followup_at <= today_end
    ).count()
    week_new = q.filter(Customer.created_at >= week_start).count()

    by_source = (
        q.with_entities(Customer.source, func.count(Customer.id))
        .group_by(Customer.source)
        .all()
    )
    funnel = (
        q.with_entities(Customer.stage, func.count(Customer.id))
        .group_by(Customer.stage)
        .all()
    )

    due_rows = (
        base.filter(Customer.next_followup_at <= today_end)
        .order_by(Customer.next_followup_at.asc())
        .limit(50)
        .all()
    )
    due_list = [
        {
            "id": c.id,
            "company_name": c.company_name,
            "contact_name": c.contact_name,
            "phone": c.phone,
            "stage": c.stage.value,
            "owner_name": c.owner.name if c.owner else "",
            "next_followup_at": c.next_followup_at.isoformat() if c.next_followup_at else None,
            "overdue": bool(c.next_followup_at and c.next_followup_at < now),
        }
        for c in due_rows
    ]

    # —— 成交业绩（本月）——
    dq = db.query(Deal)
    if user.role == Role.sales:
        dq = dq.filter(Deal.user_id == user.id)
    month_amount = (
        dq.filter(Deal.deal_date >= month_start.date())
        .with_entities(func.coalesce(func.sum(Deal.amount), 0))
        .scalar()
    )
    month_units = (
        dq.filter(Deal.deal_date >= month_start.date(), Deal.unit == "台")
        .with_entities(func.coalesce(func.sum(Deal.quantity), 0))
        .scalar()
    )
    # admin/boss 视角：按人本月业绩排行
    deal_ranking = []
    if user.role != Role.sales:
        rank_rows = (
            db.query(User.name, func.sum(Deal.amount))
            .join(Deal, Deal.user_id == User.id)
            .filter(Deal.deal_date >= month_start.date(), User.is_active == True)  # noqa: E712
            .group_by(User.id, User.name)
            .order_by(func.sum(Deal.amount).desc())
            .all()
        )
        deal_ranking = [
            {"name": n, "amount": round(a or 0, 2)} for n, a in rank_rows
        ]

    return {
        "scope": "self" if user.role == Role.sales else "all",
        "overdue": overdue,
        "today_due": today_due,
        "week_new": week_new,
        "month_amount": round(month_amount or 0, 2),
        "month_units": month_units or 0,
        "deal_ranking": deal_ranking,
        "by_source": [{"source": s.value, "count": n} for s, n in by_source],
        "funnel": [{"stage": s.value, "count": n} for s, n in funnel],
        "due_list": due_list,
    }
