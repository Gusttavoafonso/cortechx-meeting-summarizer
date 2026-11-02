from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from google.auth.transport import requests
from google.oauth2 import id_token
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    GoogleAccountPasswordMissingError,
    InvalidCredentialsError,
    InvalidGoogleTokenError,
    InvalidSessionTokenError,
    UserAlreadyExistsError,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository


def hash_password(password: str) -> str:
    """Gera um hash seguro de senha utilizando bcrypt com salt aleatório."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto plano confere com o hash bcrypt."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def register_user(
    db: Session,
    email: str,
    password: str,
    name: str,
) -> User:
    """Cadastra um novo usuário com login tradicional por e-mail e senha."""
    user_repo = UserRepository(db)
    normalized_email = email.strip().lower()
    existing = user_repo.get_by_email(normalized_email)
    if existing:
        raise UserAlreadyExistsError(
            f"Já existe uma conta cadastrada com o e-mail '{email}'."
        )

    user = User(
        email=normalized_email,
        name=name.strip(),
        hashed_password=hash_password(password),
        google_id=None,
        picture_url=None,
    )
    return user_repo.create(user)


def authenticate_with_credentials(
    db: Session,
    email: str,
    password: str,
) -> User:
    """Valida as credenciais de login tradicional (e-mail e senha)."""
    user_repo = UserRepository(db)
    normalized_email = email.strip().lower()
    user = user_repo.get_by_email(normalized_email)
    if not user:
        raise InvalidCredentialsError("E-mail ou senha incorretos.")

    if not user.hashed_password:
        raise GoogleAccountPasswordMissingError(
            "Esta conta foi cadastrada via Google. Por favor, entre com o Google."
        )

    if not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("E-mail ou senha incorretos.")

    return user


def verify_google_token(credential: str) -> dict[str, Any]:
    """Valida o ID token emitido pelo Google Identity Services.

    Retorna o payload validado com claims (sub, email, name, picture).
    Lança `InvalidGoogleTokenError` se o token for inválido, adulterado, expirado
    ou se o e-mail não tiver sido verificado pelo Google.
    """
    try:
        request = requests.Request()
        audience = settings.google_client_id if settings.google_client_id else None
        id_info = id_token.verify_oauth2_token(credential, request, audience=audience)
        if not id_info.get("email_verified", False):
            raise InvalidGoogleTokenError(
                "O e-mail da conta Google não foi verificado pelo Google."
            )
        return id_info
    except InvalidGoogleTokenError:
        raise
    except Exception as exc:
        raise InvalidGoogleTokenError(f"Token do Google inválido: {str(exc)}") from exc


def create_session_token(user_id: int) -> str:
    """Gera um JWT de sessão interna da aplicação assinado criptograficamente."""
    now = datetime.now(timezone.utc)
    exp_time = now + timedelta(seconds=settings.session_max_age_seconds)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(exp_time.timestamp()),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def verify_session_token(token: str) -> int:
    """Decodifica e valida o JWT de sessão interna, retornando o user_id.

    Lança `InvalidSessionTokenError` se o token for inválido, malformado ou expirado.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise InvalidSessionTokenError(
                "Payload do token não contém o identificador do usuário"
            )
        return int(user_id_str)
    except jwt.ExpiredSignatureError as exc:
        raise InvalidSessionTokenError("Sessão expirada") from exc
    except (jwt.PyJWTError, ValueError) as exc:
        raise InvalidSessionTokenError(f"Token de sessão inválido: {str(exc)}") from exc


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
    normalized_email = email.strip().lower()

    if user:
        updated = False
        if user.name != name:
            user.name = name
            updated = True
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
