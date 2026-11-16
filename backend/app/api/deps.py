from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_session
from app.core.exceptions import InvalidSessionTokenError
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories.user_repository import UserRepository

# auto_error=False: a resposta 401 (com WWW-Authenticate) é montada abaixo, e o
# cookie HTTP-Only emitido pelo login Google continua aceito como alternativa.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request,
    bearer_token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_session),
) -> User:
    """Valida o JWT (Bearer ou cookie de sessão) e devolve o usuário ativo."""
    token = bearer_token or request.cookies.get(settings.session_cookie_name)
    if not token:
        raise _unauthorized("Não autenticado.")

    try:
        user_id = decode_access_token(token)
    except InvalidSessionTokenError as exc:
        raise _unauthorized(str(exc)) from exc

    user = UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Usuário não encontrado ou inativo.")

    return user
