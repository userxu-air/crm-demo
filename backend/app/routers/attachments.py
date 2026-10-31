"""客户附件：multipart 上传（白名单+20MB）、下载、删除（同步磁盘）。权限随客户，boss 只读。"""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Attachment, Customer, Role, User
from app.schemas import AttachmentOut

router = APIRouter(prefix="/api", tags=["attachments"])

ALLOWED_EXT = {".pdf", ".xlsx", ".xls", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".csv", ".txt"}


def _upload_dir() -> Path:
    p = Path(settings.UPLOAD_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _can_read(user: User, customer: Customer) -> bool:
    if user.role in (Role.admin, Role.boss):
        return True
    return customer.owner_id == user.id


def _get_customer_or_403(user: User, customer_id: int, db: Session) -> Customer:
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(404, "客户不存在")
    if not _can_read(user, c):
        raise HTTPException(403, "无权访问该客户")
    return c


@router.get("/customers/{customer_id}/attachments", response_model=list[AttachmentOut])
def list_attachments(
    customer_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_customer_or_403(user, customer_id, db)
    rows = (
        db.query(Attachment)
        .filter(Attachment.customer_id == customer_id)
        .order_by(Attachment.created_at.desc())
        .all()
    )
    out = []
    for a in rows:
        o = AttachmentOut.model_validate(a)
        o.uploader_name = a.user.name if a.user else ""
        out.append(o)
    return out


@router.post("/customers/{customer_id}/attachments", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    customer_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传客户附件（合同 PDF / 交易明细等），≤20MB，白名单类型。"""
    if user.role == Role.boss:
        raise HTTPException(403, "老板账号为只读")
    c = _get_customer_or_403(user, customer_id, db)

    orig = os.path.basename(file.filename or "unnamed")
    ext = Path(orig).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"不支持的文件类型 {ext}，仅允许：PDF/Excel/Word/图片/CSV/TXT")
    content = await file.read()
    if len(content) > settings.UPLOAD_MAX_MB * 1024 * 1024:
        raise HTTPException(400, f"文件超过 {settings.UPLOAD_MAX_MB}MB 限制")

    stored = f"{uuid.uuid4().hex}{ext}"
    dest = _upload_dir() / stored
    with open(dest, "wb") as f:
        f.write(content)

    a = Attachment(
        customer_id=c.id,
        uploaded_by=user.id,
        filename=orig,
        stored_name=stored,
        size=len(content),
        content_type=file.content_type or "",
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    o = AttachmentOut.model_validate(a)
    o.uploader_name = user.name
    return o


@router.get("/attachments/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    a = db.get(Attachment, attachment_id)
    if not a:
        raise HTTPException(404, "附件不存在")
    c = db.get(Customer, a.customer_id)
    if not _can_read(user, c):
        raise HTTPException(403, "无权下载该附件")
    path = _upload_dir() / a.stored_name
    if not path.exists():
        raise HTTPException(404, "文件已丢失，请联系管理员")
    return FileResponse(
        path,
        filename=a.filename,
        media_type=a.content_type or "application/octet-stream",
    )


@router.delete("/attachments/{attachment_id}", status_code=204)
def delete_attachment(
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除附件（admin 或上传者），同时删除磁盘文件。"""
    if user.role == Role.boss:
        raise HTTPException(403, "老板账号为只读")
    a = db.get(Attachment, attachment_id)
    if not a:
        raise HTTPException(404, "附件不存在")
    if user.role != Role.admin and a.uploaded_by != user.id:
        raise HTTPException(403, "仅管理员或上传者可删除")
    path = _upload_dir() / a.stored_name
    if path.exists():
        os.remove(path)
    db.delete(a)
    db.commit()
