from unittest.mock import patch

from app.api.deps import get_current_user
from app.core.config import settings
from app.main import app
from app.models.user import User
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_register_success(client: TestClient, db_session: Session):
    """Testa cadastro com e-mail e senha, verificando hashing e cookie de sessão."""
    payload = {
        "email": "mariana@example.com",
        "password": "SenhaForte123!",
        "name": "Mariana Souza",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Mariana Souza"
    assert "id" in data
    assert "email" not in data
    assert "password" not in data

    # Cookie HTTP-Only de sessão deve estar presente
    cookie = response.cookies.get(settings.session_cookie_name)
    assert cookie is not None
    assert "HttpOnly" in response.headers.get("Set-Cookie", "")

    # Validação no banco de dados
    user = db_session.query(User).filter(User.email == "mariana@example.com").first()
    assert user is not None
    assert user.hashed_password is not None
    assert user.hashed_password.startswith("$2")
    assert user.hashed_password != "SenhaForte123!"


def test_register_duplicate_email(client: TestClient):
    """Testa rejeição (409) de tentativa de cadastro com e-mail já existente."""
    payload = {
        "email": "duplicado@example.com",
        "password": "MinhaSenha123",
        "name": "Primeiro Cadastro",
    }
    res1 = client.post("/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/auth/register", json=payload)
    assert res2.status_code == 409
    assert "Já existe uma conta" in res2.json()["detail"]


def test_register_short_password(client: TestClient):
    """Testa rejeição de senha com menos de 8 caracteres via validação Pydantic."""
    payload = {
        "email": "curta@example.com",
        "password": "123",
        "name": "Senha Curta",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 422


def test_register_long_password_rejected(client: TestClient):
    """Testa rejeição de senha com mais de 72 caracteres para prevenir DoS em Bcrypt."""
    payload = {
        "email": "longa@example.com",
        "password": "A" * 73,
        "name": "Senha Longa",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 422


def test_login_success_and_get_me(client: TestClient):
    """Testa login com sucesso e acesso a rota protegida /auth/me usando o cookie."""
    # 1. Registra usuário
    client.post(
        "/auth/register",
        json={
            "email": "login_sucesso@example.com",
            "password": "SenhaValida123",
            "name": "Usuário Login",
        },
    )
    client.cookies.clear()

    # 2. Faz login
    res_login = client.post(
        "/auth/login",
        json={
            "email": "login_sucesso@example.com",
            "password": "SenhaValida123",
        },
    )
    assert res_login.status_code == 200
    assert res_login.json()["name"] == "Usuário Login"
    assert res_login.cookies.get(settings.session_cookie_name) is not None

    # 3. Chama /auth/me sem override de autenticação
    override = app.dependency_overrides.pop(get_current_user, None)
    try:
        res_me = client.get("/auth/me")
        assert res_me.status_code == 200
        assert res_me.json()["name"] == "Usuário Login"
    finally:
        client.cookies.clear()
        if override:
            app.dependency_overrides[get_current_user] = override


def test_login_wrong_password(client: TestClient):
    """Testa rejeição de login com senha incorreta (401)."""
    client.post(
        "/auth/register",
        json={
            "email": "senha_errada@example.com",
            "password": "SenhaCorreta123",
            "name": "Teste",
        },
    )
    client.cookies.clear()

    res = client.post(
        "/auth/login",
        json={
            "email": "senha_errada@example.com",
            "password": "SenhaTotalmenteErrada",
        },
    )
    assert res.status_code == 401
    assert "incorretos" in res.json()["detail"]


def test_login_nonexistent_email(client: TestClient):
    """Testa rejeição de login com e-mail não cadastrado (401)."""
    res = client.post(
        "/auth/login",
        json={
            "email": "naoexiste@example.com",
            "password": "QualquerSenha123",
        },
    )
    assert res.status_code == 401
    assert "incorretos" in res.json()["detail"]


def test_login_google_user_without_password(client: TestClient, db_session: Session):
    """Testa usuário criado via Google sem senha tentando login tradicional."""
    google_user = User(
        google_id="google-only-user",
        email="googleonly@example.com",
        name="Google Only",
        hashed_password=None,
    )
    db_session.add(google_user)
    db_session.commit()

    res = client.post(
        "/auth/login",
        json={
            "email": "googleonly@example.com",
            "password": "TentativaDeSenha123",
        },
    )
    assert res.status_code == 401
    assert "via Google" in res.json()["detail"]


def test_account_unification_google_after_email_password(
    client: TestClient, db_session: Session
):
    """Testa unificação: usuário cadastra com email/senha e depois entra com Google."""
    # 1. Usuário se registra com email e senha
    res_reg = client.post(
        "/auth/register",
        json={
            "email": "unificado@example.com",
            "password": "MinhaSenha123",
            "name": "Nome Original",
        },
    )
    assert res_reg.status_code == 201
    user_id = res_reg.json()["id"]

    # Usuário cria uma reunião
    res_meet = client.post("/meetings", json={"title": "Reunião Unificada"})
    assert res_meet.status_code == 201
    meeting_id = res_meet.json()["id"]

    # 2. Usuário faz login com o Google com o mesmo e-mail
    mock_google = {
        "sub": "google-sub-unificado-999",
        "email": "unificado@example.com",
        "email_verified": True,
        "name": "Nome Atualizado Google",
        "picture": "https://lh3.googleusercontent.com/unificado.jpg",
    }
    with patch("app.api.v1.auth.verify_google_token", return_value=mock_google):
        res_google = client.post(
            "/auth/google", json={"credential": "token-google-unificado"}
        )
    assert res_google.status_code == 200
    assert res_google.json()["id"] == user_id
    assert res_google.json()["name"] == "Nome Atualizado Google"

    # Verifica no banco se o registro foi unificado mantendo o mesmo ID
    user_db = db_session.query(User).filter(User.id == user_id).first()
    assert user_db is not None
    assert user_db.google_id == "google-sub-unificado-999"
    assert user_db.hashed_password is not None  # Senha antiga foi mantida!

    # Usuário ainda acessa a reunião criada antes da unificação
    res_get_meet = client.get(f"/meetings/{meeting_id}")
    assert res_get_meet.status_code == 200
    assert res_get_meet.json()["title"] == "Reunião Unificada"
