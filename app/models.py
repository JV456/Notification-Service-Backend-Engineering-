import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Priority(str, enum.Enum):
    critical = "critical"
    high = "high"
    normal = "normal"
    low = "low"


class Channel(str, enum.Enum):
    email = "email"
    sms = "sms"
    push = "push"


class NotificationStatus(str, enum.Enum):
    pending = "pending"        # created, not yet picked up by any worker
    processing = "processing"  # at least one delivery in flight / queued
    sent = "sent"               # all (non-skipped) deliveries succeeded
    partial = "partial"        # some channels succeeded, some permanently failed
    failed = "failed"          # all channels permanently failed or all skipped


class DeliveryStatus(str, enum.Enum):
    pending = "pending"      # waiting for next attempt (incl. scheduled retries)
    queued = "queued"        # sitting in the active priority queue
    sent = "sent"             # provider accepted it
    delivered = "delivered"  # confirmed delivered (e.g. via provider webhook)
    failed = "failed"        # exhausted retries
    skipped = "skipped"      # user has opted out of this channel


class Notification(Base):
    """
    A single notification *request*. One request can fan out to multiple
    channels (email + sms + push), each tracked independently as a
    NotificationDelivery row.
    """

    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, nullable=False, index=True)

    # Used to deduplicate retried client requests. Unique per-user (not
    # globally) so two different users can reuse the same key.
    idempotency_key = Column(String, nullable=True)

    priority = Column(SAEnum(Priority), nullable=False, default=Priority.normal)
    template_id = Column(String, ForeignKey("templates.id"), nullable=True)

    subject = Column(String, nullable=True)
    body = Column(Text, nullable=True)
    variables = Column(JSON, nullable=False, default=dict)

    channels_requested = Column(JSON, nullable=False)  # list[str]
    status = Column(SAEnum(NotificationStatus), nullable=False, default=NotificationStatus.pending)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    deliveries = relationship(
        "NotificationDelivery", back_populates="notification", cascade="all, delete-orphan"
    )
    template = relationship("Template")

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_user_idempotency"),
        Index("ix_notifications_user_created", "user_id", "created_at"),
    )


class NotificationDelivery(Base):
    """Per-channel delivery attempt and status for a Notification."""

    __tablename__ = "notification_deliveries"

    id = Column(String, primary_key=True, default=gen_uuid)
    notification_id = Column(String, ForeignKey("notifications.id"), nullable=False, index=True)

    channel = Column(SAEnum(Channel), nullable=False)
    status = Column(SAEnum(DeliveryStatus), nullable=False, default=DeliveryStatus.pending)

    attempt_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    last_error = Column(Text, nullable=True)
    provider_message_id = Column(String, nullable=True)
    next_retry_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    notification = relationship("Notification", back_populates="deliveries")

    __table_args__ = (Index("ix_delivery_status_channel", "status", "channel"),)


class UserPreference(Base):
    """Per-user, per-channel opt-in/opt-out. Defaults to all channels enabled."""

    __tablename__ = "user_preferences"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, nullable=False, unique=True, index=True)
    email_enabled = Column(Boolean, nullable=False, default=True)
    sms_enabled = Column(Boolean, nullable=False, default=True)
    push_enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Template(Base):
    """A reusable message template with {{variable}} placeholders."""

    __tablename__ = "templates"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False, unique=True)
    channel = Column(SAEnum(Channel), nullable=True)  # null = usable on any channel
    subject_template = Column(String, nullable=True)
    body_template = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
