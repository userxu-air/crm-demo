"""环境配置（pydantic-settings）：.env 优先，默认值适配本地开发。"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """开发默认 SQLite；生产用环境变量切 PostgreSQL。"""

    DATABASE_URL: str = "sqlite:///./dev.db"
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_EXPIRE_HOURS: int = 12
    INGEST_API_KEY: str = "dev-ingest-key-change-me"
    DEFAULT_FOLLOWUP_DAYS: int = 3
    SEED_ADMIN_PHONE: str = "13800000001"
    SEED_ADMIN_PASSWORD: str = "admin123"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    ENABLE_DOCS: bool = True
    UPLOAD_DIR: str = "./uploads"
    UPLOAD_MAX_MB: int = 20
    TEMPLATE_DIR: str = "./templates"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
