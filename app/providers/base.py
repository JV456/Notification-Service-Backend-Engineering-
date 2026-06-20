from abc import ABC, abstractmethod
from typing import Optional


class ProviderResult:
    def __init__(self, success: bool, message_id: Optional[str] = None, error: Optional[str] = None) -> None:
        self.success = success
        self.message_id = message_id
        self.error = error


class BaseProvider(ABC):
    """
    Interface every channel provider implements. A real implementation would
    wrap an SDK call (SendGrid, Twilio, FCM, ...); the assignment explicitly
    asks us to mock these and focus on the service design instead.
    """

    @abstractmethod
    def send(self, recipient: str, subject: Optional[str], body: str) -> ProviderResult:
        ...
