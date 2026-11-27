from fastapi.testclient import TestClient


def test_swagger_ui_is_available(client: TestClient) -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()
    assert "/openapi.json" in response.text


def test_openapi_schema_is_available(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200

    schema = response.json()
    assert schema["info"]["title"] == "CortechX Meeting Summarizer"
    assert schema["info"]["version"] == "0.1.0"
    assert "/health" in schema["paths"]
    assert "get" in schema["paths"]["/health"]


def test_openapi_declara_a_autenticacao_das_rotas(client: TestClient) -> None:
    """A documentação precisa mostrar que as rotas de reunião exigem sessão."""
    schema = client.get("/openapi.json").json()

    assert set(schema["components"]["securitySchemes"]) == {
        "Cookie de sessão",
        "Bearer",
    }

    for path, operations in schema["paths"].items():
        if not path.startswith("/meetings"):
            continue
        for method, operation in operations.items():
            rota = f"{method.upper()} {path}"
            assert operation.get("security"), f"{rota} não declara autenticação"
            assert "401" in operation["responses"], f"{rota} não documenta o 401"


def test_health_permanece_sem_autenticacao_na_documentacao(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert "security" not in schema["paths"]["/health"]["get"]
