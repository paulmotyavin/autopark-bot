from functools import lru_cache
from typing import Any, Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """Настройки из переменных окружения; для локальной разработки читается .env.

    Реальные переменные окружения имеют приоритет над .env. В Docker-образ .env не
    копируется: compose передаёт его через env_file.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Telegram ---
    bot_token: SecretStr
    telegram_proxy: SecretStr | None = None
    owner_tg_id: int

    # --- PostgreSQL ---
    db_host: str
    db_port: int = 5432
    db_user: str
    db_password: SecretStr
    db_name: str
    db_ssl_mode: str | None = None
    db_pool_size: int = 5
    db_max_overflow: int = 5

    # --- Redis (FSM) ---
    redis_url: str = "redis://redis:6379/0"
    fsm_ttl_hours: int = 48

    # --- S3 ---
    s3_endpoint_url: str
    s3_region: str
    s3_bucket: str
    s3_access_key: SecretStr
    s3_secret_key: SecretStr
    s3_presign_ttl_seconds: int = 300

    # --- Приложение ---
    timezone: str = "Europe/Moscow"
    invite_ttl_hours: int = 72
    healthcheck_url: str | None = None
    healthcheck_interval_minutes: int = 5
    log_level: str = "INFO"
    log_format: Literal["pretty", "json"] = "pretty"

    @field_validator("telegram_proxy", "healthcheck_url", "db_ssl_mode", mode="before")
    @classmethod
    def _empty_to_none(cls, value: Any) -> Any:
        # В .env пустая строка («TELEGRAM_PROXY=») должна означать «не задано».
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def database_url(self) -> URL:
        # URL.create сам экранирует спецсимволы в пароле.
        return URL.create(
            "postgresql+asyncpg",
            username=self.db_user,
            password=self.db_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )

    @property
    def db_connect_args(self) -> dict[str, Any]:
        return {"ssl": self.db_ssl_mode} if self.db_ssl_mode else {}


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # поля читаются из окружения
