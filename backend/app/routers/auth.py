"""登录（phone+password → JWT）+ 当前用户信息。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import LoginIn, PasswordChange, TokenOut, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == body.phone).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "手机号或密码错误")
    if not user.is_active:
        raise HTTPException(403, "账号已停用，请联系管理员")
    token = create_access_token(user)
    return TokenOut(access_token=token, id=user.id, role=user.role, name=user.name)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    """当前登录用户信息（id/name/role），前端用于自愈旧会话缺失的 id。"""
    return user


@router.post("/change-password")
def change_password(
    body: PasswordChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(400, "原密码错误")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}
