from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import httpx
import pytest
from app.core.config import settings
from app.integrations.providers.discord import DiscordProvider, _mask_webhook_url
from app.integrations.registry import default_registry
from app.integrations.service import IntegrationService
from app.schemas.integration import MeetingIntegrationPayload, TaskIntegrationPayload
from pydantic import HttpUrl, SecretStr


def _sample_payload(title: str = "Planejamento da Sprint") -> MeetingIntegrationPayload:
    return MeetingIntegrationPayload(
        meeting_id=1,
        title=title,
        summary="A equipe alinhou entregas e prazos.",
        objective="Alinhar sprint",
        key_points=["Implementar Discord"],
        decisions=["Usar Webhooks"],
        tasks=[
            TaskIntegrationPayload(
                description="Criar DiscordProvider",
                responsible="Sergio",
                deadline=date(2026, 10, 15),
            )
        ],
        created_at=datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc),
    )


class TestDiscordProviderConfiguration:
    def test_registered_in_default_registry(self):
        assert "discord" in default_registry.list_available()
        assert default_registry.get("discord") is DiscordProvider

    def test_missing_webhook_url_returns_failure(self, monkeypatch):
        monkeypatch.setattr(settings, "discord_webhook_url", None)
        provider = DiscordProvider(webhook_url=None)

        result = provider.send(_sample_payload())

        assert result.provider == "discord"
        assert result.success is False
        assert "URL do webhook do Discord não configurada" in (result.error or "")

    def test_invalid_webhook_url_returns_failure(self):
        provider = DiscordProvider(webhook_url="invalid-url-without-scheme")

        result = provider.send(_sample_payload())

        assert result.success is False
        assert "URL do webhook do Discord inválida" in (result.error or "")

    def test_supports_secret_str_and_http_url(self):
        secret_url = SecretStr("https://discord.com/api/webhooks/123/secret_token")
        provider = DiscordProvider(webhook_url=secret_url)
        assert (
            provider.webhook_url == "https://discord.com/api/webhooks/123/secret_token"
        )

        http_url = HttpUrl("https://discord.com/api/webhooks/123/http_url")
        provider2 = DiscordProvider(webhook_url=http_url)
        assert provider2.webhook_url == "https://discord.com/api/webhooks/123/http_url"

    def test_falls_back_to_settings_when_available(self, monkeypatch):
        fallback_url = "https://discord.com/api/webhooks/999/fallback_token"
        monkeypatch.setattr(settings, "discord_webhook_url", fallback_url)

        provider = DiscordProvider(webhook_url=None)
        assert provider.webhook_url == fallback_url

    def test_mask_webhook_url_hides_sensitive_token(self):
        url = "https://discord.com/api/webhooks/123456789/my-secret-token"
        masked = _mask_webhook_url(url)
        assert "my-secret-token" not in masked
        assert masked == "https://discord.com/api/webhooks/123456789/***masked***"


