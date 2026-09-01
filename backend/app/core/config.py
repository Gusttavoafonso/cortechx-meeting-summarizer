from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Define a raiz do diretório que contém o arquivo .env
BASE_DIR = Path(__file__).resolve().parents[3]

class Settings(BaseSettings):
    DATABASE_URL: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/cortechx_meeting"
    )
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()