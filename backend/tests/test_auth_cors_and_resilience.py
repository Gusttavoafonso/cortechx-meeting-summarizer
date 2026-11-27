from __future__ import annotations

from unittest.mock import patch

import pytest
from app.core.config import Settings, settings
from app.core.errors import register_exception_handlers
from app.main import app
from app.services.auth_service import verify_google_token
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError


@pytest.mark.parametrize("origin", ["http://localhost:3001", "http://127.0.0.1:5173"])
@pytest.mark.parametrize("path", ["/auth/google", "/auth/register"])
def test_cors_allows_local_loopback_ports(origin: str, path: str) -> None:
    with TestClient(app) as client:
        res = client.options(
            path,
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == origin
    assert res.headers.get("access-control-allow-credentials") == "true"


def test_cors_rejects_untrusted_external_origin() -> None:
    with TestClient(app) as client:
        res = client.options(
            "/auth/google",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
    assert res.status_code == 400
    assert "access-control-allow-origin" not in res.headers


def test_operational_error_returns_503_json_with_cors_headers() -> None:
    test_app = FastAPI()
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.parsed_cors_origins,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(test_app)

    @test_app.get("/db-boom")
    def db_boom():
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    with TestClient(test_app) as test_client:
        res = test_client.get(
            "/db-boom",
            headers={"Origin": "http://localhost:3001"},
        )

    assert res.status_code == 503
    assert "Banco de dados indisponível" in res.json()["detail"]
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3001"


def test_verify_google_token_passes_clock_skew_and_google_auth_returns_has_password(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        settings, "google_client_id", "test-client-id.apps.googleusercontent.com"
    )
    captured: dict = {}

    def fake_verify(credential, request, audience=None, clock_skew_in_seconds=0):
        captured["audience"] = audience
        captured["clock_skew_in_seconds"] = clock_skew_in_seconds
        return {
            "sub": "g-sub-skew",
            "email": "skew@example.com",
            "email_verified": True,
            "name": "Skew User",
            "picture": "https://example.com/pic.png",
        }

    monkeypatch.setattr(
        "app.services.auth_service.id_token.verify_oauth2_token", fake_verify
    )

    claims = verify_google_token("dummy-id-token")
    assert claims["sub"] == "g-sub-skew"
    assert captured["audience"] == "test-client-id.apps.googleusercontent.com"
    assert captured["clock_skew_in_seconds"] == 10

    with patch("app.api.v1.auth.verify_google_token", return_value=claims):
        res = client.post("/auth/google", json={"credential": "dummy-id-token"})

    assert res.status_code == 200
    body = res.json()
    assert body["email"] == "skew@example.com"
    assert body["has_password"] is False


def test_parsed_cors_origins_appends_and_deduplicates() -> None:
    cfg = Settings(
        JWT_SECRET_KEY="test-only-secret-key-with-at-least-32-characters",
        CORS_ORIGINS="https://app.cortechx.ai/, http://localhost:3000, https://app.cortechx.ai",
    )
    assert "https://app.cortechx.ai" in cfg.parsed_cors_origins
    assert cfg.parsed_cors_origins.count("http://localhost:3000") == 1
    assert cfg.parsed_cors_origins.count("https://app.cortechx.ai") == 1
