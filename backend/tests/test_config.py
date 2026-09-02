from app.core.config import Settings


def test_settings_load_database_defaults() -> None:
    settings = Settings()

    assert settings.DATABASE_URL
    assert settings.DEBUG is False


def test_settings_reads_app_debug(monkeypatch) -> None:
    monkeypatch.setenv("APP_DEBUG", "true")

    settings = Settings(_env_file=None)

    assert settings.DEBUG is True
