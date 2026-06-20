import logging
import random
import uuid
from typing import Optional

from app.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger("notification_service.providers")


class MockProvider(BaseProvider):
    """
    Stands in for a real delivery gateway. Succeeds most of the time but
    randomly simulates a transient failure so the retry/backoff path in the
    worker has something real to exercise — exactly like a flaky upstream
    SendGrid/Twilio/FCM call would in production.
    """

    channel_name = "generic"
    failure_rate = 0.15  # 15% simulated transient failure rate

    def send(self, recipient: str, subject: Optional[str], body: str) -> ProviderResult:
        if random.random() < self.failure_rate:
            error = f"Simulated {self.channel_name} provider timeout"
            logger.warning("provider_send_failed", extra={"channel": self.channel_name, "recipient": recipient})
            return ProviderResult(success=False, error=error)

        message_id = f"{self.channel_name}-{uuid.uuid4().hex[:12]}"
        logger.info(
            "provider_send_succeeded",
            extra={"channel": self.channel_name, "recipient": recipient, "message_id": message_id},
        )
        return ProviderResult(success=True, message_id=message_id)


class MockEmailProvider(MockProvider):
    channel_name = "email"


class MockSMSProvider(MockProvider):
    channel_name = "sms"


class MockPushProvider(MockProvider):
    channel_name = "push"


PROVIDER_REGISTRY = {
    "email": MockEmailProvider(),
    "sms": MockSMSProvider(),
    "push": MockPushProvider(),
}
