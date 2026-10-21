"""Rotas de integrações de uma reunião (consulta e reenvio manual).

Router próprio, incluído em ``main.py`` com o prefixo ``/meetings``. O reenvio
só agenda o job de entrega: reaproveita o resultado persistido e nunca executa
STT, diarização ou LLM de novo, nem mantém a requisição HTTP aberta.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.integrations.delivery import enabled_providers_from_settings
from app.models.integration_delivery import IntegrationDeliveryStatus
from app.models.meeting import Meeting
from app.models.meeting_status import MeetingStatus
from app.repositories.integration_delivery_repository import (
    IntegrationDeliveryRepository,
)
from app.repositories.meeting_repository import MeetingRepository
from app.schemas.integration_delivery_schema import (
    IntegrationDeliveryResponse,
    IntegrationRetryRequest,
    IntegrationRetryResponse,
    MeetingIntegrationsResponse,
)
from app.workers.integration_job import enqueue_integration_delivery

logger = logging.getLogger(__name__)

router = APIRouter()

_NOT_RETRYABLE = {
    IntegrationDeliveryStatus.SUCCESS.value,
    IntegrationDeliveryStatus.RUNNING.value,
}


def get_enabled_providers() -> list[str]:
    return enabled_providers_from_settings()


def get_integration_dispatcher() -> Callable[..., None]:
    return enqueue_integration_delivery


def _validate_meeting_id(meeting_id: int) -> None:
    if meeting_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O ID da reunião deve ser um número inteiro positivo.",
        )


def _get_meeting_or_404(db: Session, meeting_id: int) -> Meeting:
    meeting = MeetingRepository(db).get_by_id(meeting_id)
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reunião com ID {meeting_id} não encontrada.",
        )
    return meeting


@router.get(
    "/{meeting_id}/integrations",
    response_model=MeetingIntegrationsResponse,
    summary="Consultar o resultado das integrações da reunião",
)
def list_integrations(
    meeting_id: int,
    db: Session = Depends(get_session),
) -> MeetingIntegrationsResponse:
    _validate_meeting_id(meeting_id)
    _get_meeting_or_404(db, meeting_id)

    deliveries = IntegrationDeliveryRepository(db).list_by_meeting(meeting_id)
    return MeetingIntegrationsResponse(
        meeting_id=meeting_id,
        integrations=[
            IntegrationDeliveryResponse.model_validate(delivery)
            for delivery in deliveries
        ],
    )


@router.post(
    "/{meeting_id}/integrations/retry",
    response_model=IntegrationRetryResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Reenviar o resultado às integrações que ainda não foram entregues",
    description=(
        "Agenda a entrega em segundo plano usando o resultado já persistido. "
        "Providers já entregues ou em andamento são ignorados. Não repete "
        "transcrição, diarização nem LLM."
    ),
)
def retry_integrations(
    meeting_id: int,
    background_tasks: BackgroundTasks,
    payload: IntegrationRetryRequest | None = None,
    db: Session = Depends(get_session),
    enabled: list[str] = Depends(get_enabled_providers),
    dispatcher: Callable[..., None] = Depends(get_integration_dispatcher),
) -> IntegrationRetryResponse:
    _validate_meeting_id(meeting_id)
    meeting = _get_meeting_or_404(db, meeting_id)

    if MeetingStatus(meeting.status) != MeetingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"A reunião com ID {meeting_id} ainda não foi concluída; "
                "não há resultado para reenviar."
            ),
        )

    enabled_names = [name.strip().lower() for name in enabled]
    if payload is None or payload.providers is None:
        targets = enabled_names
    else:
        targets = list(dict.fromkeys(n.strip().lower() for n in payload.providers))
        not_enabled = [name for name in targets if name not in enabled_names]
        if not_enabled:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Integração não habilitada: {', '.join(not_enabled)}.",
            )

    current = {
        d.provider: d.status
        for d in IntegrationDeliveryRepository(db).list_by_meeting(meeting_id)
    }
    eligible = [name for name in targets if current.get(name) not in _NOT_RETRYABLE]
    if not eligible:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Nenhuma integração elegível para reenvio: todas já foram "
                "entregues, estão em andamento ou nenhuma está habilitada."
            ),
        )

    try:
        dispatcher(
            meeting_id,
            providers=eligible,
            reset=False,
            background_tasks=background_tasks,
        )
    except Exception:
        logger.exception("Falha ao agendar o reenvio da reunião %s", meeting_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível agendar o reenvio das integrações.",
        )

    return IntegrationRetryResponse(meeting_id=meeting_id, providers=eligible)
