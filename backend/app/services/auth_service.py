from __future__ import annotations

from typing import Any

from google.auth.transport import requests
from google.oauth2 import id_token
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    InvalidCredentialsError,
    InvalidGoogleTokenError,
    UserAlreadyExistsError,
    GoogleAccountPasswordMissingError,
)
from app.core.security import (
    hash_password,
    verify_dummy_password,
    verify_password,
)
from app.models.user import User, normalize_email
from app.repositories.user_repository import UserRepository

INVALID_CREDENTIALS_MESSAGE = "E-mail ou senha incorretos."


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
    if not verify_password(current_password, user.hashed_password):
        raise InvalidCredentialsError("Senha atual incorreta.")
    user.hashed_password = hash_password(new_password)
    UserRepository(db).update(user)
