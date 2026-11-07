from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models.meeting import Meeting
from app.models.meeting_status import MeetingStatus
from app.models.transcript import Transcript


class MeetingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _with_relations(self, statement):
        """Aplica o carregamento ansioso usado por todas as leituras de reuniao."""
        return statement.options(
            selectinload(Meeting.audio),
            selectinload(Meeting.transcript).selectinload(Transcript.segments),
        )

    def get_by_id(self, meeting_id: int, user_id: int) -> Meeting | None:
        """Busca a reuniao pertencente ao usuario informado.

        Reuniao de outro dono, ou sem dono (criada antes do controle de posse),
        nao e encontrada: a API responde 404 e nao revela que ela existe.
        """
        statement = self._with_relations(
            select(Meeting).where(
                Meeting.id == meeting_id,
                Meeting.user_id == user_id,
            )
        )
        return self.db.scalars(statement).first()

    def list_all(self, user_id: int) -> list[Meeting]:
        """Lista somente as reunioes do usuario informado."""
        statement = self._with_relations(
            select(Meeting).where(Meeting.user_id == user_id)
        ).order_by(Meeting.created_at.desc())
        return list(self.db.scalars(statement).all())

    def get_for_pipeline(self, meeting_id: int) -> Meeting | None:
        """Busca a reuniao sem filtro de posse.

        Uso exclusivo do pipeline interno (worker Celery, entrega das
        integracoes e transicoes de estado), que recebe apenas o ``meeting_id``
        porque a API ja validou a posse antes de enfileirar o job. Nenhuma rota
        HTTP deve chamar este metodo.
        """
        statement = self._with_relations(
            select(Meeting).where(Meeting.id == meeting_id)
        )
        return self.db.scalars(statement).first()

    def create(
        self,
        meeting_or_title: Meeting | str | None = None,
        *,
        meeting: Meeting | None = None,
        title: str | None = None,
        status: str | MeetingStatus = MeetingStatus.RECEIVED,
        user_id: int | None = None,
    ) -> Meeting:
        if isinstance(meeting_or_title, Meeting):
            target = meeting_or_title
        elif isinstance(meeting_or_title, str):
            target = Meeting(title=meeting_or_title, status=status)
        elif meeting is not None:
            target = meeting
        elif title is not None:
            target = Meeting(title=title, status=status)
        else:
            raise ValueError("Either a Meeting instance or title must be provided.")

        if user_id is not None and target.user_id is None:
            target.user_id = user_id

        self.db.add(target)
        self.db.commit()
        self.db.refresh(target)
        return target

    def update_status(
        self,
        meeting: Meeting,
        status: str | MeetingStatus,
        *,
        commit: bool = True,
    ) -> Meeting:
        meeting.status = status
        self.db.add(meeting)
        try:
            if commit:
                self.db.commit()
                self.db.refresh(meeting)
            else:
                self.db.flush()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return meeting

    def try_claim_processing(self, meeting_id: int) -> bool:
        """Adquire atomicamente o lock de processamento via UPDATE condicional."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(Meeting)
            .where(
                Meeting.id == meeting_id,
                Meeting.status.notin_(
                    [MeetingStatus.PROCESSING, MeetingStatus.TRANSCRIBING]
                ),
            )
            .values(
                status=MeetingStatus.PROCESSING,
                processing_started_at=now,
                processing_completed_at=None,
                last_error=None,
                updated_at=now,
            )
        )
        try:
            result = self.db.execute(stmt)
            self.db.commit()
            return bool(result.rowcount and result.rowcount > 0)
        except SQLAlchemyError:
            self.db.rollback()
            raise
