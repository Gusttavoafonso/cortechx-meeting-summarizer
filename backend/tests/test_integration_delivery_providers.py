"""Entrega com os providers REAIS (Discord e Notion), sem rede.

Valida que a camada de entrega reaproveita o que os providers já fazem:
retry com backoff e Retry-After, não repetir erro definitivo, mensagens de
erro seguras e deduplicação no Notion. HTTP e SDK são simulados.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import httpx
import pytest
from app.core.config import settings
from app.integrations.configuration import ProviderConfigurationResolver
from app.integrations.delivery import (
    OUTCOME_FAILED,
    OUTCOME_SUCCESS,
    IntegrationDeliveryService,
)
from app.integrations.payload import meeting_to_integration_payload
from app.integrations.providers import discord as discord_module
from app.integrations.providers import notion as notion_module
from app.integrations.providers.formatters.notion import NotionFormatter
from app.integrations.registry import default_registry
from app.integrations.service import IntegrationService
from app.models.meeting import Meeting
from app.models.meeting_status import MeetingStatus
from app.models.summary import Summary
from app.models.task import Task
from app.repositories.integration_delivery_repository import (
    IntegrationDeliveryRepository,
)
from pydantic import SecretStr
from sqlalchemy.orm import Session

WEBHOOK_TOKEN = "token-secreto-do-webhook"
WEBHOOK_URL = f"https://discord.com/api/webhooks/123456/{WEBHOOK_TOKEN}"
NOTION_DATABASE_ID = "11111111-1111-1111-1111-111111111111"


class _Meetings:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, meeting_id: int):
        return self.db.get(Meeting, meeting_id)


def _completed_meeting(db_session: Session) -> Meeting:
    meeting = Meeting(title="Planejamento", status=MeetingStatus.COMPLETED)
    db_session.add(meeting)
    db_session.flush()
    db_session.add(
        Summary(
            meeting_id=meeting.id,
            summary="A equipe definiu as prioridades.",
            key_points=["Priorizar autenticação"],
            decisions=["Liberar na sexta-feira"],
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


def _service(
    db_session: Session, *, enabled: tuple[str, ...]
) -> IntegrationDeliveryService:
    return IntegrationDeliveryService(
        meeting_repository=_Meetings(db_session),
        delivery_repository=IntegrationDeliveryRepository(db_session),
        integration_service=IntegrationService(
            default_registry, ProviderConfigurationResolver(db_session)
        ),
        enabled_providers=lambda: list(enabled),
    )


# --------------------------------------------------------------------------
# Discord
# --------------------------------------------------------------------------


def _install_discord(
    monkeypatch: pytest.MonkeyPatch, statuses: list[int]
) -> list[httpx.Request]:
    """Simula o webhook: devolve os status na ordem e 204 depois disso."""
    seen: list[httpx.Request] = []
    queue = list(statuses)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(queue.pop(0) if queue else 204)

    original_client = httpx.Client
    monkeypatch.setattr(
        discord_module.httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )
    monkeypatch.setattr(
        discord_module.DiscordProvider, "_sleep", lambda self, seconds: None
    )
    monkeypatch.setattr(settings, "discord_webhook_url", WEBHOOK_URL)
    return seen


def test_discord_transient_failure_is_retried_by_the_provider_itself(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    meeting = _completed_meeting(db_session)
    requests = _install_discord(monkeypatch, [503])

    report = _service(db_session, enabled=("discord",)).deliver(meeting.id)

    assert [o.status for o in report.outcomes] == [OUTCOME_SUCCESS]
    # 503 e depois 204, dentro de UMA tentativa de entrega
    assert len(requests) == 2
    delivery = IntegrationDeliveryRepository(db_session).get(meeting.id, "discord")
    assert delivery.status == "success"
    assert delivery.attempts == 1


def test_discord_definitive_error_is_not_retried_and_does_not_leak_the_token(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    meeting = _completed_meeting(db_session)
    requests = _install_discord(monkeypatch, [401])

    report = _service(db_session, enabled=("discord",)).deliver(meeting.id)

    assert [o.status for o in report.outcomes] == [OUTCOME_FAILED]
    assert len(requests) == 1
    delivery = IntegrationDeliveryRepository(db_session).get(meeting.id, "discord")
    assert delivery.status == "failed"
    assert delivery.error_message
    assert WEBHOOK_TOKEN not in delivery.error_message


def test_discord_rate_limit_exhausted_then_manual_resend_succeeds(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    meeting = _completed_meeting(db_session)
    requests = _install_discord(monkeypatch, [429, 429, 429])
    service = _service(db_session, enabled=("discord",))

    first = service.deliver(meeting.id)

    assert [o.status for o in first.outcomes] == [OUTCOME_FAILED]
    assert len(requests) == 3  # tentativa inicial + 2 retries do provider

    resend = service.deliver(meeting.id)  # a fila de status acabou: 204

    assert [o.status for o in resend.outcomes] == [OUTCOME_SUCCESS]
    delivery = IntegrationDeliveryRepository(db_session).get(meeting.id, "discord")
    assert delivery.status == "success"
    assert delivery.attempts == 2
    assert delivery.error_message is None


# --------------------------------------------------------------------------
# Notion
# --------------------------------------------------------------------------


class _FakeNotion:
    """Simula o SDK do Notion: criação, busca por meeting_id e blocos."""

    def __init__(
        self, existing_page: dict | None = None, written_blocks: int = 0
    ) -> None:
        self.created: list[dict] = []
        self.appended: list[dict] = []
        self._existing = existing_page
        self._written = written_blocks
        self.data_sources = SimpleNamespace(query=self._query)
        self.pages = SimpleNamespace(create=self._create)
        self.blocks = SimpleNamespace(
            children=SimpleNamespace(list=self._list, append=self._append)
        )

    def _query(self, **_kwargs) -> dict:
        return {"results": [self._existing] if self._existing else []}

    def _create(self, **kwargs) -> dict:
        self.created.append(kwargs)
        return {"id": "nova-pagina", "url": "https://notion.so/nova-pagina"}

    def _list(self, **_kwargs) -> dict:
        return {"results": [{}] * self._written, "has_more": False}

    def _append(self, **kwargs) -> None:
        self.appended.append(kwargs)


def _install_notion(monkeypatch: pytest.MonkeyPatch, client: _FakeNotion) -> None:
    monkeypatch.setattr(notion_module, "Client", lambda **_kwargs: client)
    monkeypatch.setattr(settings, "notion_token", SecretStr("secret_notion_token"))
    monkeypatch.setattr(settings, "notion_database_id", NOTION_DATABASE_ID)


def test_notion_creates_the_page_and_stores_its_id(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    meeting = _completed_meeting(db_session)
    notion = _FakeNotion()
    _install_notion(monkeypatch, notion)

    report = _service(db_session, enabled=("notion",)).deliver(meeting.id)

    assert [o.status for o in report.outcomes] == [OUTCOME_SUCCESS]
    assert len(notion.created) == 1
    delivery = IntegrationDeliveryRepository(db_session).get(meeting.id, "notion")
    assert delivery.external_id == "nova-pagina"


def test_notion_does_not_duplicate_an_existing_page(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    meeting = _completed_meeting(db_session)
    total_blocks = len(
        NotionFormatter().blocks(meeting_to_integration_payload(meeting))
    )
    notion = _FakeNotion(
        existing_page={"id": "pagina-existente", "url": "https://notion.so/x"},
        written_blocks=total_blocks,
    )
    _install_notion(monkeypatch, notion)

    report = _service(db_session, enabled=("notion",)).deliver(meeting.id)

    assert [o.status for o in report.outcomes] == [OUTCOME_SUCCESS]
    assert notion.created == []
    assert notion.appended == []
    delivery = IntegrationDeliveryRepository(db_session).get(meeting.id, "notion")
    assert delivery.external_id == "pagina-existente"


def test_missing_notion_credentials_are_recorded_without_calling_the_api(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    meeting = _completed_meeting(db_session)
    notion = _FakeNotion()
    monkeypatch.setattr(notion_module, "Client", lambda **_kwargs: notion)
    monkeypatch.setattr(settings, "notion_token", None)
    monkeypatch.setattr(settings, "notion_database_id", None)

    report = _service(db_session, enabled=("notion",)).deliver(meeting.id)

    assert [o.status for o in report.outcomes] == [OUTCOME_FAILED]
    assert notion.created == []
    delivery = IntegrationDeliveryRepository(db_session).get(meeting.id, "notion")
    assert "não configurado" in delivery.error_message


# --------------------------------------------------------------------------
# Isolamento entre providers reais
# --------------------------------------------------------------------------


def test_discord_failure_does_not_prevent_notion_delivery(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    meeting = _completed_meeting(db_session)
    _install_discord(monkeypatch, [403])
    notion = _FakeNotion()
    _install_notion(monkeypatch, notion)

    report = _service(db_session, enabled=("discord", "notion")).deliver(meeting.id)

    outcomes = {o.provider: o.status for o in report.outcomes}
    assert outcomes == {"discord": OUTCOME_FAILED, "notion": OUTCOME_SUCCESS}
    db_session.refresh(meeting)
    assert MeetingStatus(meeting.status) == MeetingStatus.COMPLETED


def test_deliver_integrations_task_retries_only_failed_providers_without_reset():
    from unittest.mock import patch

    from app.integrations.delivery import DeliveryReport, ProviderOutcome
    from app.workers.integration_job import deliver_integrations_task
    from celery.exceptions import Retry

    mock_report = DeliveryReport(
        meeting_id=42,
        outcomes=[
            ProviderOutcome(provider="discord", status="success"),
            ProviderOutcome(provider="notion", status="failed", retryable=True),
        ],
    )

    with (
        patch.object(
            deliver_integrations_task, "retry", side_effect=Retry()
        ) as mock_retry,
        patch(
            "app.workers.integration_job.run_integration_delivery_job",
            return_value=mock_report,
        ),
    ):
        with pytest.raises(Retry):
            deliver_integrations_task(42, providers=None, reset=True)

    mock_retry.assert_called_once()
    _, kwargs = mock_retry.call_args
    assert kwargs["kwargs"] == {"providers": ["notion"], "reset": False}
    assert kwargs["countdown"] > 0
