from datetime import datetime, timedelta

from app.queue.memory import InMemoryQueue


def test_priority_ordering_drains_critical_first():
    q = InMemoryQueue()
    q.enqueue("low", {"id": "low1", "priority": "low"})
    q.enqueue("critical", {"id": "crit1", "priority": "critical"})
    q.enqueue("normal", {"id": "norm1", "priority": "normal"})
    q.enqueue("high", {"id": "high1", "priority": "high"})

    assert q.dequeue()["id"] == "crit1"
    assert q.dequeue()["id"] == "high1"
    assert q.dequeue()["id"] == "norm1"
    assert q.dequeue()["id"] == "low1"
    assert q.dequeue() is None


def test_delayed_retry_not_ready_until_due():
    q = InMemoryQueue()
    q.schedule_retry({"id": "r1", "priority": "high"}, datetime.utcnow() + timedelta(seconds=10))
    assert q.move_ready_retries() == 0
    assert q.dequeue() is None


def test_delayed_retry_ready_when_due():
    q = InMemoryQueue()
    q.schedule_retry({"id": "r1", "priority": "high"}, datetime.utcnow() - timedelta(seconds=1))
    assert q.move_ready_retries() == 1
    assert q.dequeue()["id"] == "r1"


def test_queue_depth_reports_each_priority():
    q = InMemoryQueue()
    q.enqueue("critical", {"id": "a", "priority": "critical"})
    q.enqueue("critical", {"id": "b", "priority": "critical"})
    q.enqueue("low", {"id": "c", "priority": "low"})
    depth = q.queue_depth()
    assert depth["critical"] == 2
    assert depth["low"] == 1
    assert depth["normal"] == 0
