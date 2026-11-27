# ruff: noqa: E402
import os

# Deve preceder imports de app: Settings exige JWT_SECRET_KEY.
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-only-secret-key-with-at-least-32-characters"
)

from collections.abc import Callable, Generator

import pytest
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import Base, get_session
from app.main import app
from app.models.user import User
from app.services.auth_service import create_session_token
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from tests.test_auth_helpers import auth_headers, create_test_user


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Cria uma sessão de banco isolada para cada teste."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def _api_database(db_session: Session) -> Generator[None, None, None]:
    """Substitui apenas o banco; get_current_user valida o JWT de verdade."""

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides.pop(get_current_user, None)
    try:
        yield
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def real_auth_overrides(_api_database: None) -> Generator[None, None, None]:
    """Mantém o contrato de fixtures Dev com autenticação real."""
    yield


@pytest.fixture
def create_user(db_session: Session) -> Callable[..., User]:
    """Fábrica de usuários persistidos para os testes de posse."""

    def _create_user(
        email: str = "user@cortechx.com", name: str = "Usuário de Teste"
    ) -> User:
        user = User(email=email, name=name)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create_user


@pytest.fixture
def auth_user(db_session: Session) -> User:
    """Usuário ativo com senha DEFAULT_PASSWORD e e-mail único."""
    return create_test_user(db_session)


@pytest.fixture
def test_user(auth_user: User) -> User:
    """Nome usado pela PR para o mesmo dono autenticado em auth_client."""
    return auth_user


@pytest.fixture
def client(_api_database: None) -> Generator[TestClient, None, None]:
    """Cliente sem sessão para rotas públicas e rejeições 401 reais."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def anon_client(real_auth_overrides: None) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_client(
    auth_user: User, real_auth_overrides: None
) -> Generator[TestClient, None, None]:
    """Cliente autenticado como auth_user/test_user com Bearer real."""
    with TestClient(app, headers=auth_headers(auth_user)) as test_client:
        yield test_client


@pytest.fixture
def authenticate(
    _api_database: None,
) -> Generator[Callable[[User], TestClient], None, None]:
    """Fábrica da PR: clientes por usuário com cookie real e cleanup."""
    clients: list[TestClient] = []

    def factory(user: User) -> TestClient:
        authenticated = TestClient(app)
        authenticated.cookies.set(
            settings.session_cookie_name, create_session_token(user.id)
        )
        clients.append(authenticated)
        return authenticated

    yield factory
    for test_client in clients:
        test_client.close()


@pytest.fixture
def make_auth_client(
    db_session: Session, real_auth_overrides: None
) -> Generator[Callable[..., tuple[TestClient, User]], None, None]:
    """Fábrica Dev: cria usuário e cliente com Bearer real."""
    clients: list[TestClient] = []

    def factory(**user_kwargs) -> tuple[TestClient, User]:
        user = create_test_user(db_session, **user_kwargs)
        test_client = TestClient(app, headers=auth_headers(user))
        clients.append(test_client)
        return test_client, user

    yield factory
    for test_client in clients:
        test_client.close()
