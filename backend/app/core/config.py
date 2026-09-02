from functools import lru_cache
from pathlib import Path

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    DATABASE_URL: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5434/cortechx_meeting"
    )
    DEBUG: bool = Field(False, validation_alias="APP_DEBUG")

    openai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    notion_token: SecretStr | None = None
    notion_database_id: str | None = None
    discord_webhook_url: HttpUrl | None = None

    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", PROJECT_DIR / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
