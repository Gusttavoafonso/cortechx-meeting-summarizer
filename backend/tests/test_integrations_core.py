from __future__ import annotations

import io
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.integrations.base import (
    IntegrationError,
    IntegrationProvider,
    ProviderExecutionError,
    ProviderNotFoundError,
)
from app.integrations.configuration import ProviderConfigurationResolver
from app.integrations.providers.console import ConsoleProvider
from app.integrations.registry import ProviderRegistry, default_registry
from app.integrations.service import IntegrationService
from app.schemas.integration import (
    IntegrationResult,
    MeetingIntegrationPayload,
    TaskIntegrationPayload,
)
from app.core.config import Settings


def _sample_payload() -> MeetingIntegrationPayload:
    return MeetingIntegrationPayload(
        meeting_id=1,
        title="Reunião de Alinhamento",
        summary="A equipe discutiu prazos e metas.",
        objective="Definir entregas da sprint",
        key_points=["Backend 80% concluído", "Frontend inicia na quarta"],
        decisions=["Usar Celery para async", "PostgreSQL como banco"],
        tasks=[
            TaskIntegrationPayload(
                id=10,
                description="Criar migrations",
                responsible="Dev1",
                deadline=date(2026, 10, 10),
            ),
            TaskIntegrationPayload(
                id=11,
                description="Testar webhook",
                responsible=None,
                deadline="sexta-feira",
            ),
        ],
        created_at=datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc),
    )


class TestIntegrationSchemas:
    def test_valid_payload_instantiation(self):
        payload = _sample_payload()
        assert payload.meeting_id == 1
        assert payload.title == "Reunião de Alinhamento"
        assert len(payload.tasks) == 2
        assert payload.tasks[0].deadline == date(2026, 10, 10)
        assert payload.tasks[1].deadline == "sexta-feira"

    def test_payload_validation_rejects_empty_fields(self):
        with pytest.raises(ValidationError):
            MeetingIntegrationPayload(
                meeting_id=0,
                title="",
                summary="",
            )

    def test_task_payload_validation(self):
        with pytest.raises(ValidationError):
            TaskIntegrationPayload(description="")

    def test_integration_result_defaults(self):
        result = IntegrationResult(
            provider="console",
            success=True,
        )
        assert result.provider == "console"
        assert result.success is True
        assert result.error is None
        assert result.metadata == {}
        assert isinstance(result.executed_at, datetime)

    def test_integration_result_failure(self):
        result = IntegrationResult(
            provider="discord",
            success=False,
            error="Webhook rate limited",
            metadata={"status_code": 429},
        )
        assert result.success is False
        assert result.error == "Webhook rate limited"
        assert result.metadata["status_code"] == 429


class TestProviderRegistry:
    def test_default_registry_has_console_provider(self):
        assert "console" in default_registry.list_available()
        provider_cls = default_registry.get("console")
        assert issubclass(provider_cls, IntegrationProvider)
        assert provider_cls is ConsoleProvider

    def test_registry_case_insensitive_lookup(self):
        provider_cls = default_registry.get("  CoNsOlE  ")
        assert provider_cls is ConsoleProvider

    def test_unknown_provider_raises_error(self):
        with pytest.raises(ProviderNotFoundError) as exc_info:
            default_registry.get("slack_unknown")
        assert "slack_unknown" in str(exc_info.value)
        assert issubclass(ProviderNotFoundError, IntegrationError)

    def test_custom_registry_registration_and_creation(self):
        registry = ProviderRegistry()

        @registry.register("dummy")
        class DummyProvider(IntegrationProvider):
            name = "dummy"

            def __init__(self, token: str = "abc"):
                self.token = token

            def send(self, payload: MeetingIntegrationPayload) -> IntegrationResult:
                return IntegrationResult(provider=self.name, success=True, metadata={"token": self.token})

        assert registry.list_available() == ["dummy"]
        instance = registry.create("dummy", token="xyz")
        assert isinstance(instance, DummyProvider)
        assert instance.token == "xyz"

        payload = _sample_payload()
        res = instance.send(payload)
        assert res.success is True
        assert res.metadata["token"] == "xyz"


