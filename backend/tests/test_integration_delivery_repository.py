from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.integration_delivery import (
    IntegrationDelivery,
    IntegrationDeliveryStatus,
)
from app.models.meeting import Meeting
from app.repositories.integration_delivery_repository import (
    IntegrationDeliveryRepository,
)
from sqlalchemy import update
from sqlalchemy.orm import Session


def _meeting(db_session: Session, title: str = "Reunião") -> Meeting:
    meeting = Meeting(title=title)
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)
    return meeting


def test_new_delivery_starts_pending_with_zero_attempts(db_session: Session) -> None:
    meeting = _meeting(db_session)
    repository = IntegrationDeliveryRepository(db_session)

    delivery = repository.get_or_create(meeting.id, "discord")

    assert delivery.status == IntegrationDeliveryStatus.PENDING.value
    assert delivery.attempts == 0
    assert delivery.executed_at is None
    assert delivery.error_message is None


def test_get_or_create_is_idempotent(db_session: Session) -> None:
    meeting = _meeting(db_session)
    repository = IntegrationDeliveryRepository(db_session)

    first = repository.get_or_create(meeting.id, "discord")
    second = repository.get_or_create(meeting.id, "discord")

    assert first.id == second.id
    assert len(repository.list_by_meeting(meeting.id)) == 1


def test_claim_reserves_delivery_and_counts_attempt(db_session: Session) -> None:
    meeting = _meeting(db_session)
    repository = IntegrationDeliveryRepository(db_session)
    repository.get_or_create(meeting.id, "notion")

    assert repository.try_claim(meeting.id, "notion") is True

    delivery = repository.get(meeting.id, "notion")
    assert delivery.status == IntegrationDeliveryStatus.RUNNING.value
    assert delivery.attempts == 1
    assert delivery.executed_at is not None
    # A segunda reserva falha: a primeira execução ainda a detém
    assert repository.try_claim(meeting.id, "notion") is False
    assert repository.get(meeting.id, "notion").attempts == 1


def test_successful_delivery_is_never_claimed_again(db_session: Session) -> None:
    meeting = _meeting(db_session)
    repository = IntegrationDeliveryRepository(db_session)
    repository.get_or_create(meeting.id, "discord")
    repository.try_claim(meeting.id, "discord")

    assert repository.mark_success(meeting.id, "discord", external_id="msg-1") is True

    delivery = repository.get(meeting.id, "discord")
    assert delivery.status == IntegrationDeliveryStatus.SUCCESS.value
    assert delivery.external_id == "msg-1"
    assert repository.try_claim(meeting.id, "discord") is False
    assert repository.get(meeting.id, "discord").attempts == 1


def test_failed_delivery_can_be_claimed_again(db_session: Session) -> None:
    meeting = _meeting(db_session)
    repository = IntegrationDeliveryRepository(db_session)
    repository.get_or_create(meeting.id, "discord")
    repository.try_claim(meeting.id, "discord")
    assert repository.mark_failed(meeting.id, "discord", "timeout") is True

    failed = repository.get(meeting.id, "discord")
    assert failed.status == IntegrationDeliveryStatus.FAILED.value
    assert failed.error_message == "timeout"

    assert repository.try_claim(meeting.id, "discord") is True

    retried = repository.get(meeting.id, "discord")
    assert retried.status == IntegrationDeliveryStatus.RUNNING.value
    assert retried.attempts == 2
    assert retried.error_message is None


def test_abandoned_running_delivery_can_be_reclaimed(db_session: Session) -> None:
    meeting = _meeting(db_session)
    repository = IntegrationDeliveryRepository(db_session)
    delivery = repository.get_or_create(meeting.id, "notion")
    repository.try_claim(meeting.id, "notion")

    # Simula um worker que morreu há uma hora no meio da tentativa
    db_session.execute(
        update(IntegrationDelivery)
        .where(IntegrationDelivery.id == delivery.id)
        .values(executed_at=datetime.now(timezone.utc) - timedelta(hours=1))
    )
    db_session.commit()

    assert repository.try_claim(meeting.id, "notion") is True
    assert repository.get(meeting.id, "notion").attempts == 2


def test_finish_only_applies_to_a_reserved_attempt(db_session: Session) -> None:
    meeting = _meeting(db_session)
    repository = IntegrationDeliveryRepository(db_session)
    repository.get_or_create(meeting.id, "discord")

    # Sem reserva (PENDING) não é possível marcar sucesso nem falha
    assert repository.mark_success(meeting.id, "discord") is False
    assert repository.mark_failed(meeting.id, "discord", "erro") is False
    assert (
        repository.get(meeting.id, "discord").status
        == IntegrationDeliveryStatus.PENDING.value
    )


def test_error_message_is_truncated(db_session: Session) -> None:
    meeting = _meeting(db_session)
    repository = IntegrationDeliveryRepository(db_session)
    repository.get_or_create(meeting.id, "discord")
    repository.try_claim(meeting.id, "discord")

    repository.mark_failed(meeting.id, "discord", "x" * 5000)

    assert len(repository.get(meeting.id, "discord").error_message) == 2000


def test_deliveries_are_scoped_per_meeting_and_ordered_by_provider(
    db_session: Session,
) -> None:
    first = _meeting(db_session, "Primeira")
    second = _meeting(db_session, "Segunda")
    repository = IntegrationDeliveryRepository(db_session)
    repository.get_or_create(first.id, "notion")
    repository.get_or_create(first.id, "discord")
    repository.get_or_create(second.id, "discord")

    providers = [d.provider for d in repository.list_by_meeting(first.id)]

    assert providers == ["discord", "notion"]
    assert len(repository.list_by_meeting(second.id)) == 1


def test_reset_for_new_result_returns_deliveries_to_pending(
    db_session: Session,
) -> None:
    meeting = _meeting(db_session)
    repository = IntegrationDeliveryRepository(db_session)
    repository.get_or_create(meeting.id, "discord")
    repository.try_claim(meeting.id, "discord")
    repository.mark_success(meeting.id, "discord", external_id="msg-1")
    repository.get_or_create(meeting.id, "notion")
    repository.try_claim(meeting.id, "notion")
    repository.mark_failed(meeting.id, "notion", "erro")

    changed = repository.reset_for_new_result(meeting.id)

    assert changed == 2
    discord = repository.get(meeting.id, "discord")
    assert discord.status == IntegrationDeliveryStatus.PENDING.value
    assert discord.attempts == 0
    assert discord.external_id == "msg-1"  # preservado para atualizar, não duplicar
    notion = repository.get(meeting.id, "notion")
    assert notion.status == IntegrationDeliveryStatus.PENDING.value
    assert notion.error_message is None


def test_reset_for_new_result_does_not_touch_running_attempts(
    db_session: Session,
) -> None:
    meeting = _meeting(db_session)
    repository = IntegrationDeliveryRepository(db_session)
    repository.get_or_create(meeting.id, "discord")
    repository.try_claim(meeting.id, "discord")

    assert repository.reset_for_new_result(meeting.id) == 0
    assert (
        repository.get(meeting.id, "discord").status
        == IntegrationDeliveryStatus.RUNNING.value
    )
