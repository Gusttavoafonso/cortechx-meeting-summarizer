from unittest.mock import patch

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.exceptions import InvalidGoogleTokenError
from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_authenticate_google_success(client: TestClient, db_session: Session):
    """Testa o fluxo de login com ID Token válido do Google."""
    mock_payload = {
        "sub": "google-user-12345",
        "email": "ana.silva@example.com",
        "email_verified": True,
        "name": "Ana Silva",
        "picture": "https://lh3.googleusercontent.com/photo.jpg",
    }

    with patch(
        "app.api.v1.auth.verify_google_token",
        return_value=mock_payload,
    ):
        response = client.post(
            "/auth/google",
            json={"credential": "mocked-valid-google-id-token"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Ana Silva"
    assert data["picture_url"] == "https://lh3.googleusercontent.com/photo.jpg"
    # Garante privacidade: email não deve vazar na resposta pública
    assert "email" not in data
    assert "id" in data

    # Verifica se o cookie HTTP-Only foi setado corretamente
    cookie = response.cookies.get(settings.session_cookie_name)
    assert cookie is not None
    assert "Set-Cookie" in response.headers
    assert "HttpOnly" in response.headers["Set-Cookie"]

    # Verifica persistência no banco
    user = (
        db_session.query(User)
        .filter(User.google_id == "google-user-12345")
        .first()
    )
    assert user is not None
    assert user.email == "ana.silva@example.com"
    assert user.name == "Ana Silva"


def test_authenticate_google_unverified_email(client: TestClient):
    """Testa rejeição de token Google quando email_verified é False."""
    with patch(
        "app.api.v1.auth.verify_google_token",
        side_effect=InvalidGoogleTokenError(
            "O e-mail da conta Google não foi verificado pelo Google."
        ),
    ):
        response = client.post(
            "/auth/google",
            json={"credential": "token-unverified-email"},
        )

    assert response.status_code == 401
    assert "não foi verificado" in response.json()["detail"]


def test_authenticate_google_invalid_token(client: TestClient):
    """Testa a rejeição de ID Token falso ou expirado pelo Google."""
    with patch(
        "app.api.v1.auth.verify_google_token",
        side_effect=InvalidGoogleTokenError("Assinatura do token inválida"),
    ):
        response = client.post(
            "/auth/google",
            json={"credential": "invalid-token"},
        )

    assert response.status_code == 401
    assert "Assinatura do token inválida" in response.json()["detail"]


def test_authenticate_google_missing_required_claims(client: TestClient):
    """Testa rejeição de token que não contém claims essenciais (sub ou email)."""
    with patch(
        "app.api.v1.auth.verify_google_token",
        return_value={"name": "Sem Sub"},
    ):
        response = client.post(
            "/auth/google",
            json={"credential": "token-without-sub"},
        )

    assert response.status_code == 400
    assert "sub ou email" in response.json()["detail"]


def test_get_me_unauthenticated(client: TestClient):
    """Testa acesso a /users/me sem autenticação (401)."""
    # Remove qualquer override temporariamente para testar a dependência real
    override = app.dependency_overrides.pop(get_current_user, None)
    try:
        response = client.get("/users/me")
        assert response.status_code == 401
        assert "Não autenticado" in response.json()["detail"]
    finally:
        if override:
            app.dependency_overrides[get_current_user] = override


def test_get_me_authenticated_via_cookie(client: TestClient, db_session: Session):
    """Testa obter perfil (/users/me) com cookie HTTP-Only válido."""
    user = User(
        google_id="sub-profile-test",
        email="profile@example.com",
        name="Carlos Eduardo",
        picture_url="https://example.com/carlos.jpg",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(user.id)

    # Remove override para testar a dependência get_current_user real com o cookie
    override = app.dependency_overrides.pop(get_current_user, None)
    try:
        client.cookies.set(settings.session_cookie_name, token)
        response = client.get("/users/me")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user.id
        assert data["name"] == "Carlos Eduardo"
        assert data["email"] == "profile@example.com"
        assert data["is_active"] is True
        assert "hashed_password" not in data
    finally:
        client.cookies.clear()
        if override:
            app.dependency_overrides[get_current_user] = override


def test_get_me_expired_session(client: TestClient, db_session: Session):
    """Testa rejeição de sessão expirada."""
    from datetime import datetime, timedelta, timezone

    import jwt

    user = User(
        google_id="sub-expired-test",
        email="expired@example.com",
        name="Expirado",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Cria token intencionalmente expirado há 1 hora
    past_time = datetime.now(timezone.utc) - timedelta(hours=1)
    expired_payload = {
        "sub": str(user.id),
        "iat": int((past_time - timedelta(minutes=5)).timestamp()),
        "exp": int(past_time.timestamp()),
    }
    expired_token = jwt.encode(
        expired_payload,
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )

    override = app.dependency_overrides.pop(get_current_user, None)
    try:
        client.cookies.set(settings.session_cookie_name, expired_token)
        response = client.get("/users/me")
        assert response.status_code == 401
        assert "Sessão expirada" in response.json()["detail"]
    finally:
        client.cookies.clear()
        if override:
            app.dependency_overrides[get_current_user] = override


def test_logout(client: TestClient):
    """Testa logout removendo o cookie de sessão."""
    response = client.post("/auth/logout")
    assert response.status_code == 200
    assert response.json()["message"] == "Logout realizado com sucesso"
    # Cookie deve ter sido removido ou expirado
    set_cookie = response.headers.get("Set-Cookie", "")
    assert (
        f'{settings.session_cookie_name}=""' in set_cookie
        or f"{settings.session_cookie_name}=;" in set_cookie
        or "Max-Age=0" in set_cookie
    )


def test_meeting_user_segregation(client: TestClient, db_session: Session):
    """Testa isolamento multi-tenant: B não acessa reuniões do usuário A."""
    # Cria Usuário A e Usuário B
    user_a = User(
        google_id="sub-user-a",
        email="a@example.com",
        name="Usuário A",
    )
    user_b = User(
        google_id="sub-user-b",
        email="b@example.com",
        name="Usuário B",
    )
    db_session.add_all([user_a, user_b])
    db_session.commit()
    db_session.refresh(user_a)
    db_session.refresh(user_b)

    token_a = create_access_token(user_a.id)
    token_b = create_access_token(user_b.id)

    # Remove override para usar os cookies de cada usuário
    override = app.dependency_overrides.pop(get_current_user, None)
    try:
        # 1. Usuário A cria uma reunião
        client.cookies.set(settings.session_cookie_name, token_a)
        res_create = client.post(
            "/meetings", json={"title": "Reunião Confidencial do A"}
        )
        assert res_create.status_code == 201
        meeting_a_id = res_create.json()["id"]

        # Usuário A lista reuniões -> vê sua reunião
        res_list_a = client.get("/meetings")
        assert res_list_a.status_code == 200
        assert any(m["id"] == meeting_a_id for m in res_list_a.json())

        # 2. Usuário B tenta acessar
        client.cookies.set(settings.session_cookie_name, token_b)

        # Usuário B lista reuniões -> não vê a reunião do Usuário A
        res_list_b = client.get("/meetings")
        assert res_list_b.status_code == 200
        assert not any(m["id"] == meeting_a_id for m in res_list_b.json())

        # Usuário B tenta acessar reunião do A diretamente por ID -> 404
        res_get_b = client.get(f"/meetings/{meeting_a_id}")
        assert res_get_b.status_code == 404
        assert "não encontrada" in res_get_b.json()["detail"]
    finally:
        client.cookies.clear()
        if override:
            app.dependency_overrides[get_current_user] = override
