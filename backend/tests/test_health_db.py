"""GET /health/db, and /health staying independent of the database."""

import pytest
from fastapi.testclient import TestClient

import app.main as main_module

client = TestClient(main_module.app)


def test_health_does_not_touch_the_database(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("/health must not check the database")

    monkeypatch.setattr(main_module, "check_database_connection", fail_if_called)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.parametrize(
    ("reachable", "expected_status", "expected_body"),
    [
        (True, 200, {"status": "healthy", "database": "reachable"}),
        (False, 503, {"status": "unhealthy", "database": "unreachable"}),
    ],
)
def test_health_db_reports_database_state(monkeypatch, reachable, expected_status, expected_body):
    monkeypatch.setattr(main_module, "check_database_connection", lambda: reachable)

    response = client.get("/health/db")

    assert response.status_code == expected_status
    assert response.json() == expected_body
