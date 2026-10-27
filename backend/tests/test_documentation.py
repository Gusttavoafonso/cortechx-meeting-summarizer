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
