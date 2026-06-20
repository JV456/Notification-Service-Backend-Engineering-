from unittest.mock import patch

from app.providers.base import ProviderResult
from app.queue.factory import get_queue
from app.workers.notification_worker import process_one


def test_end_to_end_send_then_worker_delivers(client):
    """
    This is the full real-world flow in one test:
      1. Client calls POST /notifications -> API validates, persists, enqueues.
      2. (Normally a separate worker process) we pop the job off the queue
         ourselves and call process_one() directly, with the provider mocked
         to a deterministic success so the test isn't flaky.
      3. GET /notifications/:id shows the updated, worker-written status.
    """
    with patch(
        "app.workers.notification_worker.PROVIDER_REGISTRY",
        {"email": type("P", (), {"send": staticmethod(lambda recipient, subject, body: ProviderResult(success=True, message_id="m-1"))})()},
    ):
        create_resp = client.post(
            "/notifications", json={"user_id": "e2e-user", "channels": ["email"], "body": "End to end!"}
        )
        assert create_resp.status_code == 201
        notification_id = create_resp.json()["id"]

        # In production this is what the worker loop does in app/workers/notification_worker.py
        queue = get_queue()
        job = queue.dequeue()
        assert job is not None
        assert job["notification_id"] == notification_id
        process_one(job)

    final = client.get(f"/notifications/{notification_id}")
    data = final.json()
    assert data["status"] == "sent"
    assert data["deliveries"][0]["status"] == "sent"
    assert data["deliveries"][0]["provider_message_id"] == "m-1"
