from __future__ import annotations

import io
from datetime import date, datetime, timezone

import pytest
from app.integrations.base import (
    IntegrationError,
    IntegrationProvider,
    ProviderNotFoundError,
)
from app.integrations.providers.test_provider import ProviderTeste
from app.integrations.registry import ProviderRegistry, default_registry
from app.integrations.service import IntegrationService
from app.schemas.integration import (
    IntegrationResult,
    MeetingIntegrationPayload,
    TaskIntegrationPayload,
)
from pydantic import ValidationError


def _sample_payload() -> MeetingIntegrationPayload:
    return MeetingIntegrationPayload(
        meeting_id=1,
        title="Reunião de Alinhamento",
        summary="A equipe discutiu prazos e metas.",
        objective="Definir entregas da sprint",
        key_points=["Backend 80% concluído"],
        decisions=["Usar Celery para async"],
        tasks=[
            TaskIntegrationPayload(
                id=10,
                description="Criar migrations",
                responsible="Dev1",
                deadline=date(2026, 10, 10),
            )
        ],
        created_at=datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc),
    )


class TestIntegrationSchemas:
    def test_valid_payload_instantiation(self):
        payload = _sample_payload()
        assert payload.meeting_id == 1
        assert payload.tasks[0].deadline == date(2026, 10, 10)

    def test_payload_validation_rejects_empty_fields(self):
        with pytest.raises(ValidationError):
            MeetingIntegrationPayload(meeting_id=0, title="", summary="")

    def test_integration_result_defaults(self):
        result = IntegrationResult(provider="teste", success=True)
        assert result.error is None
        assert result.metadata == {}
        assert isinstance(result.executed_at, datetime)


class TestProviderRegistry:
    def test_default_registry_has_test_provider(self):
        assert "teste" in default_registry.list_available()
        assert default_registry.get("  TeStE  ") is ProviderTeste

    def test_unknown_provider_raises_error(self):
        with pytest.raises(ProviderNotFoundError):
            default_registry.get("inexistente")
        assert issubclass(ProviderNotFoundError, IntegrationError)

    def test_custom_registry_registration_and_creation(self):
        registry = ProviderRegistry()

        @registry.register("dummy")
        class DummyProvider(IntegrationProvider):
            name = "dummy"

            def __init__(self, destination: str) -> None:
                self.destination = destination

            def send(self, payload: MeetingIntegrationPayload) -> IntegrationResult:
                return IntegrationResult(provider=self.name, success=True)

        assert isinstance(registry.create("dummy", destination="local"), DummyProvider)


class TestTestProvider:
    def test_sends_payload_without_external_request(self):
        stream = io.StringIO()
        provider = ProviderTeste(stream=stream)

        result = provider.send(_sample_payload())

        assert result.provider == "teste"
        assert result.success is True
        assert result.metadata == {"meeting_id": 1, "tasks_count": 1}
        assert "[INTEGRAÇÃO TESTE]" in stream.getvalue()
        assert provider.last_payload == _sample_payload()


class TestIntegrationService:
    def test_sends_payload_through_requested_provider(self):
        stream = io.StringIO()

        result = IntegrationService().send("teste", _sample_payload(), stream=stream)

        assert result.success is True
        assert result.provider == "teste"
        assert "Reunião de Alinhamento" in stream.getvalue()

    def test_returns_standard_result_for_unknown_provider(self):
        result = IntegrationService().send("unknown", _sample_payload())

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

        assert result.success is False
        assert result.error == "Não foi possível executar a integração."
        assert "secret-value" not in result.error
