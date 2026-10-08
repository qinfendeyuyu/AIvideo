from fastapi.testclient import TestClient

from app.main import app


def test_legacy_studio_entrypoint_and_routes():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        paths = client.get("/openapi.json").json()["paths"]
        assert "/api/v1/episode" in paths
        assert "/api/v1/runs/{run_id}/file" in paths
