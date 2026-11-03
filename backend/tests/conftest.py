# ruff: noqa: E402
import os

# Precisa vir antes de qualquer import de `app`: Settings exige JWT_SECRET_KEY.
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-only-secret-key-with-at-least-32-characters"
)

from collections.abc import Generator

import pytest
from app.api.deps import get_current_user
from app.core.database import Base, get_session
from app.main import app
from app.models.user import User
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
