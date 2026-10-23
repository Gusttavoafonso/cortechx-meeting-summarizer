"""Entrega das integrações (Discord, Notion) em segundo plano.

Roda depois que a reunião está COMPLETED e o resultado persistido, em sessão
de banco própria, sem manter nenhuma requisição HTTP aberta. Falhas externas
ficam registradas por provider (``integration_deliveries``) e nunca alteram o
estado principal da reunião.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.integrations.configuration import ProviderConfigurationResolver
from app.integrations.delivery import (
    MAX_AUTOMATIC_ATTEMPTS,
    DeliveryReport,
    IntegrationDeliveryService,
    MeetingNotDeliverableError,
    compute_retry_delay,
)

# Os providers se registram ao serem importados: sem estas linhas o worker
# não os conhece e toda entrega falha com "provider não encontrado".
from app.integrations.service import IntegrationService
from app.repositories.integration_delivery_repository import (
    IntegrationDeliveryRepository,
)
from app.repositories.meeting_repository import MeetingRepository
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def build_delivery_service(session: Session) -> IntegrationDeliveryService:
    """Monta o serviço de entrega com dependências reais ligadas à sessão."""
    resolver = ProviderConfigurationResolver(session)
    return IntegrationDeliveryService(
        meeting_repository=MeetingRepository(session),
        delivery_repository=IntegrationDeliveryRepository(session),
        integration_service=IntegrationService(configuration_resolver=resolver),
        configuration_resolver=resolver,
    )


def run_integration_delivery_job(
    meeting_id: int,
    *,
    providers: Sequence[str] | None = None,
    reset: bool = False,
    session_factory: Callable[[], Session] = SessionLocal,
    service_factory: Callable[[Session], IntegrationDeliveryService] = (
        build_delivery_service
    ),
) -> DeliveryReport | None:
    """Entrega o resultado persistido aos providers, com sessão isolada.

    ``reset=True`` marca um NOVO resultado (pipeline concluído de novo): as
    entregas voltam a ``pending`` para o resultado atual ser enviado. O reenvio
    manual usa ``reset=False`` e só repete o que ainda não deu sucesso.
    """
    session = session_factory()
    try:
        if reset:
            IntegrationDeliveryRepository(session).reset_for_new_result(meeting_id)
        report = service_factory(session).deliver(meeting_id, providers=providers)
        for outcome in report.outcomes:
            logger.info(
                "Integração %s da reunião %s: %s",
                outcome.provider,
                meeting_id,
                outcome.status,
            )
        return report
    except MeetingNotDeliverableError as exc:
        # Reunião removida ou fora de COMPLETED: não há o que entregar.
        logger.warning("Entrega ignorada para a reunião %s: %s", meeting_id, exc)
    finally:
        session.close()


@celery_app.task(
    bind=True, name="meetings.deliver_integrations", max_retries=MAX_AUTOMATIC_ATTEMPTS
)
def deliver_integrations_task(
    self,
    meeting_id: int,
    providers: list[str] | None = None,
    reset: bool = False,
) -> None:
    """Task Celery que delega a entrega para ``run_integration_delivery_job``."""
    report = run_integration_delivery_job(meeting_id, providers=providers, reset=reset)

    if report and report.retryable_providers:
        attempts = self.request.retries + 1
        delay = compute_retry_delay(attempts, report.retry_after)

        logger.info(
            "Agendando retry (tentativa %s) para reunião %s nos providers: %s. "
            "Aguardando %s segundos.",
            attempts,
            meeting_id,
            report.retryable_providers,
            delay,
        )
        raise self.retry(countdown=delay)


def enqueue_integration_delivery(
    meeting_id: int,
    *,
    providers: Sequence[str] | None = None,
    reset: bool = False,
    background_tasks: BackgroundTasks | None = None,
) -> None:
    """Publica a entrega no Celery, com fallback se o broker estiver fora."""
    provider_list = list(providers) if providers is not None else None
    try:
        deliver_integrations_task.delay(meeting_id, provider_list, reset)
    except Exception as exc:
        if background_tasks is not None:
            logger.warning(
                "Broker Celery indisponível (%s). Entrega da reunião %s via "
                "BackgroundTasks.",
                exc,
                meeting_id,
            )
            background_tasks.add_task(
                run_integration_delivery_job,
                meeting_id,
                providers=provider_list,
                reset=reset,
            )
            return
        # Sem BackgroundTasks, já estamos dentro de um job em segundo plano:
        # executa a entrega aqui mesmo para não perdê-la.
        logger.warning(
            "Broker Celery indisponível (%s). Entrega da reunião %s executada "
            "no próprio job.",
            exc,
            meeting_id,
        )
        run_integration_delivery_job(meeting_id, providers=provider_list, reset=reset)
