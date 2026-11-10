import pytest
from app.core.exceptions import UserAlreadyExistsError
from app.models.user import User
from app.repositories.user_repository import UserRepository
from sqlalchemy.orm import Session


def test_user_defaults_and_email_normalization(db_session: Session):
    repo = UserRepository(db_session)

    user = repo.create(
        User(email="  Fulano@Example.COM ", name="Fulano", hashed_password="h")
    )

    assert user.email == "fulano@example.com"
    assert user.is_active is True
    assert user.created_at is not None and user.updated_at is not None


def test_get_by_email_and_id_normalize_input(db_session: Session):
    repo = UserRepository(db_session)
    created = repo.create(User(email="a@b.com", name="A", hashed_password="h"))

    assert repo.get_by_email("  A@B.com ").id == created.id
    assert repo.get_by_id(created.id).email == "a@b.com"
    assert repo.get_by_email("x@y.com") is None
    assert repo.get_by_id(9999) is None


def test_create_duplicate_email_raises(db_session: Session):
    repo = UserRepository(db_session)
    repo.create(User(email="dup@b.com", name="A", hashed_password="h"))

    with pytest.raises(UserAlreadyExistsError):
        repo.create(User(email="DUP@b.com", name="B", hashed_password="h"))

    # a sessão continua utilizável após o rollback
    assert repo.get_by_email("dup@b.com") is not None
