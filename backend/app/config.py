import os


class Settings:
    app_title: str = "远山不远 (YuanShan) - Multi-Agent Backend"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    jwt_secret: str = os.getenv("JWT_SECRET", "yuanshan-dev-secret-change-me")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./backend/yuanshan_dev.db")

    # Future-ready placeholders
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "")


settings = Settings()
