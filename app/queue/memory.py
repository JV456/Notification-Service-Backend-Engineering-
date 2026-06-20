import heapq
import itertools
import threading
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.queue.base import PRIORITY_ORDER, QueueBackend


class InMemoryQueue(QueueBackend):
    """
    In-process priority queue + delayed (retry) queue.

    Good for local development, demos, and tests where spinning up Redis is
    unnecessary friction. NOT durable: a process restart loses anything still
    queued. For anything resembling production reliability, run with
    QUEUE_BACKEND=redis instead (see RedisQueue).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queues: Dict[str, deque] = {p: deque() for p in PRIORITY_ORDER}
        self._delayed: List[Tuple[float, int, Dict[str, Any]]] = []  # heap
        self._counter = itertools.count()

    def enqueue(self, priority: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._queues[priority].append(payload)

    def dequeue(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            for p in PRIORITY_ORDER:
                if self._queues[p]:
                    return self._queues[p].popleft()
        return None

    def schedule_retry(self, payload: Dict[str, Any], run_at: datetime) -> None:
        with self._lock:
            heapq.heappush(self._delayed, (run_at.timestamp(), next(self._counter), payload))

    def move_ready_retries(self) -> int:
        moved = 0
        now = datetime.utcnow().timestamp()
        with self._lock:
            while self._delayed and self._delayed[0][0] <= now:
                _, _, payload = heapq.heappop(self._delayed)
                self._queues[payload["priority"]].append(payload)
                moved += 1
        return moved

    def queue_depth(self) -> Dict[str, int]:
        with self._lock:
            depths = {p: len(q) for p, q in self._queues.items()}
            depths["delayed"] = len(self._delayed)
            return depths
