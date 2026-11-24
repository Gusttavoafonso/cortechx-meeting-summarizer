from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_optional_current_user
from app.core.config import settings
from app.core.database import get_session
from app.models.user import User
from app.models.user_integration import UserIntegration
from app.schemas.settings import SystemStatusResponse

router = APIRouter()


@router.get(
    "/status",
    response_model=SystemStatusResponse,
    summary="Status dos motores de STT e LLM",
)
def get_system_status(
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_session),
) -> SystemStatusResponse:
    user_groq_key: str | None = None
    if current_user is not None:
        row = db.scalar(
            select(UserIntegration).where(
                UserIntegration.user_id == current_user.id,
                UserIntegration.provider == "groq",
                UserIntegration.enabled.is_(True),
            )
        )
        if row is not None and isinstance(row.config, dict):
            raw_key = row.config.get("api_key")
            if isinstance(raw_key, str) and raw_key.strip():
                user_groq_key = raw_key.strip()

    server_groq_key = (
        settings.groq_api_key.get_secret_value().strip()
        if settings.groq_api_key is not None
        else ""
    )

    if user_groq_key:
        stt_mode = "groq"
        stt_source = "user"
    elif server_groq_key:
        stt_mode = "groq"
        stt_source = "server"
    else:
        stt_mode = "local"
        stt_source = "local"

    llm_api_key = (
        settings.llm_api_key.get_secret_value().strip()
        if settings.llm_api_key is not None
        else ""
    )
    llm_configured = bool(
        settings.llm_provider and settings.llm_model and llm_api_key
    )

    return SystemStatusResponse(
        status="ok",
        stt_mode=stt_mode,
        stt_source=stt_source,
        whisper_model=settings.WHISPER_MODEL_SIZE,
        llm_configured=llm_configured,
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
    )
