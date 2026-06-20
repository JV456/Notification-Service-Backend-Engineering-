def test_get_default_preferences(client):
    resp = client.get("/users/new-user/preferences")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email_enabled"] is True
    assert data["sms_enabled"] is True
    assert data["push_enabled"] is True


def test_set_and_get_preferences(client):
    client.post("/users/pref-user/preferences", json={"email_enabled": False, "push_enabled": False})
    resp = client.get("/users/pref-user/preferences")
    data = resp.json()
    assert data["email_enabled"] is False
    assert data["sms_enabled"] is True
    assert data["push_enabled"] is False


def test_partial_preference_update_does_not_reset_other_fields(client):
    client.post("/users/pref-user2/preferences", json={"email_enabled": False})
    client.post("/users/pref-user2/preferences", json={"sms_enabled": False})
    resp = client.get("/users/pref-user2/preferences")
    data = resp.json()
    assert data["email_enabled"] is False
    assert data["sms_enabled"] is False
    assert data["push_enabled"] is True
