import logging
from typing import List

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Channel,
    DeliveryStatus,
    Notification,
    NotificationDelivery,
    NotificationStatus,
    Template,
    UserPreference,
)
from app.queue.factory import get_queue
from app.services.template_service import render_template

logger = logging.getLogger("notification_service.service")


class IdempotentReplay(Exception):
    """
    Raised instead of creating a duplicate row when a request reuses an
    idempotency_key already seen for this user. The caller (API layer)
    catches this and returns the original notification instead of an error.
    """

    def __init__(self, notification: Notification) -> None:
        self.notification = notification


def get_user_preference(db: Session, user_id: str) -> UserPreference:
    """Fetch a user's channel preferences, creating an all-enabled default row if none exists yet."""
    pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    if not pref:
        pref = UserPreference(user_id=user_id)
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return pref


def _enabled_channels(pref: UserPreference, requested: List[str]) -> List[str]:
    mapping = {
        "email": pref.email_enabled,
        "sms": pref.sms_enabled,
        "push": pref.push_enabled,
    }
    return [c for c in requested if mapping.get(c, True)]


def create_notification(db: Session, data) -> Notification:
    """
    Validate, persist, and enqueue a notification request.

    `data` is a NotificationCreate schema (or anything with the same
    attributes — see send_batch, which builds one per recipient).
    """
    # --- Idempotency check: same user + same key => return the original ---
    if data.idempotency_key:
        existing = (
            db.query(Notification)
            .filter(
                Notification.user_id == data.user_id,
                Notification.idempotency_key == data.idempotency_key,
            )
            .first()
        )
        if existing:
            logger.info(
                "idempotent_replay",
                extra={"user_id": data.user_id, "idempotency_key": data.idempotency_key},
            )
            raise IdempotentReplay(existing)

    # --- Resolve subject/body, either from a template or given directly ---
    if data.template_id:
        template = db.query(Template).filter(Template.id == data.template_id).first()
        if template is None:
            raise ValueError(f"template_id '{data.template_id}' not found")
        subject = render_template(template.subject_template, data.variables)
        body = render_template(template.body_template, data.variables)
    else:
        subject = render_template(data.subject, data.variables)
        body = render_template(data.body, data.variables)

    if not body:
        raise ValueError("Either 'body' or a valid 'template_id' producing a body is required")

    # --- Filter requested channels through the user's preferences ---
    pref = get_user_preference(db, data.user_id)
    requested = [c.value if hasattr(c, "value") else c for c in data.channels]
    enabled = _enabled_channels(pref, requested)

    notification = Notification(
        user_id=data.user_id,
        idempotency_key=data.idempotency_key,
        priority=data.priority,
        template_id=data.template_id,
        subject=subject,
        body=body,
        variables=data.variables,
        channels_requested=requested,
        status=NotificationStatus.pending,
    )
    db.add(notification)
    try:
        db.flush()  # assigns notification.id, surfaces unique-constraint races early
    except IntegrityError:
        # Two concurrent requests with the same idempotency key raced us —
        # the loser here just returns whatever the winner created.
        db.rollback()
        existing = (
            db.query(Notification)
            .filter(
                Notification.user_id == data.user_id,
                Notification.idempotency_key == data.idempotency_key,
            )
            .first()
        )
        if existing:
            raise IdempotentReplay(existing)
        raise

    queue = get_queue()
    priority_value = notification.priority.value if hasattr(notification.priority, "value") else notification.priority
    any_enqueued = False

    for ch in requested:
        if ch in enabled:
            delivery = NotificationDelivery(
                notification_id=notification.id,
                channel=Channel(ch),
                status=DeliveryStatus.queued,
                max_retries=settings.max_retries,
            )
            db.add(delivery)
            db.flush()  # need delivery.id before we can put it on the queue
            queue.enqueue(
                priority_value,
                {
                    "notification_id": notification.id,
                    "delivery_id": delivery.id,
                    "channel": ch,
                    "priority": priority_value,
                    "user_id": data.user_id,
                    "subject": subject,
                    "body": body,
                },
            )
            any_enqueued = True
        else:
            # User opted out — recorded as "skipped", not "failed". This still
            # shows up in delivery history/analytics but isn't treated as an error.
            db.add(
                NotificationDelivery(
                    notification_id=notification.id,
                    channel=Channel(ch),
                    status=DeliveryStatus.skipped,
                    last_error="User has opted out of this channel",
                )
            )

    notification.status = NotificationStatus.processing if any_enqueued else NotificationStatus.failed
    db.commit()
    db.refresh(notification)

    logger.info(
        "notification_created",
        extra={"notification_id": notification.id, "user_id": data.user_id, "channels": requested},
    )
    return notification
