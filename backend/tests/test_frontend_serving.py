"""Production mode: the API also serves the built React app from one origin."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import install_error_handlers
from app.main import mount_frontend


def _app(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")
    (dist / "assets" / "app-123.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("outside dist", encoding="utf-8")
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/api/v1/ping")
    def ping():
        return {"ok": True}

    assert mount_frontend(app, dist)
    return TestClient(app)


def test_client_side_routes_get_the_app_and_api_routes_still_win(tmp_path):
    client = _app(tmp_path)
    for path in ("/", "/dashboard", "/interview/setup", "/plan/123"):
        response = client.get(path)
        assert response.status_code == 200 and "id=root" in response.text
        assert response.headers["cache-control"] == "no-cache"
    assert client.get("/assets/app-123.js").text == "console.log(1)"
    assert client.get("/favicon.svg").text == "<svg/>"
    assert client.get("/api/v1/ping").json() == {"ok": True}


def test_unknown_api_paths_are_json_404_not_the_app(tmp_path):
    client = _app(tmp_path)
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404 and response.json()["error"]["code"] == "NOT_FOUND"


def test_files_outside_dist_are_never_served(tmp_path):
    client = _app(tmp_path)
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/..%2fsecret.txt"):
        assert "outside dist" not in client.get(path).text


def test_nothing_is_mounted_without_a_build(tmp_path):
    assert mount_frontend(FastAPI(), tmp_path / "missing") is False
