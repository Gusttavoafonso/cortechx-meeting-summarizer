from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_session
from app.core.exceptions import (
    GoogleAccountPasswordMissingError,
    InvalidCredentialsError,
    InvalidGoogleTokenError,
    UserAlreadyExistsError,
)
from app.models.user import User
from app.schemas.user import (
    GoogleAuthRequest,
    UserLoginRequest,
    UserPublic,
    UserRegisterRequest,
)
from app.services.auth_service import (
    authenticate_with_credentials,
    create_session_token,
    get_or_create_google_user,
    register_user,
    verify_google_token,
)

router = APIRouter()


def _set_session_cookie(response: Response, user_id: int) -> None:
    """Configura o cookie de sessão HTTP-Only assinado criptograficamente."""
    session_token = create_session_token(user_id)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar nova conta com e-mail e senha",
)
def register(
    payload: UserRegisterRequest,
    response: Response,
    db: Session = Depends(get_session),
) -> UserPublic:
    """Registra um usuário via login tradicional e inicia a sessão autenticada."""
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

    _set_session_cookie(response, user.id)
    return UserPublic.model_validate(user)


@router.post(
    "/login",
    response_model=UserPublic,
    summary="Entrar com e-mail e senha",
)
def login(
    payload: UserLoginRequest,
    response: Response,
    db: Session = Depends(get_session),
) -> UserPublic:
    """Valida as credenciais tradicionais e emite o Cookie HTTP-Only de sessão."""
    try:
        user = authenticate_with_credentials(
            db=db,
            email=payload.email,
            password=payload.password,
        )
    except (InvalidCredentialsError, GoogleAccountPasswordMissingError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    _set_session_cookie(response, user.id)
    return UserPublic.model_validate(user)


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

    _set_session_cookie(response, user.id)
    return UserPublic.model_validate(user)


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Retorna os dados públicos do usuário autenticado (nome e foto)",
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserPublic:
    """Retorna estritamente o identificador, nome e foto de perfil do usuário logado."""
    return UserPublic.model_validate(current_user)


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
