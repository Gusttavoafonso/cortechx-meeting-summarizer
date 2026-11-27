from __future__ import annotations

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyCookie, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_session
from app.core.exceptions import InvalidSessionTokenError
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories.user_repository import UserRepository


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


# Declarados como schemes para que apareçam no OpenAPI: sem isso o Swagger não
# mostra que as rotas exigem sessão nem oferece o botão "Authorize".
# auto_error=False porque a ausência dos dois é tratada aqui, com uma mensagem
# única.
session_cookie_scheme = APIKeyCookie(
    name=settings.session_cookie_name,
    auto_error=False,
    scheme_name="Cookie de sessão",
    description=(
        "Cookie HttpOnly emitido por /auth/login, /auth/register ou /auth/google."
    ),
)
bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="Bearer",
    description="Alternativa ao cookie, para o Swagger e clientes de API.",
)


def get_current_user(
    cookie_token: str | None = Security(session_cookie_scheme),
    bearer: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    db: Session = Depends(get_session),
) -> User:
    """Extrai e valida a sessão via Cookie HTTP-Only ou cabeçalho Authorization."""
    token = (bearer.credentials if bearer else None) or cookie_token

    if not token:
        raise _unauthorized("Não autenticado. Sessão ausente.")

    try:
        user_id = decode_access_token(token)
    except InvalidSessionTokenError as exc:
        raise _unauthorized(str(exc)) from exc

    user = UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Usuário não encontrado ou inativo.")

    return user
