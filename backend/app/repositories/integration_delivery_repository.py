from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.integration_delivery import (
    IntegrationDelivery,
    IntegrationDeliveryStatus,
)


DEFAULT_STALE_AFTER = timedelta(minutes=15)

MAX_ERROR_LENGTH = 2000

_PENDING = IntegrationDeliveryStatus.PENDING.value
_RUNNING = IntegrationDeliveryStatus.RUNNING.value
_SUCCESS = IntegrationDeliveryStatus.SUCCESS.value
_FAILED = IntegrationDeliveryStatus.FAILED.value


class IntegrationDeliveryRepository:

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_meeting(self, meeting_id: int) -> list[IntegrationDelivery]:
        stmt = (
            select(IntegrationDelivery)
            .where(IntegrationDelivery.meeting_id == meeting_id)
            .order_by(IntegrationDelivery.provider)
        )
        return list(self.db.scalars(stmt).all())

    def get(self, meeting_id: int, provider: str) -> IntegrationDelivery | None:
        stmt = select(IntegrationDelivery).where(
            IntegrationDelivery.meeting_id == meeting_id,
            IntegrationDelivery.provider == provider,
        )
        return self.db.scalars(stmt).first()

    def get_or_create(self, meeting_id: int, provider: str) -> IntegrationDelivery:
        existing = self.get(meeting_id, provider)
        if existing is not None:
            return existing

        delivery = IntegrationDelivery(
            meeting_id=meeting_id,
            provider=provider,
            status=_PENDING,
            attempts=0,
        )
        self.db.add(delivery)
        try:
            self.db.commit()
        except IntegrityError:
            # Outra execução criou a linha entre o SELECT e o INSERT.
            self.db.rollback()
            existing = self.get(meeting_id, provider)
            if existing is None:
                raise
            return existing
        except SQLAlchemyError:
            self.db.rollback()
            raise

        self.db.refresh(delivery)
        return delivery

    def try_claim(
        self,
        meeting_id: int,
        provider: str,
        *,
        stale_after: timedelta = DEFAULT_STALE_AFTER,
    ) -> bool:
    
        now = datetime.now(timezone.utc)
        claimable = or_(
            IntegrationDelivery.status.in_([_PENDING, _FAILED]),
            and_(
                IntegrationDelivery.status == _RUNNING,
                IntegrationDelivery.executed_at < now - stale_after,
            ),
        )
        stmt = (
            update(IntegrationDelivery)
            .where(
                IntegrationDelivery.meeting_id == meeting_id,
                IntegrationDelivery.provider == provider,
                claimable,
            )
            .values(
                status=_RUNNING,
                attempts=IntegrationDelivery.attempts + 1,
                executed_at=now,
                error_message=None,
                updated_at=now,
            )
        )
        return self._execute(stmt)

    def mark_success(
        self,
        meeting_id: int,
        provider: str,
        *,
        external_id: str | None = None,
    ) -> bool:
        values: dict[str, Any] = {
            "status": _SUCCESS,
            "error_message": None,
            "updated_at": datetime.now(timezone.utc),
        }
        if external_id is not None:
            values["external_id"] = external_id[:255]
        return self._finish(meeting_id, provider, values)

    def mark_failed(
        self,
        meeting_id: int,
        provider: str,
        error_message: str | None,
    ) -> bool:
        message = (error_message or "Falha não especificada")[:MAX_ERROR_LENGTH]
        return self._finish(
            meeting_id,
            provider,
            {
                "status": _FAILED,
                "error_message": message,
                "updated_at": datetime.now(timezone.utc),
            },
        )

    def _finish(
        self, meeting_id: int, provider: str, values: dict[str, Any]
    ) -> bool:
        """Finaliza somente uma tentativa que esta execução reservou (RUNNING)."""
        stmt = (
            update(IntegrationDelivery)
            .where(
                IntegrationDelivery.meeting_id == meeting_id,
                IntegrationDelivery.provider == provider,
                IntegrationDelivery.status == _RUNNING,
            )
            .values(**values)
        )
        return self._execute(stmt)

    def reset_for_new_result(self, meeting_id: int) -> int:
        """Prepara a reunião para entregar um NOVO resultado (reprocessamento).

        Volta as linhas para ``pending`` e zera as tentativas, preservando o
        ``external_id`` (permite atualizar em vez de duplicar no destino).
        Não toca em tentativas em andamento. Retorna quantas linhas mudaram.
        """
        stmt = (
            update(IntegrationDelivery)
            .where(
                IntegrationDelivery.meeting_id == meeting_id,
                IntegrationDelivery.status != _RUNNING,
            )
            .values(
                status=_PENDING,
                attempts=0,
                error_message=None,
                updated_at=datetime.now(timezone.utc),
            )
        )
        return self._run(stmt)

    def _execute(self, stmt) -> bool:
        return self._run(stmt) > 0

    def _run(self, stmt) -> int:
        try:
            # synchronize_session=False: o commit logo abaixo expira os objetos
            # da sessão, e evita comparar datetimes naive (SQLite) com aware.
            result = self.db.execute(stmt.execution_options(synchronize_session=False))
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return int(result.rowcount or 0)
