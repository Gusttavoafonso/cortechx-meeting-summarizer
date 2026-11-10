from unittest.mock import patch

from app.api.deps import get_current_user
from app.core.security import hash_password, verify_password
from app.main import app
from app.models.user import User
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

VALID = {
    "name": "Mariana Souza",
    "email": "mariana@example.com",
    "password": "SenhaForte123!",
}


def _login(client: TestClient, email: str, password: str):
    # OAuth2PasswordRequestForm: application/x-www-form-urlencoded, campo `username`
    return client.post("/auth/login", data={"username": email, "password": password})


def _without_auth_override():
    return app.dependency_overrides.pop(get_current_user, None)


def test_register_success_returns_201_without_hash(
    client: TestClient, db_session: Session
):
    response = client.post("/auth/register", json=VALID)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Mariana Souza"
    assert data["email"] == "mariana@example.com"
    assert data["is_active"] is True
    assert "id" in data and "created_at" in data
    assert "password" not in data
    assert "hashed_password" not in data
    assert "SenhaForte123!" not in response.text

    user = db_session.query(User).filter(User.email == "mariana@example.com").first()
    assert user is not None
    assert user.hashed_password.startswith("$argon2")
    assert user.hashed_password != VALID["password"]
    assert verify_password(VALID["password"], user.hashed_password)


def test_register_normalizes_email(client: TestClient, db_session: Session):
    payload = {**VALID, "email": "  Mariana@Example.COM "}
    response = client.post("/auth/register", json=payload)

    assert response.status_code == 201
    assert response.json()["email"] == "mariana@example.com"
    assert db_session.query(User).count() == 1


def test_register_duplicate_email_returns_409(client: TestClient):
    assert client.post("/auth/register", json=VALID).status_code == 201

    # Mesmo e-mail com caixa/espaços diferentes também é duplicado
    res = client.post("/auth/register", json={**VALID, "email": " MARIANA@example.com"})

    assert res.status_code == 409
    assert "Já existe uma conta" in res.json()["detail"]


def test_register_short_password_rejected(client: TestClient):
    res = client.post("/auth/register", json={**VALID, "password": "1234567"})
    assert res.status_code == 422


def test_register_accepts_8_char_password(client: TestClient):
    res = client.post("/auth/register", json={**VALID, "password": "12345678"})
    assert res.status_code == 201


def test_register_invalid_email_rejected(client: TestClient):
    res = client.post("/auth/register", json={**VALID, "email": "nao-e-email"})
    assert res.status_code == 422


def test_login_success_returns_bearer_token(client: TestClient):
    client.post("/auth/register", json=VALID)

    res = _login(client, "mariana@example.com", VALID["password"])

    assert res.status_code == 200
    data = res.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]


def test_login_email_is_case_insensitive(client: TestClient):
    client.post("/auth/register", json=VALID)

    res = _login(client, "  MARIANA@example.com ", VALID["password"])

    assert res.status_code == 200


def test_login_token_grants_access_to_users_me(client: TestClient):
    client.post("/auth/register", json=VALID)
    token = _login(client, "mariana@example.com", VALID["password"]).json()[
        "access_token"
    ]

    override = _without_auth_override()
    try:
        res = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.json()["email"] == "mariana@example.com"
        assert "hashed_password" not in res.json()
    finally:
        if override:
            app.dependency_overrides[get_current_user] = override


def test_login_failures_share_the_same_generic_response(
    client: TestClient, db_session: Session
):
    client.post("/auth/register", json=VALID)
    db_session.add(User(google_id="g-1", email="google@example.com", name="Google"))
    db_session.add(
        User(
            email="inativo@example.com",
            name="Inativo",
            hashed_password=hash_password(VALID["password"]),
            is_active=False,
        )
    )
    db_session.commit()

    responses = [
        _login(client, "mariana@example.com", "SenhaErrada123"),  # senha errada
        _login(client, "naoexiste@example.com", "QualquerSenha1"),  # e-mail inexistente
        _login(client, "google@example.com", "QualquerSenha1"),  # conta Google
        _login(client, "inativo@example.com", VALID["password"]),  # conta inativa
    ]

    for res in responses:
        assert res.status_code == 401
        assert res.headers["WWW-Authenticate"] == "Bearer"
    assert len({r.text for r in responses}) == 1
    assert "incorretos" in responses[0].json()["detail"]


def test_login_requires_form_data(client: TestClient):
    res = client.post("/auth/login", json={"username": "a@b.com", "password": "x"})
    assert res.status_code == 422



def test_google_login_rejects_inactive_user(client: TestClient, db_session: Session):
    db_session.add(
        User(google_id="g-off", email="off@example.com", name="Off", is_active=False)
    )
    db_session.commit()
    mock_google = {"sub": "g-off", "email": "off@example.com", "name": "Off"}

    with patch("app.api.v1.auth.verify_google_token", return_value=mock_google):
        res = client.post("/auth/google", json={"credential": "tok"})

    assert res.status_code == 401


def test_health_is_public():
    from fastapi.testclient import TestClient as PlainClient

    # Cliente sem overrides de dependência e sem token
    with PlainClient(app) as plain:
        res = plain.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}

