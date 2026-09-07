import os
from pathlib import Path

from dotenv import load_dotenv

# Always load the backend's own .env file.  Relying on the process working
# directory caused deployments/local starts from the repository root to miss
# backend/.env and silently fall back to the SQLite development database.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _origin_list(name: str, default: str) -> list:
    raw = os.getenv(name, default) or default
    return [item.strip() for item in raw.split(",") if item.strip()]


def _default_database_url() -> str:
    if os.getenv("VERCEL"):
        return "sqlite:////tmp/schoolassist.db"
    return "sqlite:///./schoolassist.db"


class Settings:
    """Central configuration loaded from environment variables (.env)."""

    PROJECT_NAME: str = "SchoolAssist API"
    API_PREFIX: str = "/api"

    # Database (Supabase PostgreSQL in production; SQLite fallback for local dev)
    DATABASE_URL: str = (os.getenv("DATABASE_URL") or "").strip() or _default_database_url()

    # JWT auth
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY") or "schoolassist-dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    # Alibaba Model Studio / Qwen (OpenAI-compatible endpoint)
    DASHSCOPE_API_KEY: str = (os.getenv("DASHSCOPE_API_KEY") or "").strip()
    QWEN_BASE_URL: str = (
        os.getenv("QWEN_BASE_URL") or "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    ).strip()
    QWEN_MODEL: str = (os.getenv("QWEN_MODEL") or "qwen-plus").strip()

    # CORS
    ALLOWED_ORIGINS: list = _origin_list("ALLOWED_ORIGINS", "http://localhost:4200")

    # Outbound email (teacher credentials etc.). Optional: when SMTP_HOST is
    # not configured the app surfaces credentials in the UI instead.
    SMTP_HOST: str = (os.getenv("SMTP_HOST") or "").strip()
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = (os.getenv("SMTP_USER") or "").strip()
    SMTP_PASSWORD: str = (os.getenv("SMTP_PASSWORD") or "").strip()
    SMTP_STARTTLS: bool = os.getenv("SMTP_STARTTLS", "true").strip().lower() != "false"
    MAIL_FROM: str = (os.getenv("MAIL_FROM") or "no-reply@schoolassist.pk").strip()



settings = Settings()
