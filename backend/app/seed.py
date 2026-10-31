"""启动时建表（create_all）+ 轻量加列迁移（ensure_column）+ 种子管理员。"""

import logging

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import Role, User
from app.security import hash_password

logger = logging.getLogger("yuecrm.seed")


def _ensure_column(engine, table: str, column: str, ddl: str):
    """轻量迁移：表存在但缺列时补列（PG 用 IF NOT EXISTS，SQLite 用 PRAGMA 检查）。"""
    from sqlalchemy import text

    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {ddl}"))
    else:  # sqlite
        with engine.connect() as conn:
            cols = [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))]
        if column not in cols:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def _ensure_phone_nullable(engine):
    """迁移：customers.phone 释放 NOT NULL（历史导入客户常无电话，空值不占唯一索引位）。"""
    from sqlalchemy import inspect, text

    cols = {c["name"]: c for c in inspect(engine).get_columns("customers")}
    if "phone" not in cols or cols["phone"].get("nullable", True):
        return
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text("ALTER TABLE customers ALTER COLUMN phone DROP NOT NULL"))
            logger.info("已迁移：customers.phone 改为可空")
        else:  # sqlite：标准表重建
            conn.execute(text("ALTER TABLE customers RENAME TO customers_old"))
            conn.execute(text("""
                CREATE TABLE customers (
                    id INTEGER NOT NULL PRIMARY KEY,
                    company_name VARCHAR(100) NOT NULL,
                    contact_name VARCHAR(50),
                    phone VARCHAR(30),
                    wechat VARCHAR(50),
                    source VARCHAR(10) NOT NULL,
                    stage VARCHAR(10) NOT NULL,
                    owner_id INTEGER NOT NULL REFERENCES users (id),
                    region VARCHAR(50),
                    demand TEXT,
                    last_contacted_at DATETIME,
                    next_followup_at DATETIME,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )"""))
            conn.execute(text("""
                INSERT INTO customers (id, company_name, contact_name, phone, wechat, source, stage,
                                       owner_id, region, demand, last_contacted_at, next_followup_at,
                                       created_at, updated_at)
                SELECT id, company_name, contact_name, phone, wechat, source, stage,
                       owner_id, region, demand, last_contacted_at, next_followup_at,
                       created_at, updated_at
                FROM customers_old"""))
            conn.execute(text("DROP TABLE customers_old"))
            logger.info("已迁移：customers.phone 改为可空（SQLite 表重建）")


def init_db_and_seed():
    """开发/首次部署：直接建表 + 种子管理员。生产改表后续用 Alembic 管理。"""
    Base.metadata.create_all(bind=engine)
    _ensure_column(engine, "users", "monthly_target", "FLOAT DEFAULT 0")
    # 布尔默认值方言自适应：PG 要求 TRUE，SQLite 只认 1
    _bool_ddl = "BOOLEAN DEFAULT TRUE" if engine.dialect.name == "postgresql" else "BOOLEAN DEFAULT 1"
    _ensure_column(engine, "users", "in_sales_report", _bool_ddl)
    _ensure_column(engine, "customers", "import_batch", "VARCHAR(36)")
    _ensure_column(engine, "deals", "import_batch", "VARCHAR(36)")
    _ensure_column(engine, "import_logs", "batch", "VARCHAR(36) DEFAULT ''")
    _ensure_phone_nullable(engine)
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            admin = User(
                name="管理员",
                phone=settings.SEED_ADMIN_PHONE,
                role=Role.admin,
                password_hash=hash_password(settings.SEED_ADMIN_PASSWORD),
            )
            db.add(admin)
            db.commit()
            logger.info(
                "已创建初始管理员：%s（请首次登录后立即修改密码）",
                settings.SEED_ADMIN_PHONE,
            )
        # 管理员默认不参与销售业绩名单（可在账号管理打开）——布尔字面量方言自适应
        from sqlalchemy import text
        f, v = ("FALSE", "TRUE") if engine.dialect.name == "postgresql" else ("0", "1")
        with engine.begin() as conn:
            conn.execute(text(f"UPDATE users SET in_sales_report = {f} WHERE role = 'admin' AND in_sales_report = {v}"))
    finally:
        db.close()
