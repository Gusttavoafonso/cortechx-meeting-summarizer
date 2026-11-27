from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_optional_current_user
from app.core.config import DEFAULT_LLM_MODEL, DEFAULT_LLM_PROVIDER, settings
from app.core.database import get_session
from app.core.secret_crypto import SecretDecryptionError, decrypt_secret
from app.models.user import User
from app.models.user_integration import UserIntegration
from app.schemas.settings import SystemStatusResponse
from app.services.llm.service import resolve_user_llm_config

logger = logging.getLogger(__name__)

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
                try:
                    decrypted_groq = decrypt_secret(
                        raw_key,
                        user_id=current_user.id,
                        provider="groq",
                        field="api_key",
                    ).strip()
                    if decrypted_groq:
                        user_groq_key = decrypted_groq
                except SecretDecryptionError:
                    logger.warning(
                        "Falha ao descriptografar chave Groq do usuário %s.",
                        current_user.id,
                    )

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

    user_llm = resolve_user_llm_config(
        db, current_user.id if current_user is not None else None
    )
    env_llm_key = (
        settings.llm_api_key.get_secret_value().strip()
        if settings.llm_api_key is not None
        else ""
    )

    if user_llm is not None:
        llm_configured = True
        llm_source = "user"
        llm_provider = user_llm["provider"]
        llm_model = user_llm["model"]
    elif settings.llm_provider and settings.llm_model and env_llm_key:
        llm_configured = True
        llm_source = "server"
        llm_provider = settings.llm_provider
        llm_model = settings.llm_model
    else:
        llm_configured = False
        llm_source = "none"
        llm_provider = settings.llm_provider or DEFAULT_LLM_PROVIDER
        llm_model = settings.llm_model or DEFAULT_LLM_MODEL

    return SystemStatusResponse(
        status="ok",
        stt_mode=stt_mode,
        stt_source=stt_source,
        whisper_model=settings.WHISPER_MODEL_SIZE,
        llm_configured=llm_configured,
        llm_source=llm_source,
        llm_provider=llm_provider,
        llm_model=llm_model,
    )
