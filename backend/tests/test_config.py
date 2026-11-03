import pytest
from app.core.config import Settings, get_settings
from pydantic import SecretStr, ValidationError


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


def test_jwt_settings_defaults(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "segredo-de-teste")
    monkeypatch.delenv("JWT_ALGORITHM", raising=False)
    monkeypatch.delenv("ACCESS_TOKEN_EXPIRE_MINUTES", raising=False)

    settings = Settings(_env_file=None)

    assert isinstance(settings.JWT_SECRET_KEY, SecretStr)
    assert settings.JWT_SECRET_KEY.get_secret_value() == "segredo-de-teste"
    assert settings.JWT_ALGORITHM == "HS256"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 60
    assert "segredo-de-teste" not in repr(settings)


def test_missing_jwt_secret_fails_clearly(monkeypatch) -> None:
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)

    get_settings.cache_clear()
    try:
        monkeypatch.setattr(
            "app.core.config.Settings",
            lambda: Settings(_env_file=None),
        )
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_blank_jwt_secret_rejected(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "   ")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
