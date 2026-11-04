from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_session
from app.core.exceptions import (
    GoogleAccountPasswordMissingError,
    InvalidCredentialsError,
)
from app.models.user import User
from app.schemas.user import PasswordChange, UserResponse, UserUpdate
from app.services.auth_service import change_password, update_user_name

router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Retorna os dados do usuário autenticado",
)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Edita o nome do usuário autenticado",
)
def update_current_user(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> User:
    return update_user_name(db, current_user, payload.name)


@router.put(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Troca a senha (exige a senha atual)",
)
def change_current_user_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> Response:
    try:
        change_password(
            db, current_user, payload.current_password, payload.new_password
        )
    except (InvalidCredentialsError, GoogleAccountPasswordMissingError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)