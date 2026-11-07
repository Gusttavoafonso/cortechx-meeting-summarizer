from collections.abc import Callable, Generator

import pytest
from app.core.config import settings
from app.core.database import Base, get_session
from app.main import app
from app.models.user import User
from app.services.auth_service import create_session_token
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


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
    """Liga a API ao banco isolado do teste.

    Só a sessão é substituída: `get_current_user` roda de verdade, para que os
    testes exercitem a autenticação real em vez de contorná-la.
    """

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        yield
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def create_user(db_session: Session) -> Callable[..., User]:
    """Fábrica de usuários persistidos."""

    def _create_user(
        email: str = "user@cortechx.com",
        name: str = "Usuário de Teste",
    ) -> User:
        user = User(email=email.strip().lower(), name=name)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create_user


@pytest.fixture
def test_user(create_user: Callable[..., User]) -> User:
    """Usuário dono das reuniões criadas pelo `auth_client`."""
    return create_user()


@pytest.fixture
def client(_api_database: None) -> Generator[TestClient, None, None]:
    """Cliente HTTP sem sessão.

    Serve as rotas públicas (`/health`, documentação) e os testes que provam
    que as rotas de reunião respondem 401 sem token.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def authenticate(_api_database: None) -> Callable[[User], TestClient]:
    """Fábrica de clientes autenticados, um por usuário.

    Cada cliente carrega o cookie de sessão real do usuário, o que permite
    exercitar o isolamento entre dois usuários na mesma API.
    """

    def _authenticate(user: User) -> TestClient:
        authenticated = TestClient(app)
        authenticated.cookies.set(
            settings.session_cookie_name,
            create_session_token(user.id),
        )
        return authenticated

    return _authenticate


@pytest.fixture
def auth_client(
    client: TestClient,
    test_user: User,
) -> TestClient:
    """Cliente HTTP autenticado como `test_user`, via cookie de sessão real."""
    client.cookies.set(
        settings.session_cookie_name,
        create_session_token(test_user.id),
    )
    return client
