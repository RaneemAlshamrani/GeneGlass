from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "GeneGlass API",
        "version": "0.1.0",
        "environment": "development",
        "database": "connected",
    }



def test_api_root_without_trailing_slash() -> None:
    response = client.get("/api")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["docs"] == "/docs"


def test_api_root_with_trailing_slash() -> None:
    response = client.get("/api/")

    assert response.status_code == 200


def test_cors_preflight_for_configured_frontend() -> None:
    response = client.options(
        "/api",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5500"
    assert response.headers["access-control-allow-credentials"] == "true"
