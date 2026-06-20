import logging
import signal
import time
from datetime import datetime, timedelta
from types import FrameType
from typing import Any, Dict, Optional

from app.config import settings
from app.database import SessionLocal
from app.models import DeliveryStatus, Notification, NotificationDelivery, NotificationStatus
from app.providers.mock_providers import PROVIDER_REGISTRY
from app.queue.factory import get_queue

logger = logging.getLogger("notification_service.worker")

_running = True


def _handle_signal(signum: int, frame: Optional[FrameType]) -> None:
    global _running
    logger.info("worker_shutdown_signal_received", extra={"signal": signum})
    _running = False


def _backoff_seconds(attempt: int) -> int:
    """Exponential backoff: attempt 1 -> base, 2 -> base*2, 3 -> base*4, ..."""
    return settings.retry_base_delay_seconds * (2 ** (attempt - 1))


def process_one(payload: Dict[str, Any]) -> None:
    """Handle a single delivery job: call the provider, update DB, schedule retry if needed."""
    db = SessionLocal()
    queue = get_queue()
    try:
        delivery = (
            db.query(NotificationDelivery)
            .filter(NotificationDelivery.id == payload["delivery_id"])
            .first()
        )
        if delivery is None:
            logger.warning("delivery_not_found", extra={"delivery_id": payload.get("delivery_id")})
            return

        provider = PROVIDER_REGISTRY.get(payload["channel"])
        delivery.attempt_count += 1
        result = provider.send(
            recipient=payload["user_id"],  # see README "Assumptions": user contact info lives in another service
            subject=payload.get("subject"),
            body=payload["body"],
        )

        if result.success:
            delivery.status = DeliveryStatus.sent
            delivery.provider_message_id = result.message_id
            delivery.last_error = None
            logger.info(
                "delivery_sent",
                extra={"delivery_id": delivery.id, "channel": delivery.channel.value, "attempt": delivery.attempt_count},
            )
        else:
            delivery.last_error = result.error
            if delivery.attempt_count <= delivery.max_retries:
                delay = _backoff_seconds(delivery.attempt_count)
                run_at = datetime.utcnow() + timedelta(seconds=delay)
                delivery.next_retry_at = run_at
                delivery.status = DeliveryStatus.pending
                queue.schedule_retry(payload, run_at)
                logger.warning(
                    "delivery_retry_scheduled",
                    extra={"delivery_id": delivery.id, "attempt": delivery.attempt_count, "delay_seconds": delay},
                )
            else:
                delivery.status = DeliveryStatus.failed
                logger.error(
                    "delivery_failed_permanently",
                    extra={"delivery_id": delivery.id, "attempts": delivery.attempt_count},
                )

        db.commit()
        _update_parent_status(db, delivery.notification_id)
    finally:
        db.close()


def _update_parent_status(db, notification_id: str) -> None:
    """Roll per-channel delivery statuses up into the parent Notification's overall status."""
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        return

    statuses = [d.status for d in notification.deliveries]
    if any(s in (DeliveryStatus.pending, DeliveryStatus.queued) for s in statuses):
        notification.status = NotificationStatus.processing
    else:
        terminal = [s for s in statuses if s != DeliveryStatus.skipped]
        succeeded = any(s in (DeliveryStatus.sent, DeliveryStatus.delivered) for s in terminal)
        failed = any(s == DeliveryStatus.failed for s in terminal)
        if not terminal:
            # every channel was skipped (user opted out of all of them)
            notification.status = NotificationStatus.failed
        elif succeeded and failed:
            notification.status = NotificationStatus.partial
        elif succeeded:
            notification.status = NotificationStatus.sent
        else:
            notification.status = NotificationStatus.failed

    db.commit()


def run_worker() -> None:
    """Main worker loop: move due retries into the active queue, then drain by priority."""
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    queue = get_queue()
    logger.info("worker_started", extra={"queue_backend": settings.queue_backend})

    while _running:
        moved = queue.move_ready_retries()
        if moved:
            logger.debug("retries_moved_to_active_queue", extra={"count": moved})

        payload = queue.dequeue()
        if payload is None:
            time.sleep(settings.worker_poll_interval)
            continue

        try:
            process_one(payload)
        except Exception:  # noqa: BLE001 - a single bad job must never crash the worker loop
            logger.exception("worker_processing_error", extra={"payload": payload})

    logger.info("worker_stopped")


if __name__ == "__main__":
    run_worker()
