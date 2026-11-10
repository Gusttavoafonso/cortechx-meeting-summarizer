"""Hash de senha (Argon2) e JWT de acesso."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import settings
from app.core.exceptions import InvalidSessionTokenError

_password_hash = PasswordHash((Argon2Hasher(),))


def hash_password(password: str) -> str:
    """Gera o hash Argon2 da senha (nunca armazenar a senha em texto)."""
    return _password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Confere a senha com o hash Argon2. Hash desconhecido/inválido => False."""
    try:
        return _password_hash.verify(plain_password, hashed_password)
    except (UnknownHashError, ValueError):
        return False


@lru_cache
def _dummy_hash() -> str:
    return hash_password("dummy-password-for-timing-equalization")


def verify_dummy_password(plain_password: str) -> None:
    """Gasta o mesmo custo de um verify real.

    Usado quando o usuário não existe, para que o tempo de resposta do login
    não revele se o e-mail está cadastrado.
    """
    verify_password(plain_password, _dummy_hash())


def create_access_token(user_id: int) -> str:
    """Gera o JWT de acesso, de curta duração (ACCESS_TOKEN_EXPIRE_MINUTES)."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> int:
    """Valida assinatura e expiração do JWT e devolve o id do usuário.

    Lança `InvalidSessionTokenError` se o token for inválido, adulterado,
    expirado ou sem `sub`.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        return int(payload["sub"])
    except jwt.ExpiredSignatureError as exc:
        raise InvalidSessionTokenError("Sessão expirada") from exc
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        raise InvalidSessionTokenError("Token inválido") from exc
