from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import UserAlreadyExistsError
from app.models.user import User, normalize_email


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: int) -> User | None:
        stmt = select(User).where(User.id == user_id)
        return self.db.scalars(stmt).first()

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == normalize_email(email))
        return self.db.scalars(stmt).first()

    def get_by_google_id(self, google_id: str) -> User | None:
        stmt = select(User).where(User.google_id == google_id)
        return self.db.scalars(stmt).first()

    def create(self, user: User) -> User:
        user.email = normalize_email(user.email)
        self.db.add(user)
        try:
            self.db.commit()
        except IntegrityError as exc:
            # Corrida entre duas requisições com o mesmo e-mail (índice único).
            self.db.rollback()
            raise UserAlreadyExistsError(
                "Já existe uma conta cadastrada com este e-mail."
            ) from exc
        self.db.refresh(user)
        return user

    def update(self, user: User) -> User:
        self.db.commit()
        self.db.refresh(user)
        return user
