from fastapi.testclient import TestClient

from app.main import app

# TestClient calls the app directly in-process — no server, no network, no port.
client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_reports_app_name():
    response = client.get("/health")

    assert response.json()["app"] == "Jarvis"