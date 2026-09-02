"""
Arquivo de configuração da aplicação.

Centraliza e valida as configurações da aplicação.
Lê variáveis do arquivo .env e do sistema.
Protege tokens e prepara as integrações futuras.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):

    # Configurações do Pydantic para ler variáveis de ambiente e ignorar extras
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
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

    # Mantém api key e tokens como SecretStr para proteger informações sensíveis
    openai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    notion_token: SecretStr | None = None
    notion_database_id: str | None = None
    discord_webhook_url: HttpUrl | None = None


# Função para obter as configurações da aplicação com cache para evitar múltiplas leituras do arquivo .env
@lru_cache
def get_settings() -> Settings:

    return Settings()
settings = Settings()
