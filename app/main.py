import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import models  # noqa: F401 - import registers all tables with Base before create_all()
from app.api import analytics, notifications, preferences, templates
from app.core.logging_config import configure_logging
from app.database import Base, engine
from app.queue.factory import get_queue

configure_logging()
logger = logging.getLogger("notification_service.main")

app = FastAPI(
    title="Notification Service",
    description=(
        "Multi-channel (email/SMS/push) notification service with priority queues, "
        "user preferences, templates, retries with backoff, idempotency, and rate limiting."
    ),
    version="1.0.0",
)


@app.on_event("startup")
def on_startup() -> None:
    # For a real production deployment, replace this with Alembic migrations
    # so schema changes are versioned and reviewable instead of "whatever the
    # models say right now." Fine for local dev / this assignment's scope.
    Base.metadata.create_all(bind=engine)
    logger.info("startup_complete")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_exception", extra={"path": str(request.url)})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", tags=["health"])
def health_check():
    """Liveness/readiness probe. Also reports current queue depth per priority."""
    queue = get_queue()
    return {"status": "ok", "queue_depth": queue.queue_depth()}


app.include_router(notifications.router)
app.include_router(preferences.router)
app.include_router(analytics.router)
app.include_router(templates.router)
