import pytest
from app.core.database import Base, get_session
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

def override_get_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

app.dependency_overrides[get_session] = override_get_session


@pytest.fixture
def client():
    """Cliente HTTP reutilizável para os testes da API, com banco isolado."""
    Base.metadata.create_all(bind=engine)
    try:
        yield TestClient(app)
    finally:
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Cria uma sessão de banco isolada para cada teste."""
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)