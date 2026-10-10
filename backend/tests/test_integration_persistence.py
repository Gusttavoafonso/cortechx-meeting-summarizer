from datetime import date

import pytest
from app.integrations.base import IntegrationProvider
from app.integrations.configuration import ProviderConfigurationResolver
from app.integrations.payload import (
    MeetingResultUnavailableError,
    meeting_to_integration_payload,
)
from app.integrations.registry import ProviderRegistry
from app.integrations.service import IntegrationService
from app.models.integration_configuration import IntegrationConfiguration
from app.models.meeting import Meeting
from app.models.summary import Summary
from app.models.task import Task
from app.schemas.integration import IntegrationResult, MeetingIntegrationPayload


def _persisted_meeting(db_session) -> Meeting:
    meeting = Meeting(title="Planejamento da sprint")
    db_session.add(meeting)
    db_session.flush()
    db_session.add(
        Summary(
            meeting_id=meeting.id,
            summary="A equipe definiu prioridades e responsáveis.",
            key_points=["Priorizar autenticação"],
            decisions=["Liberar versão na sexta-feira"],
        )
    )
    db_session.add(
        Task(
            meeting_id=meeting.id,
            position=0,
            description="Implementar autenticação",
            responsible="Ana",
            deadline=date(2026, 10, 9),
        )
    )
    db_session.commit()
    db_session.refresh(meeting)
    return meeting


def test_converts_persisted_meeting_to_integration_payload(db_session):
    meeting = _persisted_meeting(db_session)

    payload = meeting_to_integration_payload(meeting)

    assert payload.meeting_id == meeting.id
    assert payload.summary == "A equipe definiu prioridades e responsáveis."
    assert payload.tasks[0].description == "Implementar autenticação"


def test_conversion_requires_persisted_summary(db_session):
    meeting = Meeting(title="Sem resumo")
    db_session.add(meeting)
    db_session.commit()

    with pytest.raises(MeetingResultUnavailableError):
        meeting_to_integration_payload(meeting)


def test_meeting_configuration_is_used_for_its_provider(db_session):
    meeting = _persisted_meeting(db_session)
    db_session.add(
        IntegrationConfiguration(
            meeting_id=meeting.id,
            platform="teste",
            configuration={"destination": "registro-local"},
        )
    )
    db_session.commit()

    configuration = ProviderConfigurationResolver(db_session).resolve(
        "teste", meeting_id=meeting.id
    )

    assert configuration == {"destination": "registro-local"}


def test_disabled_meeting_configuration_prevents_execution_without_mutation(
    db_session,
):
    meeting = _persisted_meeting(db_session)
    db_session.add(
        IntegrationConfiguration(
            meeting_id=meeting.id,
            platform="teste",
            enabled=False,
        )
    )
    db_session.commit()
    registry = ProviderRegistry()

    @registry.register("teste")
    class DisabledTestProvider(IntegrationProvider):
        name = "teste"

        def send(self, payload: MeetingIntegrationPayload) -> IntegrationResult:
            raise AssertionError("Provider desativado não deve executar")

    service = IntegrationService(registry, ProviderConfigurationResolver(db_session))

    result = service.send_persisted_meeting("teste", meeting)
    db_session.refresh(meeting)
    db_session.refresh(meeting.summary)

    assert result.success is False
    assert meeting.summary.summary == "A equipe definiu prioridades e responsáveis."
    assert meeting.tasks[0].description == "Implementar autenticação"
