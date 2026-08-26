from fastapi.testclient import TestClient

from app.main import app

# teste para verificar se a rota de health check está funcionando corretamente.
def test_health_check_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
