import os
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Literal


class Config(BaseSettings):
    ENV: Literal["local", "dev", "production"] = "dev"

    PROJECT_NAME: str
    BACKEND_CORS_ORIGINS: Optional[List[str]] = ["*"]

    DATABASE_NAME: str
    DATABASE_URL: str

    TELEGRAM_BOT_TOKEN: str

    API_BASE_URL: str
    FRONTEND_URL: Optional[str] = None

    SENTRY_DSN: Optional[str] = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0
    SENTRY_ENVIRONMENT: Optional[str] = None

    METRICS_TOKEN: Optional[str] = None
    FLAGSMITH_TOKEN: Optional[str] = None

    JWT_SECRET_KEY: str
    PASSWORDS_SALT_SECRET_KEY: str

    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_SENDER: Optional[str] = None
    START_TLS: bool = True
    USE_TLS: bool = False

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env" if os.getenv("ENV") != "production" else None,
        env_file_encoding="utf-8",
    )


config = Config()
