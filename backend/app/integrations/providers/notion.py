from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar
from uuid import UUID

import httpx
from notion_client import Client
from notion_client.errors import APIResponseError
from pydantic import SecretStr

from app.core.config import settings
from app.integrations.base import IntegrationProvider
from app.integrations.providers.formatters.notion import NotionFormatter
from app.integrations.registry import register_provider
from app.schemas.integration import IntegrationResult, MeetingIntegrationPayload

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10.0
DEFAULT_MAX_RETRIES = 2

# O Notion aceita até 100 blocos por requisição.
NOTION_BLOCK_LIMIT = 100

RETRY_BASE_DELAY = 1.0
RETRY_MAX_DELAY = 8.0

# Falhas temporárias. Erros de configuração (400, 401, 403, 404) ficam de fora:
# repetir não muda o resultado e só gasta requisição.
RETRYABLE_STATUS = frozenset({409, 429, 500, 502, 503, 504})

T = TypeVar("T")


def _plain_text(value: str | None) -> str:
    """Normaliza textos opcionais sem expor credenciais."""
    return (value or "").strip()


def _normalize_database_id(value: str) -> str:
    """Normaliza IDs válidos do Notion para o formato UUID."""
    try:
        return str(UUID(value.strip()))
    except (ValueError, AttributeError):
        return value.strip()


