"""Helpers de autenticação real (JWT) para os testes.

    user = create_test_user(db_session)                    # usuário ativo
    token = make_token(user)                               # JWT válido
    client = TestClient(app, headers=auth_headers(user))   # cliente autenticado
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from itertools import count

import jwt
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from sqlalchemy.orm import Session

DEFAULT_PASSWORD = "senha-de-teste-123"

# Argon2 é lento de propósito (dezenas de ms por hash). Calculado uma única vez:
# a 1B migra ~139 chamadas e não pode pagar um hash por teste.
_DEFAULT_PASSWORD_HASH = hash_password(DEFAULT_PASSWORD)

_email_sequence = count(1)


def unique_email() -> str:
    """E-mail único e válido. Use @example.com: .test e .local são rejeitados."""
    return f"usuario{next(_email_sequence)}@example.com"


def create_test_user(
    db: Session,
    *,
    email: str | None = None,
    name: str = "Usuário de Teste",
    password: str | None = DEFAULT_PASSWORD,
    is_active: bool = True,
    google_id: str | None = None,
) -> User:
    """Cria o usuário direto pelo repository, sem passar pelo login.

    ``password=None`` cria uma conta sem senha (como as contas do login Google).
    """
    if password is None:
        hashed_password = None
    elif password == DEFAULT_PASSWORD:
        hashed_password = _DEFAULT_PASSWORD_HASH
    else:
        hashed_password = hash_password(password)
    user = User(
        email=email or unique_email(),
        name=name,
        hashed_password=hashed_password,
        is_active=is_active,
        google_id=google_id,
    )
    return UserRepository(db).create(user)


def make_token(user: User, *, expires_delta: timedelta | None = None) -> str:
    """JWT válido. ``expires_delta`` negativo gera um token já expirado."""
    if expires_delta is None:
        return create_access_token(user.id)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )


def tamper_token(token: str) -> str:
    """Mantém o payload e corrompe a assinatura (token adulterado)."""
    header, payload, signature = token.split(".")
    flipped = ("A" if signature[0] != "A" else "B") + signature[1:]
    return ".".join((header, payload, flipped))


def auth_headers(user_or_token: User | str) -> dict[str, str]:
    token = (
        user_or_token if isinstance(user_or_token, str) else make_token(user_or_token)
    )
    return {"Authorization": f"Bearer {token}"}