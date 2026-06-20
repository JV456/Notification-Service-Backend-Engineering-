from app.database import SessionLocal
from app.models import Channel, DeliveryStatus, Notification, NotificationDelivery, NotificationStatus, Priority
from app.providers.base import ProviderResult
from app.providers import mock_providers
from app.queue.factory import get_queue
from app.workers.notification_worker import process_one


def _make_notification_with_delivery(channel="email"):
    db = SessionLocal()
    notification = Notification(
        user_id="worker-test-user",
        priority=Priority.normal,
        body="hello",
        variables={},
        channels_requested=[channel],
        status=NotificationStatus.processing,
    )
    db.add(notification)
    db.flush()
    delivery = NotificationDelivery(
        notification_id=notification.id,
        channel=Channel(channel),
        status=DeliveryStatus.queued,
        max_retries=3,
    )
    db.add(delivery)
    db.commit()
    notification_id, delivery_id = notification.id, delivery.id
    db.close()
    return notification_id, delivery_id


def test_process_one_marks_sent_on_provider_success(monkeypatch):
    notification_id, delivery_id = _make_notification_with_delivery("email")

    monkeypatch.setattr(
        mock_providers.PROVIDER_REGISTRY["email"], "send",
        lambda recipient, subject, body: ProviderResult(success=True, message_id="msg-1"),
    )

    process_one({
        "notification_id": notification_id, "delivery_id": delivery_id, "channel": "email",
        "priority": "normal", "user_id": "worker-test-user", "subject": None, "body": "hello",
    })

    db = SessionLocal()
    delivery = db.query(NotificationDelivery).filter(NotificationDelivery.id == delivery_id).first()
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    assert delivery.status == DeliveryStatus.sent
    assert delivery.attempt_count == 1
    assert notification.status == NotificationStatus.sent
    db.close()


def test_process_one_schedules_retry_on_failure_under_max(monkeypatch):
    notification_id, delivery_id = _make_notification_with_delivery("sms")

    monkeypatch.setattr(
        mock_providers.PROVIDER_REGISTRY["sms"], "send",
        lambda recipient, subject, body: ProviderResult(success=False, error="timeout"),
    )

    payload = {
        "notification_id": notification_id, "delivery_id": delivery_id, "channel": "sms",
        "priority": "normal", "user_id": "worker-test-user", "subject": None, "body": "hello",
    }
    process_one(payload)

    db = SessionLocal()
    delivery = db.query(NotificationDelivery).filter(NotificationDelivery.id == delivery_id).first()
    assert delivery.status == DeliveryStatus.pending
    assert delivery.attempt_count == 1
    assert delivery.last_error == "timeout"
    db.close()

    # A retry should now be sitting in the delayed queue, not the active one.
    queue = get_queue()
    assert queue.dequeue() is None


def test_process_one_marks_failed_after_exhausting_retries(monkeypatch):
    notification_id, delivery_id = _make_notification_with_delivery("push")

    monkeypatch.setattr(
        mock_providers.PROVIDER_REGISTRY["push"], "send",
        lambda recipient, subject, body: ProviderResult(success=False, error="boom"),
    )

    payload = {
        "notification_id": notification_id, "delivery_id": delivery_id, "channel": "push",
        "priority": "normal", "user_id": "worker-test-user", "subject": None, "body": "hello",
    }
    # max_retries=3 => attempts 1,2,3 retry; attempt 4 is permanent failure
    for _ in range(4):
        process_one(payload)

    db = SessionLocal()
    delivery = db.query(NotificationDelivery).filter(NotificationDelivery.id == delivery_id).first()
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    assert delivery.status == DeliveryStatus.failed
    assert delivery.attempt_count == 4
    assert notification.status == NotificationStatus.failed
    db.close()
