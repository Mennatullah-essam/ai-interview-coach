"""Registration, login, current user, refresh, logout and token validation."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import _jwt_secret, hash_password, hash_refresh_token, verify_password
from app.models import RefreshToken, User
from tests.conftest import CLIENT_HEADER, PASSWORD, auth_headers, present_refresh_cookie, register


def test_register_creates_account_with_hashed_password(client, api_session_factory):
    response = register(client, "  New.User@Example.COM ", "  New User ")

    body = response.json()
    assert body["user"]["email"] == "new.user@example.com"  # normalised
    assert body["user"]["name"] == "New User"  # trimmed
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == get_settings().access_token_minutes * 60
    assert "password" not in response.text
    with api_session_factory() as db:
        user = db.scalar(select(User).where(User.email == "new.user@example.com"))
        assert user.password_hash.startswith("scrypt$")
        assert PASSWORD not in user.password_hash
        assert verify_password(PASSWORD, user.password_hash)


def test_register_sets_httponly_refresh_cookie(client):
    response = register(client, "cookie@example.com")

    header = response.headers["set-cookie"].lower()
    assert "aic_refresh=" in header
    assert "httponly" in header
    assert "samesite=strict" in header
    assert "path=/api/v1/auth" in header
    assert "secure" not in header  # plain HTTP is allowed outside production


@pytest.mark.parametrize("email", ["dup@example.com", "DUP@example.com", " Dup@Example.com "])
def test_duplicate_email_rejected_case_insensitively(client, email):
    register(client, "dup@example.com")

    response = client.post("/api/v1/auth/register", json={"name": "Again", "email": email, "password": PASSWORD})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"name": "A", "email": "a@example.com", "password": PASSWORD}, "name"),
        ({"name": "Valid Name", "email": "not-an-email", "password": PASSWORD}, "email"),
        ({"name": "Valid Name", "email": "a@example.com", "password": "short"}, "password"),
        ({"email": "a@example.com", "password": PASSWORD}, "name"),
        ({"name": "Valid Name", "email": "a@example.com", "password": PASSWORD, "is_admin": True}, "is_admin"),
    ],
)
def test_register_validation_errors_use_error_envelope(client, payload, field):
    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"][0]["field"] == field
    assert error["request_id"].startswith("req_")
    assert response.headers["X-Request-ID"] == error["request_id"]


def test_login_success_and_me(client):
    register(client, "login@example.com", "Login Person")

    response = client.post("/api/v1/auth/login", json={"email": "LOGIN@example.com", "password": PASSWORD})

    assert response.status_code == 200
    me = client.get("/api/v1/users/me", headers=auth_headers(response))
    assert me.status_code == 200
    assert me.json()["email"] == "login@example.com"
    assert me.json()["name"] == "Login Person"


@pytest.mark.parametrize(
    "credentials",
    [
        {"email": "known@example.com", "password": "wrong-password"},
        {"email": "unknown@example.com", "password": PASSWORD},
    ],
)
def test_invalid_login_has_identical_response(client, credentials):
    register(client, "known@example.com")

    response = client.post("/api/v1/auth/login", json=credentials)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert response.json()["error"]["message"] == "Incorrect email or password."


def test_account_without_password_cannot_log_in(client, api_session_factory):
    with api_session_factory() as db:  # e.g. a row created before Milestone 3
        db.add(User(full_name="Legacy", email="legacy@example.com"))
        db.commit()

    response = client.post("/api/v1/auth/login", json={"email": "legacy@example.com", "password": PASSWORD})

    assert response.status_code == 401


def test_inactive_account_cannot_log_in(client, api_session_factory):
    register(client, "inactive@example.com")
    with api_session_factory() as db:
        db.scalar(select(User).where(User.email == "inactive@example.com")).is_active = False
        db.commit()

    response = client.post("/api/v1/auth/login", json={"email": "inactive@example.com", "password": PASSWORD})

    assert response.status_code == 401


@pytest.mark.parametrize(
    "path",
    ["/api/v1/users/me", "/api/v1/cvs", "/api/v1/interviews", "/api/v1/performance/skills", "/api/v1/performance/summary"],
)
def test_protected_endpoints_require_authentication(client, path):
    response = client.get(path)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def _token(**overrides):
    now = datetime.now(UTC)
    payload = {"sub": "00000000-0000-0000-0000-000000000000", "typ": "access", "iss": "ai-interview-coach",
               "iat": now, "exp": now + timedelta(minutes=5)}
    payload.update(overrides)
    return payload


def test_expired_token_returns_token_expired(client):
    user = register(client, "expiry@example.com").json()["user"]
    past = datetime.now(UTC) - timedelta(hours=1)
    token = jwt.encode(_token(sub=user["id"], iat=past, exp=past + timedelta(minutes=1)), _jwt_secret(), algorithm="HS256")

    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"


@pytest.mark.parametrize(
    "token_factory",
    [
        lambda uid: jwt.encode(_token(sub=uid), "a-different-secret-with-enough-length!!", algorithm="HS256"),
        lambda uid: jwt.encode(_token(sub=uid), None, algorithm="none"),
        lambda uid: jwt.encode(_token(sub=uid, typ="refresh"), _jwt_secret(), algorithm="HS256"),
        lambda uid: jwt.encode(_token(sub=uid, iss="someone-else"), _jwt_secret(), algorithm="HS256"),
        lambda uid: "not-a-jwt",
    ],
    ids=["wrong-signature", "alg-none", "wrong-type", "wrong-issuer", "garbage"],
)
def test_invalid_tokens_rejected(client, token_factory):
    user = register(client, "forger@example.com").json()["user"]

    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token_factory(user['id'])}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_refresh_restores_session_and_rotates_cookie(client):
    register(client, "refresh@example.com")
    first_cookie = client.cookies.get("aic_refresh")

    response = client.post("/api/v1/auth/refresh", headers=CLIENT_HEADER)

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "refresh@example.com"
    assert client.get("/api/v1/users/me", headers=auth_headers(response)).status_code == 200
    assert client.cookies.get("aic_refresh") not in (None, first_cookie)


def test_reusing_a_rotated_refresh_token_revokes_all_sessions(client, api_session_factory):
    register(client, "reuse@example.com")
    stolen = client.cookies.get("aic_refresh")
    assert client.post("/api/v1/auth/refresh", headers=CLIENT_HEADER).status_code == 200

    with api_session_factory() as db:
        old = db.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(stolen)
            )
        )
        assert old is not None
        assert old.revoked_at is not None
        old.revoked_at = datetime.now(UTC) - timedelta(minutes=5)
        db.commit()
    present_refresh_cookie(client, stolen)  # the old token must be the only cookie sent
    reused = client.post("/api/v1/auth/refresh", headers=CLIENT_HEADER)

    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "TOKEN_INVALID"
    with api_session_factory() as db:
        tokens = list(db.scalars(select(RefreshToken)))
        assert len(tokens) == 2  # the original and its rotated successor
        assert all(t.revoked_at is not None for t in tokens)


def test_simultaneous_refresh_from_two_tabs_is_not_treated_as_theft(client, api_session_factory):
    register(client, "tabs@example.com")
    shared = client.cookies.get("aic_refresh")
    assert client.post("/api/v1/auth/refresh", headers=CLIENT_HEADER).status_code == 200  # tab 1

    present_refresh_cookie(client, shared)  # tab 2 sends the same, just-rotated cookie
    second = client.post("/api/v1/auth/refresh", headers=CLIENT_HEADER)

    assert second.status_code == 200
    assert second.json()["user"]["email"] == "tabs@example.com"
    with api_session_factory() as db:  # a benign race must leave a live session behind
        assert any(t.revoked_at is None for t in db.scalars(select(RefreshToken)))


def test_refresh_requires_client_header(client):
    register(client, "csrf@example.com")

    response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_refresh_without_cookie_is_rejected(client):
    response = client.post("/api/v1/auth/refresh", headers=CLIENT_HEADER)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_INVALID"


def test_logout_invalidates_the_session(client, api_session_factory):
    register(client, "logout@example.com")

    response = client.post("/api/v1/auth/logout", headers=CLIENT_HEADER)

    assert response.status_code == 204
    assert 'aic_refresh=""' in response.headers["set-cookie"] or "max-age=0" in response.headers["set-cookie"].lower()
    after = client.post("/api/v1/auth/refresh", headers=CLIENT_HEADER)
    assert after.status_code == 401
    with api_session_factory() as db:
        assert db.scalar(select(RefreshToken)).revoked_at is not None


def test_login_is_rate_limited(client, monkeypatch):
    monkeypatch.setenv("AUTH_RATE_LIMIT_PER_MINUTE", "3")
    get_settings.cache_clear()
    for _ in range(3):
        assert client.post("/api/v1/auth/login", json={"email": "x@example.com", "password": "nope-nope"}).status_code == 401

    response = client.post("/api/v1/auth/login", json={"email": "x@example.com", "password": "nope-nope"})

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert int(response.headers["Retry-After"]) >= 1


def test_update_profile_and_email_conflict(client, user_a, user_b):
    ok = client.patch("/api/v1/users/me", headers=user_a, json={"name": "Alice Changed", "email": "Alice.New@Example.com"})
    assert ok.status_code == 200
    assert ok.json() | {"id": None, "created_at": None} == {
        "id": None, "created_at": None, "name": "Alice Changed", "email": "alice.new@example.com"
    }

    conflict = client.patch("/api/v1/users/me", headers=user_a, json={"email": "bob@example.com"})
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "EMAIL_ALREADY_IN_USE"

    empty = client.patch("/api/v1/users/me", headers=user_a, json={})
    assert empty.status_code == 422


def test_password_hash_format_and_verification():
    stored = hash_password("s3cret-password")
    scheme, cost, r, p, salt, digest = stored.split("$")
    assert (scheme, cost, r, p) == ("scrypt", "10", "8", "1")
    assert verify_password("s3cret-password", stored)
    assert not verify_password("wrong", stored)
    assert not verify_password("s3cret-password", None)
    assert not verify_password("s3cret-password", "garbage")
    assert hash_password("same") != hash_password("same")  # random salt
