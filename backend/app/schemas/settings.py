from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from app.core.config import DEFAULT_OBSIDIAN_NOTES_FOLDER

ProviderName = Literal["discord", "notion", "obsidian", "groq"]


def _clean_optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class DiscordIntegrationUpdate(BaseModel):
    enabled: bool
    webhook_url: str | None = Field(default=None, max_length=2048)

    @field_validator("webhook_url", mode="before")
    @classmethod
    def validate_webhook_url(cls, value: str | None) -> str | None:
        cleaned = _clean_optional_str(value)
        if cleaned is None:
            return None
        parsed = urlparse(cleaned)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(
                "A URL do webhook do Discord deve iniciar com http:// ou https://."
            )
        return cleaned


class NotionIntegrationUpdate(BaseModel):
    enabled: bool
    api_key: str | None = Field(default=None, max_length=512)
    database_id: str | None = Field(default=None, max_length=256)

    @field_validator("api_key", "database_id", mode="before")
    @classmethod
    def clean_fields(cls, value: str | None) -> str | None:
        return _clean_optional_str(value)


class ObsidianIntegrationUpdate(BaseModel):
    enabled: bool
    vault_path: str | None = Field(default=None, max_length=1024)
    notes_folder: str | None = Field(default=None, max_length=512)

    @field_validator("vault_path", mode="before")
    @classmethod
    def clean_vault_path(cls, value: str | None) -> str | None:
        return _clean_optional_str(value)

    @field_validator("notes_folder", mode="before")
    @classmethod
    def validate_notes_folder(cls, value: str | None) -> str | None:
        cleaned = _clean_optional_str(value)
        if cleaned is None:
            return None
        parts = cleaned.replace("\\", "/").split("/")
        if (
            cleaned.startswith(("/", "\\"))
            or any(part in {".", ".."} for part in parts)
            or ":" in parts[0]
        ):
            raise ValueError(
                "A pasta de notas do Obsidian deve ser um caminho relativo "
                f"seguro dentro do vault (ex: {DEFAULT_OBSIDIAN_NOTES_FOLDER})."
            )
        return cleaned


class GroqIntegrationUpdate(BaseModel):
    enabled: bool
    api_key: str | None = Field(default=None, max_length=512)

    @field_validator("api_key", mode="before")
    @classmethod
    def clean_api_key(cls, value: str | None) -> str | None:
        return _clean_optional_str(value)


class IntegrationStatusItem(BaseModel):
    provider: ProviderName
    enabled: bool
    is_configured: bool
    source: Literal["user", "env", "none"]
    webhook_preview: str | None = None
    api_key_masked: str | None = None
    database_id: str | None = None
    vault_path: str | None = None
    notes_folder: str | None = None


class IntegrationsSettingsResponse(BaseModel):
    discord: IntegrationStatusItem
    notion: IntegrationStatusItem
    obsidian: IntegrationStatusItem
    groq: IntegrationStatusItem


class IntegrationTestResponse(BaseModel):
    ok: bool
    detail: str


class SystemStatusResponse(BaseModel):
    status: str = "ok"
    stt_mode: Literal["groq", "local"]
    stt_source: Literal["user", "server", "local"]
    whisper_model: str
    llm_configured: bool
    llm_provider: str | None = None
    llm_model: str | None = None
