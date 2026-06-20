import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Notification
from app.schemas import (
    BatchNotificationCreate,
    BatchResultItem,
    NotificationCreate,
    NotificationListOut,
    NotificationOut,
)
from app.services.notification_service import IdempotentReplay, create_notification
from app.services.rate_limiter import get_rate_limiter

router = APIRouter(tags=["notifications"])
logger = logging.getLogger("notification_service.api")


@router.post("/notifications", response_model=NotificationOut, status_code=status.HTTP_201_CREATED)
def send_notification(payload: NotificationCreate, db: Session = Depends(get_db)):
    """Send a new notification. Respects user preferences, priority, and idempotency_key."""
    limiter = get_rate_limiter()
    if not limiter.is_allowed(payload.user_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded: max notifications per hour reached for this user",
        )

    if not payload.template_id and not payload.body:
        raise HTTPException(status_code=422, detail="Either 'template_id' or 'body' must be provided")

    try:
        notification = create_notification(db, payload)
    except IdempotentReplay as replay:
        # Same status code as a fresh send: the client asked for this exact
        # operation and gets back the result, whether it's new or a replay.
        return replay.notification
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return notification


@router.post("/notifications/batch", response_model=list[BatchResultItem], status_code=status.HTTP_201_CREATED)
def send_batch(payload: BatchNotificationCreate, db: Session = Depends(get_db)):
    """Send the same message to many users in one call (bonus: Batch API)."""
    limiter = get_rate_limiter()
    results = []

    for user_id in payload.user_ids:
        if not limiter.is_allowed(user_id):
            results.append(BatchResultItem(user_id=user_id, error="rate_limited"))
            continue

        single = NotificationCreate(
            user_id=user_id,
            channels=payload.channels,
            priority=payload.priority,
            template_id=payload.template_id,
            subject=payload.subject,
            body=payload.body,
            variables=payload.variables,
        )
        try:
            notification = create_notification(db, single)
            results.append(
                BatchResultItem(user_id=user_id, notification_id=notification.id, status=notification.status.value)
            )
        except IdempotentReplay as replay:
            results.append(
                BatchResultItem(user_id=user_id, notification_id=replay.notification.id, status="duplicate")
            )
        except ValueError as e:
            results.append(BatchResultItem(user_id=user_id, error=str(e)))

    return results


@router.get("/notifications/{notification_id}", response_model=NotificationOut)
def get_notification(notification_id: str, db: Session = Depends(get_db)):
    """Get the current status of a notification and each of its per-channel deliveries."""
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@router.get("/users/{user_id}/notifications", response_model=NotificationListOut)
def list_user_notifications(
    user_id: str,
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Paginated notification history for a user, most recent first."""
    query = (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
    )
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return {"total": total, "items": items}
