from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import HttpUrl, SecretStr

from app.core.config import settings
from app.integrations.base import IntegrationProvider
from app.integrations.providers.formatters.discord import DiscordFormatter
from app.integrations.registry import register_provider
from app.schemas.integration import IntegrationResult, MeetingIntegrationPayload

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10.0
DEFAULT_MAX_RETRIES = 2


def _mask_webhook_url(url: str | None) -> str:
    """Oculta o token sensível da URL do webhook para exibição segura em logs."""
    if not url:
        return "<não configurada>"
    try:
        parsed = urlparse(url)
        path_parts = parsed.path.rstrip("/").split("/")
        if len(path_parts) >= 2 and "webhooks" in path_parts:
            masked_path = "/".join(path_parts[:-1]) + "/***masked***"
            return f"{parsed.scheme}://{parsed.netloc}{masked_path}"
        return f"{parsed.scheme}://{parsed.netloc}/***masked***"
    except Exception:
        return "***masked***"


@register_provider("discord")
class DiscordProvider(IntegrationProvider):
    """Provedor de integração para publicação de reuniões no Discord via Webhook."""

    name = "discord"

    def __init__(
        self,
        webhook_url: str | SecretStr | HttpUrl | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        formatter: DiscordFormatter | None = None,
        client: httpx.Client | None = None,
        **kwargs: Any,
    ) -> None:
        raw_url = webhook_url or kwargs.get("url")
        if raw_url is None and settings.discord_webhook_url is not None:
            raw_url = settings.discord_webhook_url

        if isinstance(raw_url, SecretStr):
            self.webhook_url = raw_url.get_secret_value().strip() or None
        elif isinstance(raw_url, HttpUrl):
            self.webhook_url = str(raw_url).strip() or None
        elif isinstance(raw_url, str):
            self.webhook_url = raw_url.strip() or None
        else:
            self.webhook_url = None

        self.timeout = timeout
        self.max_retries = max_retries
        self.formatter = formatter or DiscordFormatter()
        self._client = client

    def send(self, payload: MeetingIntegrationPayload) -> IntegrationResult:
        """Formata e envia os blocos da reunião para o webhook do Discord."""
        if not self.webhook_url:
            return IntegrationResult(
                provider=self.name,
                success=False,
                error="URL do webhook do Discord não configurada.",
                metadata={"meeting_id": payload.meeting_id},
            )

        if not self._is_valid_url(self.webhook_url):
            return IntegrationResult(
                provider=self.name,
                success=False,
                error="URL do webhook do Discord inválida. Deve iniciar com http:// ou https://.",
                metadata={"meeting_id": payload.meeting_id},
            )

        messages = self.formatter.format(payload)
        if not messages:
            return IntegrationResult(
                provider=self.name,
                success=True,
                metadata={
                    "meeting_id": payload.meeting_id,
                    "chunks_sent": 0,
                    "total_chunks": 0,
                },
            )

        client = self._client or httpx.Client(timeout=self.timeout)
        should_close = self._client is None

        try:
            return self._send_chunks(client, messages, payload.meeting_id)
        finally:
            if should_close:
                client.close()

    def _send_chunks(
        self,
        client: httpx.Client,
        messages: list[str],
        meeting_id: int,
    ) -> IntegrationResult:
        total = len(messages)
        sent = 0

        for index, message in enumerate(messages, start=1):
            success, error_result = self._send_single_chunk_with_retry(
                client=client,
                chunk=message,
                meeting_id=meeting_id,
                chunk_index=index,
                total_chunks=total,
                sent_so_far=sent,
            )
            if not success:
                return error_result  # type: ignore[return-value]
            sent += 1

        return IntegrationResult(
            provider=self.name,
            success=True,
            metadata={
                "meeting_id": meeting_id,
                "chunks_sent": sent,
                "total_chunks": total,
            },
        )

    def _send_single_chunk_with_retry(
        self,
        client: httpx.Client,
        chunk: str,
        meeting_id: int,
        chunk_index: int,
        total_chunks: int,
        sent_so_far: int,
    ) -> tuple[bool, IntegrationResult | None]:
        url = self.webhook_url
        assert url is not None

        attempt = 0
        while attempt <= self.max_retries:
            attempt += 1
            try:
                response = client.post(
                    url,
                    json={"content": chunk},
                    headers={"Content-Type": "application/json"},
                )

                if 200 <= response.status_code < 300:
                    return True, None

                # HTTP 429: Rate Limit
                if response.status_code == 429:
                    logger.warning(
                        "Rate limit (429) do Discord no chunk %d/%d (tentativa %d/%d)",
                        chunk_index,
                        total_chunks,
                        attempt,
                        self.max_retries + 1,
                    )
                    if attempt <= self.max_retries:
                        delay = self._extract_retry_after(response)
                        self._sleep(delay)
                        continue
                    return False, IntegrationResult(
                        provider=self.name,
                        success=False,
                        error=(
                            "Limite de requisições do Discord atingido "
                            "(rate limit 429)."
                        ),
                        metadata={
                            "meeting_id": meeting_id,
                            "chunks_sent": sent_so_far,
                            "total_chunks": total_chunks,
                            "status_code": 429,
                        },
                    )

                # HTTP 5xx: Erro no servidor do Discord (temporário)
                if response.status_code >= 500:
                    logger.warning(
                        "Erro 5xx do Discord (%d) na tentativa %d/%d",
                        response.status_code,
                        attempt,
                        self.max_retries + 1,
                    )
                    if attempt <= self.max_retries:
                        self._sleep(0.5 * attempt)
                        continue
                    return False, IntegrationResult(
                        provider=self.name,
                        success=False,
                        error=(
                            "Serviço do Discord temporariamente indisponível "
                            f"(HTTP {response.status_code})."
                        ),
                        metadata={
                            "meeting_id": meeting_id,
                            "chunks_sent": sent_so_far,
                            "total_chunks": total_chunks,
                            "status_code": response.status_code,
                        },
                    )

                # HTTP 4xx (exceto 429): erros do cliente não devem ser retentados
                error_desc = "Erro na requisição ao Discord"
                if response.status_code in (401, 403):
                    error_desc = "Webhook do Discord não autorizado ou token inválido"
                elif response.status_code == 404:
                    error_desc = "Webhook do Discord não encontrado"
                elif response.status_code == 400:
                    error_desc = "Payload rejeitado pelo Discord"

                return False, IntegrationResult(
                    provider=self.name,
                    success=False,
                    error=f"{error_desc} (HTTP {response.status_code}).",
                    metadata={
                        "meeting_id": meeting_id,
                        "chunks_sent": sent_so_far,
                        "total_chunks": total_chunks,
                        "status_code": response.status_code,
                    },
                )

            except httpx.TimeoutException:
                logger.warning(
                    "Timeout ao comunicar com Discord (%s) na tentativa %d/%d",
                    _mask_webhook_url(self.webhook_url),
                    attempt,
                    self.max_retries + 1,
                )
                if attempt <= self.max_retries:
                    self._sleep(0.5 * attempt)
                    continue
                return False, IntegrationResult(
                    provider=self.name,
                    success=False,
                    error="Tempo limite esgotado ao comunicar com o Discord (timeout).",
                    metadata={
                        "meeting_id": meeting_id,
                        "chunks_sent": sent_so_far,
                        "total_chunks": total_chunks,
                    },
                )

            except httpx.NetworkError:
                logger.warning(
                    "Erro de rede com Discord (%s) na tentativa %d/%d",
                    _mask_webhook_url(self.webhook_url),
                    attempt,
                    self.max_retries + 1,
                )
                if attempt <= self.max_retries:
                    self._sleep(0.5 * attempt)
                    continue
                return False, IntegrationResult(
                    provider=self.name,
                    success=False,
                    error="Falha de conexão com o servidor do Discord.",
                    metadata={
                        "meeting_id": meeting_id,
                        "chunks_sent": sent_so_far,
                        "total_chunks": total_chunks,
                    },
                )

            except Exception:
                logger.exception("Erro inesperado no DiscordProvider")
                return False, IntegrationResult(
                    provider=self.name,
                    success=False,
                    error="Falha inesperada ao enviar mensagem para o Discord.",
                    metadata={
                        "meeting_id": meeting_id,
                        "chunks_sent": sent_so_far,
                        "total_chunks": total_chunks,
                    },
                )

        return False, None

    def _sleep(self, seconds: float) -> None:
        """Pausa para retry, facilitando substituição/mock em testes."""
        time.sleep(seconds)

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

    @staticmethod
    def _extract_retry_after(response: httpx.Response) -> float:
        header_val = response.headers.get("Retry-After")
        if header_val:
            try:
                return min(max(float(header_val), 0.1), 10.0)
            except (ValueError, TypeError):
                pass
        try:
            data = response.json()
            if isinstance(data, dict) and "retry_after" in data:
                return min(max(float(data["retry_after"]), 0.1), 10.0)
        except Exception:
            pass
        return 1.0
