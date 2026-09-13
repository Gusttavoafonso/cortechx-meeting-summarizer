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

    DEBUG: bool = Field(
        False,
        validation_alias="APP_DEBUG",
    )

    # Configurações genéricas do serviço de LLM.
    llm_provider: str | None = Field(
        default=None,
        validation_alias="LLM_PROVIDER",
    )

    llm_model: str | None = Field(
        default=None,
        validation_alias="LLM_MODEL",
    )

    llm_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="LLM_API_KEY",
    )

    # Configurações específicas já existentes no projeto.
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

    def validate_llm_configuration(self) -> None:
        """Valida as configurações obrigatórias para utilização do serviço de LLM."""
        missing = []

        if not self.llm_provider:
            missing.append("LLM_PROVIDER")

        if not self.llm_model:
            missing.append("LLM_MODEL")

        if self.llm_api_key is None:
            missing.append("LLM_API_KEY")

        if missing:
            raise ValueError(
                "Missing required LLM configuration: " + ", ".join(missing)
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()