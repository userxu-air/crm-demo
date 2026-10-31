"""Pydantic 进出参模型 + 枚举中文映射（SOURCE_MAP/STAGE_MAP/PRODUCT_LINE_TEXT 等，前端导出共用）。"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models import FollowMethod, ProductLine, Role, Source, Stage

PRODUCT_LINE_TEXT = {
    ProductLine.right_angle: "直角",
    ProductLine.big_right_angle: "大直角",
    ProductLine.flat: "平面",
    ProductLine.high_speed_flat: "高速平面",
    ProductLine.round_bottle: "圆瓶",
    ProductLine.vision: "视觉",
    ProductLine.box_folding: "折盒机",
    ProductLine.roller: "滚贴",
    ProductLine.precision: "高精度吸贴",
    ProductLine.consumable: "标签耗材",
    ProductLine.other: "其他",
}


class LoginIn(BaseModel):
    phone: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    id: int
    role: Role
    name: str


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    role: Role
    is_active: bool
    monthly_target: float = 0
    in_sales_report: bool = True
    created_at: datetime


class UserCreate(BaseModel):
    name: str
    phone: str
    password: str = Field(min_length=6)
    role: Role
    monthly_target: float = 0
    in_sales_report: bool = True


class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[Role] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=6)
    monthly_target: Optional[float] = None
    in_sales_report: Optional[bool] = None


class CustomerBase(BaseModel):
    company_name: str = Field(max_length=100)
    contact_name: str = ""
    phone: Optional[str] = Field(default=None, max_length=30)  # 可空：历史导入客户常无电话
    wechat: str = ""
    source: Source = Source.sales_init
    region: str = ""
    demand: str = ""


class CustomerCreate(CustomerBase):
    next_followup_at: Optional[datetime] = None
    owner_id: Optional[int] = None  # 仅 admin 生效；sales 强制归属本人


class CustomerUpdate(BaseModel):
    company_name: Optional[str] = Field(default=None, max_length=100)
    contact_name: Optional[str] = None
    phone: Optional[str] = Field(default=None, max_length=30)
    wechat: Optional[str] = None
    source: Optional[Source] = None
    stage: Optional[Stage] = None
    owner_id: Optional[int] = None  # 仅 admin：客户交接
    region: Optional[str] = None
    demand: Optional[str] = None
    next_followup_at: Optional[datetime] = None


class CustomerOut(CustomerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stage: Stage
    owner_id: int
    owner_name: str = ""
    last_contacted_at: Optional[datetime] = None
    next_followup_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class StageUpdate(BaseModel):
    stage: Stage


class DealBase(BaseModel):
    deal_date: Optional[date] = None  # 缺省今天
    product: str = Field(min_length=1, max_length=100)
    product_line: ProductLine = ProductLine.other
    quantity: float = Field(default=1, gt=0)
    unit: str = "台"
    unit_price: float = Field(default=0, ge=0)
    amount: float = Field(default=0, ge=0)  # 缺省自动按 数量×单价
    invoice_type: str = ""
    account: str = ""
    sales_no: str = ""
    repurchase: bool = False
    remark: str = ""


class DealCreate(DealBase):
    pass


class DealUpdate(BaseModel):
    deal_date: Optional[date] = None
    product: Optional[str] = None
    product_line: Optional[ProductLine] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None
    invoice_type: Optional[str] = None
    account: Optional[str] = None
    sales_no: Optional[str] = None
    repurchase: Optional[bool] = None
    remark: Optional[str] = None


class DealOut(DealBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    user_id: int
    user_name: str = ""
    company_name: str = ""
    created_at: datetime


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    filename: str
    size: int
    content_type: str
    created_at: datetime
    uploader_name: str = ""



class FollowupCreate(BaseModel):
    method: FollowMethod
    content: str = Field(min_length=1)
    next_followup_at: Optional[datetime] = None  # 未填默认 +3 天


class FollowupUpdate(BaseModel):
    method: Optional[FollowMethod] = None
    content: Optional[str] = Field(default=None, min_length=1)
    next_followup_at: Optional[datetime] = None


class FollowupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    method: FollowMethod
    content: str
    next_followup_at: Optional[datetime] = None
    created_at: datetime
    user_id: int
    user_name: str = ""


class IngestIn(BaseModel):
    """bot 写入预留口请求体（V2 接灵犀 bot 零后端改动）。"""

    company_name: str = Field(max_length=100)
    contact_name: str = ""
    phone: str = Field(max_length=30)
    source: Source = Source.wecom
    remark: str = ""
    owner_id: Optional[int] = None  # 缺省归第一个活跃管理员
