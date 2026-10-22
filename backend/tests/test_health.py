from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200_and_expected_body():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "ai-interview-coach-backend",
    }


def test_openapi_docs_are_available():
    response = client.get("/docs")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
