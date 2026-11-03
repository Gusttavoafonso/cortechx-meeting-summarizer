from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse

router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Retorna os dados do usuário autenticado",
)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user
