from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://relay:relay@localhost:5432/relay"
    redis_url: str = "redis://localhost:6379/0"

    secret_key: str = "change-me-in-production-use-long-random-string"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14
    algorithm: str = "HS256"

    admin_email: str = "admin@relay.local"
    admin_password: str = "RelayDemo2026!"
    admin_name: str = "Relay Admin"

    cors_origins: str = "http://localhost:3000,http://localhost:3001"
    app_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"

    slack_webhook_url: str = ""
    hubspot_access_token: str = ""

    worker_id: str = "worker-1"
    lease_seconds: int = 30
    heartbeat_seconds: int = 10
    poll_interval_seconds: float = 1.0

    export_dir: str = "data/exports"
    redis_queue_key: str = "relay:steps:ready"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