class TestDiscordProviderExecution:
    @pytest.fixture(autouse=True)
    def disable_sleep(self, monkeypatch):
        monkeypatch.setattr(DiscordProvider, "_sleep", lambda self, s: None)

    def test_successful_send_single_chunk(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = httpx.Response(status_code=204)

        provider = DiscordProvider(
            webhook_url="https://discord.com/api/webhooks/1/token",
            client=mock_client,
        )

        result = provider.send(_sample_payload())

        assert result.success is True
        assert result.provider == "discord"
        assert result.metadata["chunks_sent"] == 1
        assert result.metadata["total_chunks"] == 1
        assert mock_client.post.call_count == 1

        call_args = mock_client.post.call_args
        assert call_args.args[0] == "https://discord.com/api/webhooks/1/token"
        assert "content" in call_args.kwargs["json"]
        assert "Reunião: Planejamento da Sprint" in call_args.kwargs["json"]["content"]

    def test_successful_send_multiple_chunks(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = httpx.Response(status_code=204)

        provider = DiscordProvider(
            webhook_url="https://discord.com/api/webhooks/1/token",
            client=mock_client,
        )

        long_payload = _sample_payload()
        long_payload.summary = "A" * 3500

        result = provider.send(long_payload)

        assert result.success is True
        assert result.metadata["chunks_sent"] > 1
        assert mock_client.post.call_count == result.metadata["chunks_sent"]

    def test_rate_limit_retry_succeeds(self):
        mock_client = MagicMock(spec=httpx.Client)
        response_429 = httpx.Response(
            status_code=429,
            headers={"Retry-After": "0.1"},
            json={"message": "You are being rate limited.", "retry_after": 0.1},
        )
        response_204 = httpx.Response(status_code=204)
        mock_client.post.side_effect = [response_429, response_204]

        provider = DiscordProvider(
            webhook_url="https://discord.com/api/webhooks/1/token",
            client=mock_client,
            max_retries=2,
        )

        result = provider.send(_sample_payload())

        assert result.success is True
        assert mock_client.post.call_count == 2

    def test_rate_limit_exhausted_returns_failure(self):
        mock_client = MagicMock(spec=httpx.Client)
        response_429 = httpx.Response(
            status_code=429,
            headers={"Retry-After": "0.1"},
            json={"message": "You are being rate limited.", "retry_after": 0.1},
        )
        mock_client.post.return_value = response_429

        provider = DiscordProvider(
            webhook_url="https://discord.com/api/webhooks/1/token",
            client=mock_client,
            max_retries=1,
        )

        result = provider.send(_sample_payload())

        assert result.success is False
        assert "rate limit 429" in (result.error or "")
        assert result.metadata["status_code"] == 429
        assert mock_client.post.call_count == 2

    def test_server_error_5xx_retries_and_fails_gracefully(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = httpx.Response(status_code=503)

        provider = DiscordProvider(
            webhook_url="https://discord.com/api/webhooks/1/token",
            client=mock_client,
            max_retries=2,
        )

        result = provider.send(_sample_payload())

        assert result.success is False
        assert "HTTP 503" in (result.error or "")
        assert mock_client.post.call_count == 3

    def test_client_error_400_does_not_retry(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = httpx.Response(status_code=400)

        provider = DiscordProvider(
            webhook_url="https://discord.com/api/webhooks/1/token",
            client=mock_client,
            max_retries=2,
        )

        result = provider.send(_sample_payload())

        assert result.success is False
        assert "HTTP 400" in (result.error or "")
        assert mock_client.post.call_count == 1

    def test_client_error_404_not_found(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = httpx.Response(status_code=404)

        provider = DiscordProvider(
            webhook_url="https://discord.com/api/webhooks/1/token",
            client=mock_client,
        )

        result = provider.send(_sample_payload())

        assert result.success is False
        assert "não encontrado" in (result.error or "")
        assert mock_client.post.call_count == 1

    def test_timeout_retries_and_returns_failure(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.side_effect = httpx.ReadTimeout("Timeout")

        provider = DiscordProvider(
            webhook_url="https://discord.com/api/webhooks/1/token",
            client=mock_client,
            max_retries=1,
        )

        result = provider.send(_sample_payload())

        assert result.success is False
        assert "timeout" in (result.error or "").lower()
        assert mock_client.post.call_count == 2

    def test_network_error_retries_and_returns_failure(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.side_effect = httpx.ConnectError("Network is down")

        provider = DiscordProvider(
            webhook_url="https://discord.com/api/webhooks/1/token",
            client=mock_client,
            max_retries=1,
        )

        result = provider.send(_sample_payload())

        assert result.success is False
        assert "Falha de conexão" in (result.error or "")
        assert mock_client.post.call_count == 2

    def test_webhook_token_is_never_leaked_in_error_result(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = httpx.Response(
            status_code=401, text="Invalid token"
        )

        secret_token = "ultra-secret-discord-token-xyz"
        provider = DiscordProvider(
            webhook_url=f"https://discord.com/api/webhooks/123/{secret_token}",
            client=mock_client,
        )

        result = provider.send(_sample_payload())

        assert result.success is False
        assert secret_token not in (result.error or "")


class TestIntegrationServiceWithDiscord:
    def test_integration_service_sends_to_discord(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = httpx.Response(status_code=204)

        service = IntegrationService()
        result = service.send(
            "discord",
            _sample_payload(),
            webhook_url="https://discord.com/api/webhooks/123/token",
            client=mock_client,
        )

        assert result.success is True
        assert result.provider == "discord"
        assert result.metadata["chunks_sent"] == 1
