import os

from fastapi.testclient import TestClient


def test_health_and_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("DISPATCHARR_API_KEY", "test-dispatcharr-key")
    monkeypatch.setenv("CONTROL_PLANE_API_TOKEN", "test-control-token")
    monkeypatch.setenv("CONTROL_PLANE_DB", str(tmp_path / "cp.sqlite3"))

    from controlplane.app.main import app

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/dashboard").status_code == 401
        assert client.get("/api/settings/public").status_code == 401
        response = client.get(
            "/api/settings/public",
            headers={"Authorization": "Bearer test-control-token"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["secrets"] == "not exposed to browser"
        assert "test-dispatcharr-key" not in response.text


def test_static_frontend_is_served(tmp_path, monkeypatch):
    monkeypatch.setenv("DISPATCHARR_API_KEY", "test-dispatcharr-key")
    monkeypatch.setenv("CONTROL_PLANE_API_TOKEN", "test-control-token")
    monkeypatch.setenv("CONTROL_PLANE_DB", str(tmp_path / "cp.sqlite3"))

    from controlplane.app.main import app

    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "VOD operations console" in response.text