class TestConsoleProvider:
    def test_console_provider_send_success(self):
        stream = io.StringIO()
        provider = ConsoleProvider(stream=stream)
        payload = _sample_payload()

        result = provider.send(payload)

        assert result.provider == "console"
        assert result.success is True
        assert result.metadata["meeting_id"] == 1
        assert result.metadata["tasks_count"] == 2
        assert result.metadata["key_points_count"] == 2
        assert result.metadata["decisions_count"] == 2

        output = stream.getvalue()
        assert "Reunião #1" in output
        assert "Reunião de Alinhamento" in output
        assert "Criar migrations" in output
        assert "Dev1" in output
        assert "sexta-feira" in output

    def test_console_provider_without_stream(self):
        provider = ConsoleProvider()
        payload = MeetingIntegrationPayload(
            meeting_id=99,
            title="Reunião Rápida",
            summary="Apenas um teste rápido.",
        )
        result = provider.send(payload)
        assert result.success is True
        assert result.metadata["tasks_count"] == 0
        assert provider.last_payload == payload


class TestErrorIsolation:
    def test_failing_provider_contract(self):
        class BrokenExternalProvider(IntegrationProvider):
            name = "broken"

            def send(self, payload: MeetingIntegrationPayload) -> IntegrationResult:
                try:
                    raise ConnectionResetError("Connection refused by remote host")
                except Exception as exc:
                    return IntegrationResult(
                        provider=self.name,
                        success=False,
                        error=f"Falha de comunicação: {exc}",
                        metadata={"attempt": 1},
                    )

        provider = BrokenExternalProvider()
        result = provider.send(_sample_payload())

        assert result.success is False
        assert "Connection refused" in result.error
        assert result.metadata["attempt"] == 1


class TestIntegrationService:
    def test_sends_payload_through_requested_provider(self):
        stream = io.StringIO()
        service = IntegrationService()

        result = service.send("console", _sample_payload(), stream=stream)

        assert result.success is True
        assert result.provider == "console"
        assert "Reunião de Alinhamento" in stream.getvalue()

    def test_returns_standard_result_for_unknown_provider(self):
        result = IntegrationService().send("unknown", _sample_payload())

        assert result.provider == "unknown"
        assert result.success is False
        assert result.error == "Provider de integração não encontrado."

    def test_isolates_provider_execution_failure(self):
        registry = ProviderRegistry()

        @registry.register("broken")
        class BrokenProvider(IntegrationProvider):
            name = "broken"

            def send(self, payload: MeetingIntegrationPayload) -> IntegrationResult:
                raise RuntimeError("token=secret-value")

        result = IntegrationService(registry).send("broken", _sample_payload())

        assert result.provider == "broken"
        assert result.success is False
        assert result.error == "Não foi possível executar a integração."
        assert "secret-value" not in result.error

    def test_uses_automatic_discord_configuration(self):
        registry = ProviderRegistry()

        @registry.register("discord")
        class DiscordProvider(IntegrationProvider):
            name = "discord"

            def __init__(self, webhook_url: str) -> None:
                self.webhook_url = webhook_url

            def send(self, payload: MeetingIntegrationPayload) -> IntegrationResult:
                return IntegrationResult(
                    provider=self.name,
                    success=True,
                    metadata={"webhook_url": self.webhook_url},
                )

        settings = Settings(
            _env_file=None,
            discord_webhook_url="https://discord.com/api/webhooks/123/token",
        )
        service = IntegrationService(
            registry,
            ProviderConfigurationResolver(settings),
        )

        result = service.send("discord", _sample_payload())

        assert result.success is True
        assert result.metadata["webhook_url"] == (
            "https://discord.com/api/webhooks/123/token"
        )

    def test_returns_safe_result_when_provider_configuration_is_missing(self):
        registry = ProviderRegistry()

        @registry.register("discord")
        class DiscordProvider(IntegrationProvider):
            name = "discord"

            def __init__(self, webhook_url: str) -> None:
                self.webhook_url = webhook_url

            def send(self, payload: MeetingIntegrationPayload) -> IntegrationResult:
                return IntegrationResult(provider=self.name, success=True)

        service = IntegrationService(
            registry,
            ProviderConfigurationResolver(Settings(_env_file=None)),
        )

        result = service.send("discord", _sample_payload())

        assert result.provider == "discord"
        assert result.success is False
        assert result.error == (
            "A configuração do provider de integração está ausente ou inválida."
        )
