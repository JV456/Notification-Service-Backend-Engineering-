from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models import Channel, DeliveryStatus, NotificationStatus, Priority


class NotificationCreate(BaseModel):
    user_id: str
    channels: List[Channel] = Field(..., min_length=1, description="Channels to attempt for this notification")
    priority: Priority = Priority.normal
    template_id: Optional[str] = Field(None, description="If set, subject/body are rendered from this template")
    subject: Optional[str] = None
    body: Optional[str] = Field(None, description="Required if template_id is not provided")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Values substituted into {{placeholders}}")
    idempotency_key: Optional[str] = Field(
        None, description="Client-supplied key; resending the same key for the same user returns the original result"
    )


class DeliveryOut(BaseModel):
    id: str
    channel: Channel
    status: DeliveryStatus
    attempt_count: int
    last_error: Optional[str] = None
    provider_message_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationOut(BaseModel):
    id: str
    user_id: str
    priority: Priority
    status: NotificationStatus
    channels_requested: List[str]
    subject: Optional[str] = None
    body: Optional[str] = None
    variables: Dict[str, Any]
    idempotency_key: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deliveries: List[DeliveryOut] = []

    class Config:
        from_attributes = True


class NotificationListOut(BaseModel):
    total: int
    items: List[NotificationOut]


class PreferenceIn(BaseModel):
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None


class PreferenceOut(BaseModel):
    user_id: str
    email_enabled: bool
    sms_enabled: bool
    push_enabled: bool

    class Config:
        from_attributes = True


class BatchNotificationCreate(BaseModel):
    user_ids: List[str] = Field(..., min_length=1)
    channels: List[Channel] = Field(..., min_length=1)
    priority: Priority = Priority.normal
    template_id: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    variables: Dict[str, Any] = Field(default_factory=dict)


class BatchResultItem(BaseModel):
    user_id: str
    notification_id: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None


class TemplateCreate(BaseModel):
    name: str
    channel: Optional[Channel] = None
    subject_template: Optional[str] = None
    body_template: str


class TemplateOut(BaseModel):
    id: str
    name: str
    channel: Optional[Channel] = None
    subject_template: Optional[str] = None
    body_template: str

    class Config:
        from_attributes = True
