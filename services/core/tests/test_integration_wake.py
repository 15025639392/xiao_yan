from fastapi.testclient import TestClient

from app.main import app


def test_wake_endpoint_returns_thought():
    client = TestClient(app)
    response = client.post("/lifecycle/wake")
    body = response.json()

    assert response.status_code == 200
    assert body["mode"] == "awake"
    assert body["current_thought"]
