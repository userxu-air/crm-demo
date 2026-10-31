"""账号管理（仅 admin）：增删改查 + 重置密码 + 月度目标 + 参与业绩开关。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import Customer, Role, User
from app.schemas import UserCreate, UserOut, UserUpdate
from app.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])

admin_only = require_roles(Role.admin)


@router.get("", response_model=list[UserOut])
def list_users(_: User = Depends(admin_only), db: Session = Depends(get_db)):
    return db.query(User).order_by(User.id).all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    if db.query(User).filter(User.phone == body.phone).first():
        raise HTTPException(409, f"手机号 {body.phone} 已存在")
    user = User(
        name=body.name,
        phone=body.phone,
        role=body.role,
        password_hash=hash_password(body.password),
        monthly_target=body.monthly_target,
        in_sales_report=body.in_sales_report,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    admin: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    """管理员删除账号。保护：不能删自己；名下有客户需先转移；不能删最后一个管理员。"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if user.id == admin.id:
        raise HTTPException(400, "不能删除自己")
    owned = db.query(Customer).filter(Customer.owner_id == user.id).count()
    if owned > 0:
        raise HTTPException(409, f"该账号名下还有 {owned} 家客户，请先在客户详情页转移后再删除")
    if user.role == Role.admin:
        admins = db.query(User).filter(User.role == Role.admin, User.is_active == True).count()  # noqa: E712
        if admins <= 1:
            raise HTTPException(400, "系统至少保留一个管理员")
    db.delete(user)
    db.commit()


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    admin: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if body.name is not None:
        user.name = body.name
    if body.phone is not None and body.phone and body.phone != user.phone:
        dup = db.query(User).filter(User.phone == body.phone, User.id != user_id).first()
        if dup:
            raise HTTPException(409, f"手机号已被「{dup.name}」占用")
        user.phone = body.phone
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        if user.id == admin.id and not body.is_active:
            raise HTTPException(400, "不能停用自己")
        user.is_active = body.is_active
    if body.password is not None:
        user.password_hash = hash_password(body.password)
    if body.monthly_target is not None:
        user.monthly_target = body.monthly_target
    if body.in_sales_report is not None:
        user.in_sales_report = body.in_sales_report
    db.commit()
    db.refresh(user)
    return user
