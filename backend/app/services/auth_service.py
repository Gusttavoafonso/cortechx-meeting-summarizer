from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from google.auth.transport import requests
from google.oauth2 import id_token
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    GoogleAccountPasswordMissingError,
    InvalidCredentialsError,
    InvalidGoogleTokenError,
    UserAlreadyExistsError,
)
from app.core.security import (
    hash_password,
    verify_dummy_password,
    verify_password,
)
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User, normalize_email
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)
INVALID_CREDENTIALS_MESSAGE = "E-mail ou senha incorretos."
PASSWORD_RESET_TTL_MINUTES = 15


def register_user(
    db: Session,
    email: str,
    password: str,
    name: str,
) -> User:
    """Cadastra um novo usuário com login tradicional por e-mail e senha."""
    user_repo = UserRepository(db)
    normalized_email = normalize_email(email)
    if user_repo.get_by_email(normalized_email):
        raise UserAlreadyExistsError(
            "Já existe uma conta cadastrada com este e-mail."
        )

    user = User(
        email=normalized_email,
        name=name.strip(),
        hashed_password=hash_password(password),
    )
    return user_repo.create(user)


def authenticate_with_credentials(
    db: Session,
    email: str,
    password: str,
) -> User:
    """Valida as credenciais de login tradicional (e-mail e senha).

    Todas as falhas (e-mail inexistente, senha errada, conta sem senha ou conta
    inativa) lançam a mesma `InvalidCredentialsError`, para não revelar se o
    e-mail existe.
    """
    if len(password) > 128:
        raise InvalidCredentialsError(INVALID_CREDENTIALS_MESSAGE)

    user = UserRepository(db).get_by_email(email)

    if user is None or not user.hashed_password:
        verify_dummy_password(password)
        raise InvalidCredentialsError(INVALID_CREDENTIALS_MESSAGE)

    if not verify_password(password, user.hashed_password) or not user.is_active:
        raise InvalidCredentialsError(INVALID_CREDENTIALS_MESSAGE)

    return user


def verify_google_token(credential: str) -> dict[str, Any]:
    """Valida o ID token emitido pelo Google Identity Services.

    Retorna o payload validado com claims (sub, email, name, picture).
    Lança `InvalidGoogleTokenError` se o token for inválido, adulterado, expirado,
    se `GOOGLE_CLIENT_ID` não estiver configurado ou se o e-mail não tiver sido
    verificado pelo Google.
    """
    if not settings.google_client_id:
        raise InvalidGoogleTokenError(
            "Autenticação com Google não configurada no servidor."
        )

    try:
        request = requests.Request()
        id_info = id_token.verify_oauth2_token(
            credential,
            request,
            audience=settings.google_client_id,
            clock_skew_in_seconds=10,
        )
        if not id_info.get("email_verified", False):
            raise InvalidGoogleTokenError(
                "O e-mail da conta Google não foi verificado pelo Google."
            )
        return id_info
    except InvalidGoogleTokenError:
        raise
    except ValueError as exc:
        logger.warning(
            "Falha ao verificar ID token do Google (%s): %s",
            exc.__class__.__name__,
            exc,
        )
        raise InvalidGoogleTokenError("Token do Google inválido ou expirado.") from exc
    except Exception as exc:
        logger.warning(
            "Falha ao verificar ID token do Google (%s): %s",
            exc.__class__.__name__,
            exc,
        )
        raise InvalidGoogleTokenError("Token do Google inválido.") from exc


def get_or_create_google_user(
    db: Session,
    google_sub: str,
    email: str,
    name: str,
    picture_url: str | None = None,
) -> User:
    """Localiza ou cria o registro do usuário autenticado via Google no banco."""
    user_repo = UserRepository(db)
    user = user_repo.get_by_google_id(google_sub)
    normalized_email = normalize_email(email)

    if user:
        updated = False
        if user.picture_url != picture_url:
            user.picture_url = picture_url
            updated = True
        if user.email != normalized_email:
            user.email = normalized_email
            updated = True
        if updated:
            user_repo.update(user)
        return user

    user_by_email = user_repo.get_by_email(normalized_email)
    if user_by_email:
        user_by_email.google_id = google_sub
        user_by_email.name = name
        user_by_email.hashed_password = None
        if picture_url:
            user_by_email.picture_url = picture_url
        user_repo.update(user_by_email)
        return user_by_email

    new_user = User(
        google_id=google_sub,
        email=normalized_email,
        name=name,
        picture_url=picture_url,
    )
    return user_repo.create(new_user)


def update_user_name(db: Session, user: User, name: str) -> User:
    """Atualiza o nome do usuário autenticado."""
    user.name = name.strip()
    return UserRepository(db).update(user)


def change_password(
    db: Session,
    user: User,
    current_password: str,
    new_password: str,
) -> None:
    """Troca a senha, exigindo a senha atual.

    Contas sem senha (criadas pelo login Google) não têm o que conferir.
    """
    if not user.hashed_password:
        raise GoogleAccountPasswordMissingError(
            "Esta conta foi cadastrada via Google e não possui senha de acesso."
        )
    if len(current_password) > 128:
        raise InvalidCredentialsError("Senha atual incorreta.")
    if len(new_password) > 128:
        raise InvalidCredentialsError("A nova senha deve ter no máximo 128 caracteres.")
    if not verify_password(current_password, user.hashed_password):
        raise InvalidCredentialsError("Senha atual incorreta.")
    user.hashed_password = hash_password(new_password)
    UserRepository(db).update(user)


def _hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def request_password_reset(db: Session, email: str) -> tuple[str, str | None]:
    """Gera token temporário de redefinição de senha (15 min) sem enviar e-mail."""
    generic_message = (
        "Se houver uma conta com senha para este e-mail, um token de "
        "recuperação foi gerado."
    )
    user = UserRepository(db).get_by_email(email)
    if user is None or not user.is_active or not user.hashed_password:
        return generic_message, None

    now = datetime.now(timezone.utc)
    # Invalida tokens pendentes anteriores do mesmo usuário
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )

    raw_token = secrets.token_urlsafe(32)
    reset_entry = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_reset_token(raw_token),
        expires_at=now + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES),
    )
    db.add(reset_entry)
    db.commit()

    if settings.DEBUG:
        logger.info(
            "Token de recuperação de senha gerado em modo DEBUG para user_id=%s.",
            user.id,
        )
        return generic_message, raw_token

    logger.info("Token de recuperação de senha gerado para user_id=%s.", user.id)
    return generic_message, None


def reset_password_with_token(db: Session, token: str, new_password: str) -> None:
    """Valida token de recuperação e redefine a senha com Argon2."""
    if len(new_password) < 8 or len(new_password) > 128:
        raise InvalidCredentialsError(
            "A nova senha deve ter entre 8 e 128 caracteres."
        )

    token_hash = _hash_reset_token(token)
    entry = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash)
        .first()
    )
    if entry is None or entry.used_at is not None:
        raise InvalidCredentialsError("Token de recuperação inválido ou já utilizado.")

    now = datetime.now(timezone.utc)
    expires_at = (
        entry.expires_at
        if entry.expires_at.tzinfo is not None
        else entry.expires_at.replace(tzinfo=timezone.utc)
    )
    if expires_at <= now:
        raise InvalidCredentialsError("Token de recuperação expirado.")

    user = UserRepository(db).get_by_id(entry.user_id)
    if user is None or not user.is_active:
        raise InvalidCredentialsError("Token de recuperação inválido.")

    user.hashed_password = hash_password(new_password)
    entry.used_at = now
    db.add(user)
    db.add(entry)
    db.commit()
