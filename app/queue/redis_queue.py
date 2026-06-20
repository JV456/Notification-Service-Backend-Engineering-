import json
from datetime import datetime
from typing import Any, Dict, Optional

import redis

from app.queue.base import PRIORITY_ORDER, QueueBackend


class RedisQueue(QueueBackend):
    """
    Durable queue backend for multi-process / multi-worker deployments.

    Layout:
      notif:queue:<priority>  -> Redis LIST (RPUSH/LPOP), one per priority level
      notif:delayed           -> Redis SORTED SET, score = unix timestamp to run at

    Using one list per priority (rather than a single list with sorting) keeps
    dequeue O(1) and avoids needing Redis-side sorting logic.
    """

    def __init__(self, redis_url: str, namespace: str = "notif") -> None:
        self.r = redis.from_url(redis_url, decode_responses=True)
        self.ns = namespace

    def _qkey(self, priority: str) -> str:
        return f"{self.ns}:queue:{priority}"

    def _delayed_key(self) -> str:
        return f"{self.ns}:delayed"

    def enqueue(self, priority: str, payload: Dict[str, Any]) -> None:
        self.r.rpush(self._qkey(priority), json.dumps(payload))

    def dequeue(self) -> Optional[Dict[str, Any]]:
        for p in PRIORITY_ORDER:
            raw = self.r.lpop(self._qkey(p))
            if raw:
                return json.loads(raw)
        return None

    def schedule_retry(self, payload: Dict[str, Any], run_at: datetime) -> None:
        self.r.zadd(self._delayed_key(), {json.dumps(payload): run_at.timestamp()})

    def move_ready_retries(self) -> int:
        now = datetime.utcnow().timestamp()
        ready = self.r.zrangebyscore(self._delayed_key(), 0, now)
        moved = 0
        for raw in ready:
            # ZREM first: guards against two workers both seeing it as "ready"
            # and double-enqueueing the same retry.
            if self.r.zrem(self._delayed_key(), raw):
                payload = json.loads(raw)
                self.enqueue(payload["priority"], payload)
                moved += 1
        return moved

    def queue_depth(self) -> Dict[str, int]:
        depths = {p: self.r.llen(self._qkey(p)) for p in PRIORITY_ORDER}
        depths["delayed"] = self.r.zcard(self._delayed_key())
        return depths
