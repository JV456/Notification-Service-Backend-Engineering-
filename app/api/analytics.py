from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import NotificationDelivery

router = APIRouter(tags=["analytics"])


@router.get("/analytics/stats")
def get_stats(
    db: Session = Depends(get_db),
    since: Optional[datetime] = Query(None, description="ISO timestamp; only count deliveries created after this"),
):
    """Bonus: sent/failed/etc. counts broken down by channel and status."""
    query = db.query(
        NotificationDelivery.channel,
        NotificationDelivery.status,
        func.count(NotificationDelivery.id),
    )
    if since:
        query = query.filter(NotificationDelivery.created_at >= since)

    rows = query.group_by(NotificationDelivery.channel, NotificationDelivery.status).all()

    stats: dict = {}
    for channel, delivery_status, count in rows:
        channel_key = channel.value if hasattr(channel, "value") else channel
        status_key = delivery_status.value if hasattr(delivery_status, "value") else delivery_status
        stats.setdefault(channel_key, {})[status_key] = count

    return {"by_channel": stats}
