from typing import Optional

from app.config import settings
from app.queue.base import QueueBackend
from app.queue.memory import InMemoryQueue

_queue_instance: Optional[QueueBackend] = None


def get_queue() -> QueueBackend:
    global _queue_instance
    if _queue_instance is not None:
        return _queue_instance

    if settings.queue_backend == "redis":
        from app.queue.redis_queue import RedisQueue  # imported lazily: redis is optional

        _queue_instance = RedisQueue(settings.redis_url)
    else:
        _queue_instance = InMemoryQueue()
    return _queue_instance


def reset_queue_for_tests() -> None:
    """Test-only helper to force a fresh queue instance between test cases."""
    global _queue_instance
    _queue_instance = None
