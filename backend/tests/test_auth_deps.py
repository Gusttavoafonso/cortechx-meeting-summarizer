from datetime import datetime, timedelta, timezone

import jwt
import pytest
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.exceptions import InvalidSessionTokenError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.main import app
from app.models.user import User
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

SECRET = settings.JWT_SECRET_KEY.get_secret_value()


@pytest.fixture
def real_auth(client: TestClient):
    """Remove o override de get_current_user para exercitar a dependência real."""
    override = app.dependency_overrides.pop(get_current_user, None)
    yield client
    if override:
        app.dependency_overrides[get_current_user] = override


def _user(db: Session, **kwargs) -> User:
    user = User(
        email=kwargs.pop("email", "user@example.com"),
        name="User",
        hashed_password=hash_password("SenhaValida1"),
        **kwargs,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_password_hash_is_argon2_and_verifies():
    hashed = hash_password("SenhaValida1")

    assert hashed.startswith("$argon2")
    assert verify_password("SenhaValida1", hashed)
    assert not verify_password("outra", hashed)
    assert not verify_password("SenhaValida1", "not-a-hash")


def test_access_token_roundtrip_and_short_expiry():
    token = create_access_token(42)
    payload = jwt.decode(token, SECRET, algorithms=[settings.JWT_ALGORITHM])

    assert decode_access_token(token) == 42
    assert payload["exp"] - payload["iat"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


@pytest.mark.parametrize("bad", ["lixo", "a.b.c", ""])
def test_decode_rejects_malformed_token(bad):
    with pytest.raises(InvalidSessionTokenError):
        decode_access_token(bad)


def test_decode_rejects_wrong_signature():
    forged = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "x" * 40,
        algorithm="HS256",
    )
    with pytest.raises(InvalidSessionTokenError):
        decode_access_token(forged)


def test_decode_rejects_token_without_sub():
    token = jwt.encode(
        {"exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        SECRET,
        algorithm="HS256",
    )
    with pytest.raises(InvalidSessionTokenError):
        decode_access_token(token)


def test_valid_token_returns_user(real_auth: TestClient, db_session: Session):
    user = _user(db_session)

    res = real_auth.get("/users/me", headers=_bearer(create_access_token(user.id)))

    assert res.status_code == 200
    assert res.json()["id"] == user.id


@pytest.mark.parametrize(
    "headers",
    [None, {"Authorization": "Bearer lixo"}, {"Authorization": "Basic abc"}],
)
def test_missing_or_invalid_token_returns_401_with_www_authenticate(
    real_auth: TestClient, headers
):
    res = real_auth.get("/users/me", headers=headers)

    assert res.status_code == 401
    assert res.headers["WWW-Authenticate"] == "Bearer"


def test_expired_token_returns_401(real_auth: TestClient, db_session: Session):
    user = _user(db_session)
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    token = jwt.encode(
        {"sub": str(user.id), "iat": past - timedelta(hours=1), "exp": past},
        SECRET,
        algorithm="HS256",
    )

    res = real_auth.get("/users/me", headers=_bearer(token))

    assert res.status_code == 401
    assert res.headers["WWW-Authenticate"] == "Bearer"
    assert "expirada" in res.json()["detail"]


def test_token_for_missing_user_returns_401(real_auth: TestClient):
    res = real_auth.get("/users/me", headers=_bearer(create_access_token(99999)))

    assert res.status_code == 401
    assert res.headers["WWW-Authenticate"] == "Bearer"


def test_inactive_user_returns_401(real_auth: TestClient, db_session: Session):
    user = _user(db_session, is_active=False)

    res = real_auth.get("/users/me", headers=_bearer(create_access_token(user.id)))

    assert res.status_code == 401
    assert res.headers["WWW-Authenticate"] == "Bearer"


def test_protected_routes_require_auth(real_auth: TestClient):
    assert real_auth.get("/meetings").status_code == 401
