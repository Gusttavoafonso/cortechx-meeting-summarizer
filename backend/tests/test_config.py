from pathlib import Path

import pytest
from app.core.config import Settings
from pydantic import SecretStr


def test_settings_load_database_defaults() -> None:
    settings = Settings()

    assert settings.DATABASE_URL
    assert settings.DEBUG is False


def test_settings_reads_app_debug(monkeypatch) -> None:
    monkeypatch.setenv("APP_DEBUG", "true")

    settings = Settings(_env_file=None)

    assert settings.DEBUG is True


def test_settings_reads_llm_configuration(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-test")
    monkeypatch.setenv("LLM_API_KEY", "secret-test-key")

    settings = Settings(_env_file=None)

    assert settings.llm_provider == "openai"
    assert settings.llm_model == "gpt-test"
    assert isinstance(settings.llm_api_key, SecretStr)
    assert settings.llm_api_key.get_secret_value() == "secret-test-key"


def test_validate_llm_configuration_success(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-test")
    monkeypatch.setenv("LLM_API_KEY", "secret-test-key")

    settings = Settings(_env_file=None)

    settings.validate_llm_configuration()


def test_validate_llm_configuration_missing(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    settings = Settings(
        _env_file=None,
        llm_provider=None,
        llm_model=None,
        llm_api_key=None,
    )

    with pytest.raises(ValueError) as exc_info:
        settings.validate_llm_configuration()

    message = str(exc_info.value)

    assert "LLM_PROVIDER" in message
    assert "LLM_MODEL" in message
    assert "LLM_API_KEY" in message


def test_settings_obsidian_defaults(monkeypatch) -> None:
    for name in ("OBSIDIAN_ENABLED", "OBSIDIAN_VAULT_PATH", "OBSIDIAN_NOTES_FOLDER"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.obsidian_enabled is False
    assert settings.obsidian_vault_path is None
    assert settings.obsidian_notes_folder == "Reuniões"


def test_settings_reads_obsidian_configuration(monkeypatch) -> None:
    monkeypatch.setenv("OBSIDIAN_ENABLED", "true")
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "/vault")
    monkeypatch.setenv("OBSIDIAN_NOTES_FOLDER", "Atas/2026")

    settings = Settings(_env_file=None)

    assert settings.obsidian_enabled is True
    assert settings.obsidian_vault_path == Path("/vault")
    assert settings.obsidian_notes_folder == "Atas/2026"


def test_settings_obsidian_empty_values_use_defaults(monkeypatch) -> None:
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "")
    monkeypatch.setenv("OBSIDIAN_NOTES_FOLDER", "  ")

    settings = Settings(_env_file=None)

    assert settings.obsidian_vault_path is None
    assert settings.obsidian_notes_folder == "Reuniões"


@pytest.mark.parametrize(
    "folder", ["../fora", "a/../../b", "/etc", "\\\\servidor", "C:/x", "a\\..\\b"]
)
def test_settings_rejects_obsidian_folder_outside_vault(monkeypatch, folder) -> None:
    monkeypatch.setenv("OBSIDIAN_NOTES_FOLDER", folder)

    with pytest.raises(ValueError):
        Settings(_env_file=None)
