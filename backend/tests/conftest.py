# ruff: noqa: E402
import os

# Precisa vir antes de qualquer import de `app`: Settings exige JWT_SECRET_KEY.
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-only-secret-key-with-at-least-32-characters"
)

from collections.abc import Generator, Callable

import pytest
from app.api.deps import get_current_user
from app.core.database import Base, get_session
from app.main import app
from app.models.user import User
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
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Cliente HTTP reutilizável para os testes da API, com banco isolado."""

    def override_get_session():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user():
        user = db_session.query(User).filter(User.google_id == "default_test_sub").first()
        if not user:
            user = User(
                google_id="default_test_sub",
                email="default_test@cortechx.com",
                name="Default Test User",
                picture_url="https://lh3.googleusercontent.com/test.jpg",
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
        return user

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def real_auth_overrides(db_session: Session) -> Generator[None, None, None]:
    """Só get_session é sobrescrito; get_current_user usa o JWT de verdade."""

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides.pop(get_current_user, None)
    yield
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def anon_client(real_auth_overrides: None) -> Generator[TestClient, None, None]:
    """Cliente SEM token e sem override: autenticação real (testes de 401)."""
    test_client = TestClient(app)
    yield test_client
    test_client.close()


@pytest.fixture
def auth_user(db_session: Session) -> User:
    """Usuário ativo já persistido (senha: DEFAULT_PASSWORD)."""
    return create_test_user(db_session)


@pytest.fixture
def auth_client(
    auth_user: User, real_auth_overrides: None
) -> Generator[TestClient, None, None]:
    """Cliente já autenticado como ``auth_user`` (Bearer token real)."""
    test_client = TestClient(app, headers=auth_headers(auth_user))
    yield test_client
    test_client.close()


@pytest.fixture
def make_auth_client(
    db_session: Session, real_auth_overrides: None
) -> Generator[Callable[..., tuple[TestClient, User]], None, None]:
    """Fábrica para testes com mais de um usuário (isolamento da 1B):

        alice_client, alice = make_auth_client(name="Alice")
        bob_client, bob = make_auth_client(name="Bob")
    """
    clients: list[TestClient] = []

    def factory(**user_kwargs) -> tuple[TestClient, User]:
        user = create_test_user(db_session, **user_kwargs)
        test_client = TestClient(app, headers=auth_headers(user))
        clients.append(test_client)
        return test_client, user

    yield factory
    for test_client in clients:
        test_client.close()