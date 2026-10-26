"""Entrega persistida e idempotente do resultado de uma reunião aos providers.

Responsabilidades (e só estas):
- decidir quais providers executar (flags globais + desativação por reunião);
- reservar, executar e registrar cada entrega de forma isolada;
- devolver um relatório que a camada de job usa para decidir o retry.

Não conhece Discord nem Notion, não altera o ``MeetingStatus`` e não executa
retries por conta própria: o retry fica a cargo de quem chama (task Celery).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.exceptions import DefinitiveError
from app.integrations.configuration import (
    ProviderConfigurationError,
    ProviderDisabledError,
)
from app.models.integration_delivery import IntegrationDeliveryStatus
from app.models.meeting_status import MeetingStatus
from app.repositories.integration_delivery_repository import (
    IntegrationDeliveryRepository,
)
from app.schemas.integration import IntegrationResult

logger = logging.getLogger(__name__)

# Política de retry automático (reenvio manual não tem limite de tentativas).
MAX_AUTOMATIC_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 2.0
RETRY_MAX_DELAY_SECONDS = 300.0

OUTCOME_SUCCESS = "success"
OUTCOME_FAILED = "failed"
# Já entregue anteriormente, ou desativado para esta reunião.
OUTCOME_SKIPPED = "skipped"
# Outra execução detém a reserva desta entrega.
OUTCOME_IN_PROGRESS = "in_progress"

DISABLED_MESSAGE = "Provider desativado para esta reunião."
GENERIC_ERROR_MESSAGE = "Não foi possível executar a integração."


class MeetingReader(Protocol):
    def get_by_id(self, meeting_id: int) -> Any | None: ...


class ProviderSender(Protocol):
    def send_persisted_meeting(
        self, provider: str, meeting: Any, **provider_config: Any
    ) -> IntegrationResult: ...


class ConfigurationResolver(Protocol):
    def resolve(
        self,
        provider: str,
        *,
        meeting_id: int | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


class MeetingNotDeliverableError(DefinitiveError, ValueError):
    """A reunião não existe ou ainda não está COMPLETED (resultado persistido)."""


class DeliveryMeetingNotFoundError(MeetingNotDeliverableError):
    """A reunião informada não existe (a rota deve responder 404, não 409)."""


@dataclass(frozen=True)
class ProviderOutcome:
    provider: str
    status: str
    error: str | None = None
    # Falha transitória (timeout, 429, 5xx): elegível ao retry automático.
    retryable: bool = False
    # Espera sugerida pelo provider (Retry-After), em segundos.
    retry_after: float | None = None


@dataclass(frozen=True)
class DeliveryReport:
    meeting_id: int
    outcomes: tuple[ProviderOutcome, ...] = ()

    @property
    def retryable_providers(self) -> list[str]:
        """Providers que falharam de forma transitória (o retry automático só
        deve repetir estes; erros definitivos não são repetidos)."""
        return [
            o.provider
            for o in self.outcomes
            if o.status == OUTCOME_FAILED and o.retryable
        ]

    @property
    def retry_after(self) -> float | None:
        values = [
            o.retry_after
            for o in self.outcomes
            if o.status == OUTCOME_FAILED and o.retryable and o.retry_after
        ]
        return max(values) if values else None


def enabled_providers_from_settings(settings: Any | None = None) -> list[str]:
    """Providers habilitados pelas flags globais de integração."""
    if settings is None:
        from app.core.config import get_settings

        settings = get_settings()

    providers: list[str] = []
    if getattr(settings, "discord_enabled", False):
        providers.append("discord")
    if getattr(settings, "notion_enabled", False):
        providers.append("notion")
    if getattr(settings, "obsidian_enabled", False):
        providers.append("obsidian")
    return providers


def compute_retry_delay(attempt: int, retry_after: float | None = None) -> float:
    """Backoff exponencial limitado, respeitando o Retry-After (também limitado).

    ``attempt`` é o número (a partir de 1) da tentativa que acabou de falhar.
    """
    backoff = min(
        RETRY_BASE_DELAY_SECONDS * (2 ** max(attempt - 1, 0)),
        RETRY_MAX_DELAY_SECONDS,
    )
    if retry_after is None:
        return backoff
    return max(backoff, min(float(retry_after), RETRY_MAX_DELAY_SECONDS))


class IntegrationDeliveryService:
    def __init__(
        self,
        meeting_repository: MeetingReader,
        delivery_repository: IntegrationDeliveryRepository,
        integration_service: ProviderSender,
        *,
        configuration_resolver: ConfigurationResolver | None = None,
        enabled_providers: Callable[[], Sequence[str]] | None = None,
    ) -> None:
        self._meetings = meeting_repository
        self._deliveries = delivery_repository
        self._integration_service = integration_service
        self._configuration_resolver = configuration_resolver
        self._enabled_providers = enabled_providers or enabled_providers_from_settings

    def deliver(
        self,
        meeting_id: int,
        *,
        providers: Sequence[str] | None = None,
    ) -> DeliveryReport:
        """Entrega o resultado persistido aos providers que ainda não o receberam.

        Sem ``providers``, considera todos os habilitados. Providers que não
        estão habilitados são ignorados. Entregas já bem-sucedidas nunca são
        repetidas, e uma falha em um provider não impede os demais.
        """
        meeting = self._meetings.get_by_id(meeting_id)
        if meeting is None:
            raise DeliveryMeetingNotFoundError(f"Reunião {meeting_id} não encontrada.")

        current = MeetingStatus(meeting.status)
        if current != MeetingStatus.COMPLETED:
            raise MeetingNotDeliverableError(
                f"A reunião {meeting_id} ainda não foi concluída "
                f"(estado atual: {current.value})."
            )

        enabled = [name.strip().lower() for name in self._enabled_providers()]
        requested = enabled if providers is None else list(providers)
        wanted = [name.strip().lower() for name in requested]
        targets = [name for name in dict.fromkeys(wanted) if name in enabled]

        outcomes = [self._deliver_one(meeting_id, meeting, name) for name in targets]
        return DeliveryReport(meeting_id=meeting_id, outcomes=tuple(outcomes))

    def _deliver_one(
        self, meeting_id: int, meeting: Any, provider: str
    ) -> ProviderOutcome:
        if self._is_disabled_for_meeting(provider, meeting_id):
            return ProviderOutcome(provider, OUTCOME_SKIPPED, error=DISABLED_MESSAGE)

        delivery = self._deliveries.get_or_create(meeting_id, provider)
        if delivery.status == IntegrationDeliveryStatus.SUCCESS.value:
            return ProviderOutcome(provider, OUTCOME_SKIPPED)

        if not self._deliveries.try_claim(meeting_id, provider):
            return ProviderOutcome(provider, OUTCOME_IN_PROGRESS)

        try:
            result = self._integration_service.send_persisted_meeting(provider, meeting)
        except Exception:
            logger.exception(
                "Falha inesperada na integração %s da reunião %s", provider, meeting_id
            )
            result = IntegrationResult(
                provider=provider, success=False, error=GENERIC_ERROR_MESSAGE
            )

        if result.success:
            self._deliveries.mark_success(
                meeting_id, provider, external_id=_external_id(result)
            )
            return ProviderOutcome(provider, OUTCOME_SUCCESS)

        self._deliveries.mark_failed(meeting_id, provider, result.error)
        return ProviderOutcome(
            provider,
            OUTCOME_FAILED,
            error=result.error,
            retryable=bool(result.metadata.get("retryable", False)),
            retry_after=_as_positive_float(result.metadata.get("retry_after")),
        )

    def _is_disabled_for_meeting(self, provider: str, meeting_id: int) -> bool:
        if self._configuration_resolver is None:
            return False
        try:
            self._configuration_resolver.resolve(provider, meeting_id=meeting_id)
        except ProviderDisabledError:
            return True
        except ProviderConfigurationError:
            # Configuração inválida é reportada pelo próprio envio.
            return False
        return False


def _external_id(result: IntegrationResult) -> str | None:
    # O NotionProvider informa "page_id"; "external_id" é o nome genérico.
    value = result.metadata.get("external_id") or result.metadata.get("page_id")
    return str(value) if value else None


def _as_positive_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None
