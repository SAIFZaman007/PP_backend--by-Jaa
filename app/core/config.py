"""
Central application settings, loaded from environment / .env.
"""
from functools import lru_cache

from pydantic import EmailStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    # Core
    PROJECT_NAME: str = "Peak Physique API"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./peak_physique.db"

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:5174"]

    # Frontend / redirects
    FRONTEND_URL: str = "http://localhost:5173"
    DASHBOARD_URL: str = "http://localhost:5174"

    # SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "no-reply@trainpeakphysique.com"
    SMTP_FROM_NAME: str = "Peak Physique"
    SMTP_STARTTLS: bool = True
    TRAINER_NOTIFY_EMAIL: str = "founder@trainpeakphysique.com"

    AI_CHAT_ENABLED: bool = False
    AI_CHAT_PROVIDER: str = "groq"  # "groq" | "anthropic"
    AI_CHAT_API_KEY: str = ""
    AI_CHAT_MODEL: str = "llama-3.3-70b-versatile"

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""

    # Google Calendar
    GOOGLE_CALENDAR_ENABLED: bool = False
    GOOGLE_SERVICE_ACCOUNT_FILE: str = "./google-service-account.json"
    GOOGLE_CALENDAR_ID: str = "primary"

    # --- Media / admin image uploads ---------------------------------------
    MEDIA_ROOT: str = "./media"
    MEDIA_URL_PATH: str = "/media"
    MAX_UPLOAD_MB: int = 5
    PUBLIC_BASE_URL: str = ""

    # Seed / first trainer.
    FIRST_TRAINER_EMAIL: EmailStr
    FIRST_TRAINER_PASSWORD: str
    FIRST_TRAINER_NAME: str

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        """Fail fast at startup — not deep inside a request or the seed
        script — if production is about to run with an unsafe secret."""
        if self.is_production and len(self.SECRET_KEY) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters when ENVIRONMENT=production. "
                "Generate one with `openssl rand -hex 32` and set it in your env vars."
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def stripe_enabled(self) -> bool:
        return bool(self.STRIPE_SECRET_KEY)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()