from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import (
    AliasChoices,
    Field,
    HttpUrl,
    SecretStr,
    ValidationError,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent
DEFAULT_OBSIDIAN_NOTES_FOLDER = "Reuniões"


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
        ".ogg",
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
        "audio/ogg",
        "video/mp4",
        "video/webm",
    }

    # Configurações genéricas do serviço de LLM
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

    groq_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"
    summary_chunk_size: int = 12000
    summary_chunk_overlap: int = 500

    gemini_api_key: SecretStr | None = None

    notion_token: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("NOTION_API_KEY", "NOTION_TOKEN"),
    )
    notion_database_id: str | None = Field(
        default=None,
        validation_alias="NOTION_DATABASE_ID",
    )

    discord_enabled: bool = Field(default=False, validation_alias="DISCORD_ENABLED")
    notion_enabled: bool = Field(default=False, validation_alias="NOTION_ENABLED")

    obsidian_enabled: bool = Field(default=False, validation_alias="OBSIDIAN_ENABLED")
    # Caminho do vault visto pelo backend (dentro do container, via volume montado).
    obsidian_vault_path: Path | None = Field(
        default=None, validation_alias="OBSIDIAN_VAULT_PATH"
    )
    obsidian_notes_folder: str = Field(
        default=DEFAULT_OBSIDIAN_NOTES_FOLDER,
        validation_alias="OBSIDIAN_NOTES_FOLDER",
    )

    discord_webhook_url: HttpUrl | None = None

    WHISPER_MODEL_SIZE: str = Field(
        default="small", validation_alias="WHISPER_MODEL_SIZE"
    )
    WHISPER_DEVICE: str = Field(default="auto", validation_alias="WHISPER_DEVICE")
    WHISPER_COMPUTE_TYPE: str = Field(
        default="auto", validation_alias="WHISPER_COMPUTE_TYPE"
    )

    # Configurações da Política de Retry (Issue #26)
    RETRY_MAX_ATTEMPTS: int = Field(default=3, validation_alias="RETRY_MAX_ATTEMPTS")
    RETRY_INITIAL_DELAY: float = Field(
        default=1.0, validation_alias="RETRY_INITIAL_DELAY"
    )
    RETRY_BACKOFF_FACTOR: float = Field(
        default=2.0, validation_alias="RETRY_BACKOFF_FACTOR"
    )
    RETRY_MAX_DELAY: float = Field(default=10.0, validation_alias="RETRY_MAX_DELAY")
    RETRY_JITTER: bool = Field(default=False, validation_alias="RETRY_JITTER")

    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="CELERY_BROKER_URL",
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="CELERY_RESULT_BACKEND",
    )
    CELERY_TASK_ALWAYS_EAGER: bool = Field(
        default=False,
        validation_alias="CELERY_TASK_ALWAYS_EAGER",
    )

    # Configurações de Autenticação Google (cookie de sessão)
    google_client_id: str | None = Field(
        default=None,
        validation_alias="GOOGLE_CLIENT_ID",
    )
    # Configurações do JWT de acesso (sem valor padrão para o segredo: a aplicação
    # não sobe sem JWT_SECRET_KEY definida).
    JWT_SECRET_KEY: SecretStr = Field(validation_alias="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=60,
        gt=0,
        validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    session_cookie_name: str = Field(
        default="session_token",
        validation_alias="SESSION_COOKIE_NAME",
    )
    session_cookie_secure: bool = Field(
        default=False,
        validation_alias="SESSION_COOKIE_SECURE",
    )
    session_cookie_samesite: str = Field(
        default="lax",
        validation_alias="SESSION_COOKIE_SAMESITE",
    )
    cors_origins: str = Field(default="", validation_alias="CORS_ORIGINS")

    @property
    def parsed_cors_origins(self) -> list[str]:
        defaults = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "tauri://localhost",
            "http://tauri.localhost",
            "https://tauri.localhost",
        ]
        extras = [
            origin.strip().rstrip("/")
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]
        return list(dict.fromkeys([*defaults, *extras]))

    @field_validator("AUDIO_STORAGE_PATH", mode="before")
    @classmethod
    def resolve_storage_path(cls, v: Any) -> Path:
        if v is not None:
            path = Path(v)
            if not path.is_absolute():
                return BACKEND_DIR / path
            return path
        return BACKEND_DIR / "storage" / "meetings"

    @field_validator("JWT_SECRET_KEY", mode="after")
    @classmethod
    def jwt_secret_must_not_be_blank(cls, v: SecretStr) -> SecretStr:
        if not v.get_secret_value().strip():
            raise ValueError("JWT_SECRET_KEY não pode ser vazia")
        return v

    @field_validator(
        "discord_webhook_url",
        "groq_api_key",
        "openai_api_key",
        "gemini_api_key",
        "notion_token",
        "notion_database_id",
        "llm_api_key",
        "obsidian_vault_path",
        "google_client_id",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("obsidian_notes_folder", mode="before")
    @classmethod
    def validate_obsidian_notes_folder(cls, v: Any) -> Any:
        """Usa o padrão se vazio e rejeita pastas que escapem do vault."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return DEFAULT_OBSIDIAN_NOTES_FOLDER
        if not isinstance(v, str):
            return v
        folder = v.strip()
        parts = folder.replace("\\", "/").split("/")
        if folder.startswith(("/", "\\")) or ".." in parts or ":" in parts[0]:
            raise ValueError(
                "OBSIDIAN_NOTES_FOLDER deve ser um caminho relativo dentro do vault."
            )
        return folder
    @field_validator(
        "discord_enabled", "notion_enabled", "obsidian_enabled", mode="before"
    )
    @classmethod
    def empty_str_bool_to_false(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return False
        return v

    model_config = SettingsConfigDict(
        env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env", ".env"),
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
    try:
        return Settings()
    except ValidationError as exc:
        if any("JWT_SECRET_KEY" in map(str, err["loc"]) for err in exc.errors()):
            raise RuntimeError(
                "Configuração inválida: JWT_SECRET_KEY ausente ou vazia. "
                "Defina JWT_SECRET_KEY no .env ou no ambiente. Para gerar um "
                'valor: python -c "import secrets; print(secrets.token_urlsafe(64))"'
            ) from exc
        raise


settings = get_settings()
