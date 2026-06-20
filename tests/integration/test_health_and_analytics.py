def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_analytics_stats_reflects_sent_notifications(client):
    client.post("/notifications", json={"user_id": "analytics-user", "channels": ["email"], "body": "Hi"})
    resp = client.get("/analytics/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "by_channel" in data
