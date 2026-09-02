import pytest
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """Cliente HTTP reutilizável para os testes da API."""
    return TestClient(app)
