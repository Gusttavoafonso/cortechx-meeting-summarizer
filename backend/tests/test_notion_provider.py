from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import httpx
import pytest
from app.integrations.providers import notion as notion_module
from app.integrations.providers.formatters.notion import NotionFormatter
from app.integrations.providers.notion import NotionProvider
from app.schemas.integration import (
    MeetingIntegrationPayload,
    TaskIntegrationPayload,
)
from notion_client.errors import APIResponseError


def sample_payload():
    return MeetingIntegrationPayload(
        meeting_id=123,
        title="Reunião de teste",
        summary="Resumo da reunião.",
        objective="Validar a integração.",
        key_points=["Ponto importante"],
        decisions=["Decisão aprovada"],
        tasks=[
            TaskIntegrationPayload(
                id=1,
                description="Criar documentação",
                responsible="Equipe",
                deadline=date(2026, 10, 20),
            )
        ],
        created_at=datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc),
    )


def make_provider(client):
    return NotionProvider(
        token="token-de-teste",
        database_id="database-de-teste",
        client=client,
    )


def test_missing_configuration_returns_failure():
    provider = NotionProvider(token="", database_id="")

    result = provider.send(sample_payload())

    assert result.success is False
    assert "não configurado" in result.error


def test_supports_api_key_keyword_argument():
    provider = NotionProvider(api_key="chave-via-api-key", database_id="db-123")
    assert provider.token == "chave-via-api-key"


def test_existing_meeting_is_not_created_twice():
    client = MagicMock()
    client.data_sources.query.return_value = {
        "results": [{"id": "page-123", "url": "https://notion.so/page-123"}]
    }
    client.blocks.children.list.return_value = {
        "results": [{}] * len(NotionFormatter().blocks(sample_payload())),
        "has_more": False,
    }
    provider = make_provider(client)

    result = provider.send(sample_payload())

    assert result.success is True
    assert result.metadata["already_exists"] is True
    assert result.metadata["page_id"] == "page-123"
    client.pages.create.assert_not_called()


def test_creates_page_with_meeting_content():
    client = MagicMock()
    client.data_sources.query.return_value = {"results": []}
    client.pages.create.return_value = {
        "id": "page-456",
        "url": "https://notion.so/page-456",
    }
    provider = make_provider(client)

    result = provider.send(sample_payload())

    assert result.success is True
    assert result.metadata["page_id"] == "page-456"
    client.pages.create.assert_called_once()

    call = client.pages.create.call_args.kwargs
    assert call["properties"]["meeting_id"]["number"] == 123
    assert call["properties"]["Status"]["select"]["name"] == "Pendente"

    blocks = call["children"]
    serialized_blocks = str(blocks)
    assert "Resumo da reunião." in serialized_blocks
    assert "Ponto importante" in serialized_blocks
    assert "Decisão aprovada" in serialized_blocks
    assert "Criar documentação" in serialized_blocks


def test_api_error_returns_safe_failure():
    client = MagicMock()
    client.data_sources.query.side_effect = RuntimeError("token=segredo")
    provider = make_provider(client)

    result = provider.send(sample_payload())

    assert result.success is False
    assert "segredo" not in result.error


def api_error(status, headers=None):
    return APIResponseError(
        code="error",
        status=status,
        message=f"erro {status}",
        headers=httpx.Headers(headers or {}),
        raw_body_text="{}",
    )


@pytest.fixture
def sleeps(monkeypatch):
    """Captura as esperas do retry sem segurar a suíte."""
    recorded = []
    monkeypatch.setattr(notion_module.time, "sleep", recorded.append)
    return recorded


def test_invalid_token_is_not_retried(sleeps):
    client = MagicMock()
    client.data_sources.query.side_effect = api_error(401)
    provider = make_provider(client)

    result = provider.send(sample_payload())

    assert result.success is False
    assert "Token do Notion inválido" in result.error
    assert client.data_sources.query.call_count == 1
    assert sleeps == []


def test_missing_database_is_not_retried(sleeps):
    client = MagicMock()
    client.data_sources.query.side_effect = api_error(404)
    provider = make_provider(client)

    result = provider.send(sample_payload())

    assert result.success is False
    assert "não encontrada" in result.error
    assert client.data_sources.query.call_count == 1
    assert sleeps == []


def test_rate_limit_is_retried_respecting_retry_after(sleeps):
    client = MagicMock()
    client.data_sources.query.side_effect = [
        api_error(429, {"Retry-After": "3"}),
        {"results": []},
    ]
    client.pages.create.return_value = {
        "id": "page-456",
        "url": "https://notion.so/page-456",
    }
    provider = make_provider(client)

    result = provider.send(sample_payload())

    assert result.success is True
    assert sleeps == [3.0]
    assert client.data_sources.query.call_count == 2


def test_timeout_is_retried_with_backoff(sleeps):
    client = MagicMock()
    client.data_sources.query.side_effect = [
        httpx.ReadTimeout("tempo esgotado"),
        {"results": []},
    ]
    client.pages.create.return_value = {
        "id": "page-456",
        "url": "https://notion.so/page-456",
    }
    provider = make_provider(client)

    result = provider.send(sample_payload())

    assert result.success is True
    assert sleeps == [1.0]


def test_network_failure_returns_safe_failure_after_retries(sleeps):
    client = MagicMock()
    client.data_sources.query.side_effect = httpx.ConnectError("sem rede")
    provider = make_provider(client)

    result = provider.send(sample_payload())

    assert result.success is False
    assert "Não foi possível publicar" in result.error
    # Uma tentativa inicial e mais duas do retry padrão.
    assert client.data_sources.query.call_count == 3
    assert sleeps == [1.0, 2.0]


def test_retry_does_not_duplicate_page(sleeps):
    client = MagicMock()
    client.data_sources.query.side_effect = [
        {"results": []},
        {"results": [{"id": "page-1", "url": "https://notion.so/page-1"}]},
    ]
    client.pages.create.side_effect = httpx.ReadTimeout("tempo esgotado")
    client.blocks.children.list.return_value = {
        "results": [],
        "has_more": False,
    }
    provider = make_provider(client)

    result = provider.send(sample_payload())

    assert result.success is True
    assert result.metadata["already_exists"] is True
    assert result.metadata["page_id"] == "page-1"
    client.pages.create.assert_called_once()


def test_partial_failure_completes_missing_blocks():
    payload = sample_payload()
    expected = NotionFormatter().blocks(payload)

    client = MagicMock()
    client.data_sources.query.return_value = {
        "results": [{"id": "page-1", "url": "https://notion.so/page-1"}]
    }
    client.blocks.children.list.return_value = {
        "results": [{}, {}],
        "has_more": False,
    }
    provider = make_provider(client)

    result = provider.send(payload)

    assert result.success is True
    assert result.metadata["blocks_completed"] is True
    client.pages.create.assert_not_called()

    appended = client.blocks.children.append.call_args.kwargs
    assert appended["children"] == expected[2:]


def test_complete_page_is_not_rewritten():
    payload = sample_payload()
    expected = NotionFormatter().blocks(payload)

    client = MagicMock()
    client.data_sources.query.return_value = {
        "results": [{"id": "page-1", "url": "https://notion.so/page-1"}]
    }
    client.blocks.children.list.return_value = {
        "results": [{}] * len(expected),
        "has_more": False,
    }
    provider = make_provider(client)

    result = provider.send(payload)

    assert result.metadata["blocks_completed"] is False
    client.blocks.children.append.assert_not_called()
