"""应用入口：注册全部路由 + CORS + 启动建表种子。生产关闭 docs/openapi。"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import attachments, auth, customers, dashboard, deals, exports, importer, ingest, users
from app.seed import init_db_and_seed

# 生产环境（ENABLE_DOCS=0）关闭 API 文档与 OpenAPI 结构，避免接口结构对公网暴露
docs_url = "/api/docs" if settings.ENABLE_DOCS else None
openapi_url = "/openapi.json" if settings.ENABLE_DOCS else None

app = FastAPI(title="CRM Demo", version="0.1.0", docs_url=docs_url, redoc_url=None, openapi_url=openapi_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(attachments.router)
app.include_router(exports.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(customers.router)
app.include_router(deals.router)
app.include_router(ingest.router)
app.include_router(importer.router)
app.include_router(dashboard.router)


@app.on_event("startup")
def on_startup():
    init_db_and_seed()


@app.get("/api/health")
def health():
    return {"ok": True, "app": "CRM Demo"}
