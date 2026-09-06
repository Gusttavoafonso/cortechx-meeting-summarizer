from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    DATABASE_URL: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5434/cortechx_meeting"
    )
    DEBUG: bool = Field(False, validation_alias="APP_DEBUG")

    AUDIO_STORAGE_PATH: Path = Field(
        default=BACKEND_DIR / "storage" / "meetings",
        validation_alias="AUDIO_STORAGE_PATH",
    )
    MAX_AUDIO_SIZE_MB: int = Field(250, validation_alias="MAX_AUDIO_SIZE_MB")
    ALLOWED_AUDIO_EXTENSIONS: set[str] = {
        ".mp3",
        ".wav",
        ".m4a",
        ".mp4",
        ".webm",
    }
    ALLOWED_AUDIO_MIME_TYPES: set[str] = {
        "audio/mpeg",
        "audio/mp3",
        "audio/wav",
        "audio/x-wav",
        "audio/wave",
        "audio/mp4",
        "audio/x-m4a",
        "audio/m4a",
        "audio/webm",
        "video/mp4",
        "video/webm",
    }

    groq_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    notion_token: SecretStr | None = None
    notion_database_id: str | None = None
    discord_webhook_url: HttpUrl | None = None

    WHISPER_MODEL_SIZE: str = Field(
        default="small", validation_alias="WHISPER_MODEL_SIZE"
    )
    WHISPER_DEVICE: str = Field(default="auto", validation_alias="WHISPER_DEVICE")
    WHISPER_COMPUTE_TYPE: str = Field(
        default="auto", validation_alias="WHISPER_COMPUTE_TYPE"
    )

    @field_validator("AUDIO_STORAGE_PATH", mode="before")
    @classmethod
    def resolve_storage_path(cls, v: Any) -> Path:
        if v is not None:
            path = Path(v)
            if not path.is_absolute():
                return BACKEND_DIR / path
            return path
        return BACKEND_DIR / "storage" / "meetings"

    @field_validator(
        "discord_webhook_url",
        "groq_api_key",
        "openai_api_key",
        "gemini_api_key",
        "notion_token",
        "notion_database_id",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    model_config = SettingsConfigDict(
        env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
