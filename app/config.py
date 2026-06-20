import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Notification Service"

    # "sqlite:///./notifications.db" for local dev, or a Postgres URL in production,
    # e.g. "postgresql://user:pass@localhost:5432/notifications"
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./notifications.db")

    # "memory" for local dev/demo (no external dependency), "redis" for durable,
    # multi-process queueing in staging/production.
    queue_backend: str = os.getenv("QUEUE_BACKEND", "memory")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    rate_limit_per_hour: int = int(os.getenv("RATE_LIMIT_PER_HOUR", "100"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    retry_base_delay_seconds: int = int(os.getenv("RETRY_BASE_DELAY_SECONDS", "5"))
    worker_poll_interval: float = float(os.getenv("WORKER_POLL_INTERVAL", "0.5"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"


settings = Settings()
