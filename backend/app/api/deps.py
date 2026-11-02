from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_session
from app.core.exceptions import InvalidSessionTokenError
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import verify_session_token


def get_current_user(
    request: Request,
    db: Session = Depends(get_session),
) -> User:
    """Extrai e valida a sessão via Cookie HTTP-Only ou cabeçalho Authorization."""
    token = request.cookies.get(settings.session_cookie_name)

    if not token:
        # Fallback para cabeçalho Authorization Bearer (testes e Swagger)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer ") :].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado. Sessão ausente.",
        )

    try:
        user_id = verify_session_token(token)
    except InvalidSessionTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    user = UserRepository(db).get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado.",
        )

    return user
