from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_session
from app.core.exceptions import (
    InvalidCredentialsError,
    InvalidGoogleTokenError,
    UserAlreadyExistsError,
)
from app.core.security import create_access_token
from app.schemas.user import (
    GoogleAuthRequest,
    Token,
    UserCreate,
    UserPublic,
    UserResponse,
)
from app.services.auth_service import (
    authenticate_with_credentials,
    get_or_create_google_user,
    register_user,
    verify_google_token,
)

router = APIRouter()


def _set_session_cookie(response: Response, user_id: int) -> None:
    """Configura o cookie HTTP-Only com o JWT de acesso (fluxo Google)."""
    response.set_cookie(
        key=settings.session_cookie_name,
        value=create_access_token(user_id),
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar nova conta com e-mail e senha",
)
def register(
    payload: UserCreate,
    db: Session = Depends(get_session),
) -> UserResponse:
    """Cria o usuário (senha com hash Argon2). Não inicia sessão."""
    try:
        user = register_user(
            db=db,
            email=payload.email,
            password=payload.password,
            name=payload.name,
        )
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=Token,
    summary="Entrar com e-mail e senha (OAuth2 password flow)",
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_session),
) -> Token:
    """O campo `username` do formulário OAuth2 recebe o e-mail."""
    try:
        user = authenticate_with_credentials(
            db=db,
            email=form_data.username,
            password=form_data.password,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return Token(access_token=create_access_token(user.id), token_type="bearer")


@router.post(
    "/google",
    response_model=UserPublic,
    summary="Autentica usuário com Google Identity Services (ID Token)",
)
def authenticate_with_google(
    payload: GoogleAuthRequest,
    response: Response,
    db: Session = Depends(get_session),
) -> UserPublic:
    """Valida ID Token do Google, atualiza usuário e emite Cookie HTTP-Only."""
    try:
        id_info = verify_google_token(payload.credential)
    except InvalidGoogleTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    google_sub = id_info.get("sub")
    email = id_info.get("email")
    name = id_info.get("name") or "Usuário Google"
    picture = id_info.get("picture")

    if not google_sub or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token do Google sem dados obrigatórios (sub ou email).",
        )

    user = get_or_create_google_user(
        db=db,
        google_sub=google_sub,
        email=email,
        name=name,
        picture_url=picture,
    )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado ou inativo.",
        )

    _set_session_cookie(response, user.id)
    return UserPublic.model_validate(user)


@router.post(
    "/logout",
    summary="Encerra a sessão do usuário removendo o cookie HTTP-Only",
)
def logout(response: Response) -> dict[str, str]:
    """Invalida a sessão local removendo o cookie session_token do navegador."""
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
    )
    return {"message": "Logout realizado com sucesso"}
