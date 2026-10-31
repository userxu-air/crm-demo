"""ORM 模型 6 张表：users / customers(线索客户合一) / followups / deals / attachments / import_logs。"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Role(str, enum.Enum):
    admin = "admin"
    sales = "sales"
    boss = "boss"


class Source(str, enum.Enum):
    sales_init = "sales_init"  # 销售自拓
    referral = "referral"      # 转介绍
    aigopo = "aigopo"          # 爱采购
    website = "website"        # 官网
    wecom = "wecom"            # 企微
    tel = "tel"                # 电话
    other = "other"


class Stage(str, enum.Enum):
    new = "new"          # 新线索
    following = "following"  # 跟进中
    won = "won"          # 成交
    lost = "lost"        # 流失


class FollowMethod(str, enum.Enum):
    tel = "tel"
    wechat = "wechat"
    visit = "visit"
    email = "email"


class ProductLine(str, enum.Enum):
    """产品线（对照销售明细表"产品简称"列归纳，业绩汇总按此统计）。"""

    right_angle = "right_angle"        # 直角
    big_right_angle = "big_right_angle"  # 大直角
    flat = "flat"                      # 平面
    high_speed_flat = "high_speed_flat"  # 高速平面
    round_bottle = "round_bottle"      # 圆瓶
    vision = "vision"                  # 视觉
    box_folding = "box_folding"        # 折盒机
    roller = "roller"                  # 滚贴
    precision = "precision"            # 高精度吸贴/治具
    consumable = "consumable"          # 标签耗材
    other = "other"                    # 其他


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    role: Mapped[Role] = mapped_column(SAEnum(Role))
    password_hash: Mapped[str] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(default=True)
    monthly_target: Mapped[float] = mapped_column(default=0)  # 月度业绩目标（业绩汇总"达成占比"用）
    in_sales_report: Mapped[bool] = mapped_column(default=True)  # 是否参与业绩汇总名单（管理员/不参与销售者关掉）
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    customers: Mapped[list["Customer"]] = relationship(back_populates="owner")


class Customer(Base):
    """线索与客户合一，stage 区分阶段。"""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_name: Mapped[str] = mapped_column(String(100), index=True)
    contact_name: Mapped[str] = mapped_column(String(50), default="")
    phone: Mapped[str | None] = mapped_column(String(30), index=True)  # 可空：历史导入客户常无电话，界面显示'-'
    wechat: Mapped[str] = mapped_column(String(50), default="")
    source: Mapped[Source] = mapped_column(SAEnum(Source), default=Source.sales_init)
    stage: Mapped[Stage] = mapped_column(SAEnum(Stage), default=Stage.new, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    region: Mapped[str] = mapped_column(String(50), default="")
    demand: Mapped[str] = mapped_column(Text, default="")
    last_contacted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    next_followup_at: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    import_batch: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)  # 导入批次（溯源：哪次导入进来的）
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)

    owner: Mapped["User"] = relationship(back_populates="customers")
    followups: Mapped[list["Followup"]] = relationship(
        back_populates="customer", order_by="Followup.created_at.desc()"
    )


class Followup(Base):
    __tablename__ = "followups"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    method: Mapped[FollowMethod] = mapped_column(SAEnum(FollowMethod))
    content: Mapped[str] = mapped_column(Text)
    next_followup_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    customer: Mapped["Customer"] = relationship(back_populates="followups")
    user: Mapped["User"] = relationship()


class Deal(Base):
    """成交记录（流水）：客户详情页录入，业绩汇总/表格导出的数据源。"""

    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    deal_date: Mapped[datetime] = mapped_column(index=True)  # 成交日期
    product: Mapped[str] = mapped_column(String(100))  # 产品名称
    product_line: Mapped[ProductLine] = mapped_column(SAEnum(ProductLine), default=ProductLine.other, index=True)
    quantity: Mapped[float] = mapped_column(default=1)
    unit: Mapped[str] = mapped_column(String(10), default="台")
    unit_price: Mapped[float] = mapped_column(default=0)
    amount: Mapped[float] = mapped_column(default=0)  # 成交金额
    invoice_type: Mapped[str] = mapped_column(String(20), default="")  # 开票类型
    account: Mapped[str] = mapped_column(String(50), default="")  # 收款账户
    sales_no: Mapped[str] = mapped_column(String(50), default="")  # 来源号（示例号/AI号等）
    repurchase: Mapped[bool] = mapped_column(default=False)
    remark: Mapped[str] = mapped_column(Text, default="")
    import_batch: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)  # 导入批次（溯源）
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    customer: Mapped["Customer"] = relationship()
    user: Mapped["User"] = relationship()


class Attachment(Base):
    """客户附件（合同 PDF / 交易明细等），文件存服务器磁盘。"""

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(255))  # 原始文件名
    stored_name: Mapped[str] = mapped_column(String(255), unique=True)  # uuid 存储名
    size: Mapped[int] = mapped_column(default=0)
    content_type: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    customer: Mapped["Customer"] = relationship()
    user: Mapped["User"] = relationship()


class ImportLog(Base):
    __tablename__ = "import_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(200))
    batch: Mapped[str] = mapped_column(String(36), default="")
    total: Mapped[int] = mapped_column(default=0)
    success_count: Mapped[int] = mapped_column(default=0)
    fail_count: Mapped[int] = mapped_column(default=0)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
