def test_send_notification_requires_body_or_template(client):
    resp = client.post("/notifications", json={"user_id": "u1", "channels": ["email"]})
    assert resp.status_code == 422


def test_send_notification_success(client):
    resp = client.post(
        "/notifications",
        json={"user_id": "u1", "channels": ["email", "sms"], "body": "Hello there", "priority": "high"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] in ("processing", "sent")
    assert len(data["deliveries"]) == 2
    assert {d["channel"] for d in data["deliveries"]} == {"email", "sms"}


def test_send_notification_invalid_channel_rejected(client):
    resp = client.post("/notifications", json={"user_id": "u1", "channels": ["carrier_pigeon"], "body": "hi"})
    assert resp.status_code == 422


def test_get_notification_status(client):
    create = client.post("/notifications", json={"user_id": "u2", "channels": ["push"], "body": "Hi"})
    notification_id = create.json()["id"]
    resp = client.get(f"/notifications/{notification_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == notification_id


def test_get_notification_not_found(client):
    resp = client.get("/notifications/does-not-exist")
    assert resp.status_code == 404


def test_idempotency_key_prevents_duplicate(client):
    body = {"user_id": "u3", "channels": ["email"], "body": "Hi", "idempotency_key": "abc-123"}
    first = client.post("/notifications", json=body)
    second = client.post("/notifications", json=body)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


def test_different_idempotency_keys_create_separate_notifications(client):
    base = {"user_id": "u3b", "channels": ["email"], "body": "Hi"}
    first = client.post("/notifications", json={**base, "idempotency_key": "key-1"})
    second = client.post("/notifications", json={**base, "idempotency_key": "key-2"})
    assert first.json()["id"] != second.json()["id"]


def test_user_notification_history(client):
    client.post("/notifications", json={"user_id": "u4", "channels": ["email"], "body": "Hi 1"})
    client.post("/notifications", json={"user_id": "u4", "channels": ["sms"], "body": "Hi 2"})
    resp = client.get("/users/u4/notifications")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_user_preference_filters_channels(client):
    client.post("/users/u5/preferences", json={"email_enabled": False})
    resp = client.post("/notifications", json={"user_id": "u5", "channels": ["email", "sms"], "body": "Hi"})
    data = resp.json()
    email_delivery = next(d for d in data["deliveries"] if d["channel"] == "email")
    sms_delivery = next(d for d in data["deliveries"] if d["channel"] == "sms")
    assert email_delivery["status"] == "skipped"
    assert sms_delivery["status"] in ("queued", "sent")


def test_rate_limit_enforced(client):
    from app.services import rate_limiter as rl

    rl.reset_rate_limiter_for_tests(rl.InMemoryRateLimiter(limit=2, window_seconds=3600))
    user = "rate-limited-user"
    r1 = client.post("/notifications", json={"user_id": user, "channels": ["email"], "body": "1"})
    r2 = client.post("/notifications", json={"user_id": user, "channels": ["email"], "body": "2"})
    r3 = client.post("/notifications", json={"user_id": user, "channels": ["email"], "body": "3"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r3.status_code == 429


def test_template_rendering_end_to_end(client):
    tmpl = client.post(
        "/templates",
        json={"name": "order_shipped", "body_template": "Hi {{name}}, order {{order_id}} shipped!"},
    )
    assert tmpl.status_code == 201
    template_id = tmpl.json()["id"]

    resp = client.post(
        "/notifications",
        json={
            "user_id": "u6",
            "channels": ["email"],
            "template_id": template_id,
            "variables": {"name": "Asha", "order_id": "999"},
        },
    )
    assert resp.status_code == 201
    assert resp.json()["body"] == "Hi Asha, order 999 shipped!"


def test_batch_notifications(client):
    resp = client.post(
        "/notifications/batch",
        json={"user_ids": ["b1", "b2", "b3"], "channels": ["email"], "body": "Batch hello"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data) == 3
    assert all(item["notification_id"] for item in data)