@register_provider("notion")
class NotionProvider(IntegrationProvider):
    """Publica resultados de reuniões em uma database do Notion."""

    name = "notion"

    def __init__(
        self,
        token: str | SecretStr | None = None,
        database_id: str | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        client: Any | None = None,
        formatter: NotionFormatter | None = None,
        **kwargs: Any,
    ) -> None:
        candidate_token = (
            token
            if token is not None
            else (kwargs.get("api_key") or kwargs.get("notion_api_key"))
        )
        raw_token = (
            settings.notion_token if candidate_token is None else candidate_token
        )

        if isinstance(raw_token, SecretStr):
            raw_token = raw_token.get_secret_value()

        raw_database_id = (
            settings.notion_database_id if database_id is None else database_id
        )

        self.token = _plain_text(raw_token)
        self.database_id = _normalize_database_id(_plain_text(raw_database_id))
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self._client = client
        self._formatter = formatter or NotionFormatter()

    def send(self, payload: MeetingIntegrationPayload) -> IntegrationResult:
        if not self.token or not self.database_id:
            return self._failure(
                payload.meeting_id,
                "Token ou database do Notion não configurado.",
            )

        try:
            client = self._get_client()

            page, already_exists, blocks_completed = self._with_retry(
                lambda: self._publish(client, payload),
                payload.meeting_id,
            )

            return IntegrationResult(
                provider=self.name,
                success=True,
                metadata={
                    "meeting_id": payload.meeting_id,
                    "page_id": page.get("id"),
                    "url": page.get("url"),
                    "already_exists": already_exists,
                    "blocks_completed": blocks_completed,
                },
            )

        except Exception as exc:
            logger.warning(
                "Falha ao publicar reunião %s no Notion (%s).",
                payload.meeting_id,
                type(exc).__name__,
            )

            return self._failure(
                payload.meeting_id,
                self._safe_error(exc),
            )

    def _get_client(self) -> Any:
        """Cria o cliente com o timeout aceito pelo SDK instalado."""
        if self._client is None:
            self._client = Client(
                auth=self.token,
                timeout_ms=int(self.timeout * 1000),
            )

        return self._client

    def _publish(
        self,
        client: Any,
        payload: MeetingIntegrationPayload,
    ) -> tuple[dict[str, Any], bool, bool]:
        """Cria a página ou completa uma publicação anterior incompleta.

        A busca por meeting_id roda a cada tentativa: se uma tentativa anterior
        criou a página antes de falhar, a seguinte encontra o registro em vez
        de criar um segundo.
        """
        blocks = self._formatter.blocks(payload)

        existing = self._find_existing_page(client, payload.meeting_id)

        if existing is not None:
            completed = self._complete_blocks(client, existing["id"], blocks)
            return existing, True, completed

        return self._create_page(client, payload, blocks), False, False

    def _find_existing_page(
        self,
        client: Any,
        meeting_id: int,
    ) -> dict[str, Any] | None:
        """Busca uma reunião existente pela propriedade meeting_id."""
        response = client.data_sources.query(
            data_source_id=self.database_id,
            filter={
                "property": "meeting_id",
                "number": {"equals": meeting_id},
            },
            page_size=1,
        )

        results = response.get("results", [])
        return results[0] if results else None

    def _create_page(
        self,
        client: Any,
        payload: MeetingIntegrationPayload,
        blocks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Cria a página e envia os blocos que não couberam na criação."""
        response = client.pages.create(
            parent={
                "type": "data_source_id",
                "data_source_id": self.database_id,
            },
            properties=self._formatter.properties(payload),
            children=blocks[:NOTION_BLOCK_LIMIT],
        )

        self._append_blocks(
            client,
            response["id"],
            blocks[NOTION_BLOCK_LIMIT:],
        )

        return response

    def _complete_blocks(
        self,
        client: Any,
        page_id: str,
        blocks: list[dict[str, Any]],
    ) -> bool:
        """Reenvia apenas os blocos que faltaram em uma publicação parcial."""
        written = self._count_children(client, page_id)
        missing = blocks[written:]

        if not missing:
            return False

        logger.info(
            "Completando %s blocos pendentes da página %s do Notion.",
            len(missing),
            page_id,
        )
        self._append_blocks(client, page_id, missing)
        return True

    @staticmethod
    def _append_blocks(
        client: Any,
        page_id: str,
        blocks: list[dict[str, Any]],
    ) -> None:
        for index in range(0, len(blocks), NOTION_BLOCK_LIMIT):
            client.blocks.children.append(
                block_id=page_id,
                children=blocks[index : index + NOTION_BLOCK_LIMIT],
            )

    @staticmethod
    def _count_children(client: Any, page_id: str) -> int:
        """Conta os blocos já gravados na página, percorrendo a paginação."""
        total = 0
        cursor: str | None = None

        while True:
            arguments: dict[str, Any] = {
                "block_id": page_id,
                "page_size": NOTION_BLOCK_LIMIT,
            }
            if cursor:
                arguments["start_cursor"] = cursor

            response = client.blocks.children.list(**arguments)
            total += len(response.get("results", []))

            # Só continua a paginação com um has_more explicitamente verdadeiro.
            if response.get("has_more") is not True:
                return total

            cursor = response.get("next_cursor")

    def _with_retry(
        self,
        operation: Callable[[], T],
        meeting_id: int,
    ) -> T:
        """Repete apenas falhas temporárias, relendo o estado a cada tentativa."""
        attempt = 0

        while True:
            try:
                return operation()
            except Exception as exc:
                if attempt >= self.max_retries or not self._is_retryable(exc):
                    raise

                delay = self._retry_delay(exc, attempt)
                attempt += 1

                logger.info(
                    "Tentativa %s/%s para a reunião %s no Notion em %.1fs (%s).",
                    attempt,
                    self.max_retries,
                    meeting_id,
                    delay,
                    type(exc).__name__,
                )
                time.sleep(delay)

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if isinstance(exc, APIResponseError):
            return getattr(exc, "status", None) in RETRYABLE_STATUS

        return isinstance(
            exc,
            (TimeoutError, httpx.TimeoutException, httpx.TransportError),
        )

    @classmethod
    def _retry_delay(cls, exc: Exception, attempt: int) -> float:
        """Respeita o Retry-After do Notion; sem ele, usa backoff exponencial."""
        retry_after = cls._retry_after(exc)

        if retry_after is not None:
            return min(retry_after, RETRY_MAX_DELAY)

        return min(RETRY_BASE_DELAY * (2**attempt), RETRY_MAX_DELAY)

    @staticmethod
    def _retry_after(exc: Exception) -> float | None:
        """Lê o Retry-After do erro, quando o Notion informa a espera."""
        # O SDK expõe os headers na própria exceção; outras versões usam
        # um objeto response.
        headers = getattr(exc, "headers", None)

        if headers is None:
            headers = getattr(getattr(exc, "response", None), "headers", None)

        if headers is None:
            return None

        try:
            value = headers.get("Retry-After") or headers.get("retry-after")
            return None if value is None else float(value)
        except (AttributeError, TypeError, ValueError):
            return None

    def _safe_error(self, exc: Exception) -> str:
        """Retorna mensagens seguras sem expor credenciais."""
        if isinstance(exc, APIResponseError):
            status = getattr(exc, "status", None)

            if status == 400:
                return (
                    "Dados inválidos enviados ao Notion. "
                    "Confira o ID da database e suas propriedades."
                )

            if status == 401:
                return "Token do Notion inválido ou sem autenticação."

            if status == 403:
                return "A integração não tem permissão para acessar a database."

            if status == 404:
                return "Database do Notion não encontrada ou não compartilhada."

            if status == 429:
                return "Limite de requisições do Notion excedido."

            return f"API do Notion retornou erro (HTTP {status})."

        if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
            return "Tempo limite excedido ao acessar o Notion."

        return "Não foi possível publicar a reunião no Notion."

    @staticmethod
    def _failure(
        meeting_id: int,
        message: str,
    ) -> IntegrationResult:
        return IntegrationResult(
            provider="notion",
            success=False,
            error=message,
            metadata={"meeting_id": meeting_id},
        )
